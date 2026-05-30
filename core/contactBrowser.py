import asyncio
import json
import logging
import os
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from playwright.async_api import async_playwright

from core.notifier import sendTelegram

PROFILE_DIR = Path(os.getenv("DIVAR_PROFILE_DIR", Path.cwd() / "divar_browser_profile"))
CONTACT_CAPTCHA = "__CAPTCHA_REQUIRED__"


def isCaptchaResponse(status, bodyText):
    if status in [401, 403, 429]:
        return True

    if not bodyText:
        return False

    lowered = bodyText.lower()

    captchaSignals = [
        "captcha",
        "کپچا",
        "blocked",
        "too many requests",
        "rate limit",
        "ربات",
    ]

    return any(signal in lowered for signal in captchaSignals)


def isOtpOrContactChallengeResponse(status, bodyText):
    """
    Divar sometimes answers the contact_info API with HTTP 200 but without
    phone_number, because the real UI has opened the security-code/OTP step.
    If we return None in that case, adFetcher incorrectly logs "mobile not found".
    Returning CONTACT_CAPTCHA lets the existing captchaBreakMain flow open the
    ad page, wait for the OTP, submit it, and then extract the mobile number.
    """
    if status != 200 or not bodyText:
        return False

    lowered = bodyText.lower()
    textSignals = [
        "otp",
        "one_time",
        "one-time",
        "verification",
        "verify",
        "security_code",
        "security code",
        "کد امنیتی",
        "کد تایید",
        "کد تأیید",
        "کد پیامک",
        "ارسال شده",
        "ثبت کد امنیتی",
        "درخواست مجدد",
    ]

    if any(signal in lowered for signal in textSignals):
        return True

    try:
        body = json.loads(bodyText)
    except Exception:
        return False

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                keyText = str(key).lower()
                if any(signal in keyText for signal in textSignals):
                    return True
                if walk(child):
                    return True
        elif isinstance(value, list):
            return any(walk(item) for item in value)
        elif isinstance(value, str):
            valueText = value.lower()
            return any(signal in valueText for signal in textSignals)
        return False

    return walk(body)


async def fetchContactAsync(token, contactUuid):
    context = None

    try:
        if not PROFILE_DIR.exists():
            logging.warning(
                "divar_browser_profile not found. Run python -m core.login first."
            )
            return None

        headless = os.getenv("CONTACT_BROWSER_HEADLESS", "true").lower() == "true"

        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                headless=headless,
                executable_path="/usr/bin/chromium",
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/137.0.0.0 Safari/537.36"
                ),
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            page = context.pages[0] if context.pages else await context.new_page()

            # اول صفحه آگهی را مثل کاربر واقعی باز می‌کنیم
            adUrl = f"https://divar.ir/v/-/{token}"

            try:
                await page.goto(adUrl, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(random.randint(15000, 35000))
            except Exception as e:
                logging.warning(f"Could not open ad page before contact fetch: {e}")

            url = f"https://api.divar.ir/v8/postcontact/web/contact_info_v2/{token}"

            result = await page.evaluate(
                """
                async ({url, contactUuid}) => {
                    const response = await fetch(url, {
                        method: 'POST',
                        credentials: 'include',
                        headers: {
                            'content-type': 'application/json'
                        },
                        body: JSON.stringify({
                            contact_uuid: contactUuid
                        })
                    });

                    return {
                        status: response.status,
                        body: await response.text()
                    };
                }
                """,
                {"url": url, "contactUuid": contactUuid},
            )

            status = result.get("status")
            bodyText = result.get("body", "")

            if isOtpOrContactChallengeResponse(status, bodyText):
                logging.warning(
                    f"Contact OTP/security-code challenge detected for token {token}. "
                    "Switching to browser challenge flow."
                )

                message = (
                    "⚠️ مرحله کد امنیتی/OTP دیوار فعال شد.\n\n"
                    f"Token: <code>{token}</code>\n"
                    f"Status: <code>{status}</code>\n\n"
                    "سیستم مسیر مرورگر را اجرا می‌کند تا کد پیامکی را وارد کند و شماره را بخواند."
                )

                sendTelegram(message)
                await context.close()
                return CONTACT_CAPTCHA

            if isCaptchaResponse(status, bodyText):
                message = (
                    "⚠️ کپچای دیوار فعال شد.\n\n"
                    f"Token: <code>{token}</code>\n"
                    f"Status: <code>{status}</code>\n\n"
                    "برای رفع مشکل:\n"
                    "1. فایل login.py را اجرا کن.\n"
                    "2. روی یک آگهی برو.\n"
                    "3. نمایش شماره را بزن.\n"
                    "4. کپچا را دستی حل کن.\n"
                    "5. صفحه را ببند و crawler را ادامه بده."
                )

                sendTelegram(message)
                await context.close()
                return CONTACT_CAPTCHA

            if status != 200:
                logging.warning(
                    f"Contact request failed for token {token}. Status: {status}"
                )
                await context.close()
                return None

            try:
                body = json.loads(bodyText)
            except json.JSONDecodeError:
                logging.warning(f"Invalid contact JSON for token {token}")
                await context.close()
                return None

            widgetList = body.get("widget_list", [])

            for item in widgetList:
                if item.get("widget_type") != "UNEXPANDABLE_ROW":
                    continue

                payload = item.get("data", {}).get("action", {}).get("payload", {})
                phoneNumber = payload.get("phone_number")

                if phoneNumber:
                    await context.close()
                    return phoneNumber

            logging.warning(
                f"Contact response for token {token} was 200 but contained neither "
                "phone_number nor a known OTP/captcha signal."
            )

            await context.close()
            return None

    except Exception as e:
        logging.error(f"Get contact mobile number failed for token {token}: {e}")

        try:
            if context:
                await context.close()
        except Exception:
            pass

        return None


def _runFetchContactInDedicatedThread(token, contactUuid):
    """
    Run the async Playwright contact fetch in a fresh thread.

    This is used when the current thread already has an active asyncio loop.
    Creating another loop in the same thread causes:
    "Cannot run the event loop while another loop is running".
    """

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="contact-browser") as executor:
        future = executor.submit(lambda: asyncio.run(fetchContactAsync(token, contactUuid)))
        return future.result()


def getContactSync(token, contactUuid):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # Normal synchronous path: no loop is running in this thread.
        return asyncio.run(fetchContactAsync(token, contactUuid))

    # Safe path for callers that are already inside an asyncio loop.
    logging.warning(
        f"Active asyncio loop detected while getting contact for token {token}; "
        "running contact browser in a dedicated thread."
    )
    return _runFetchContactInDedicatedThread(token, contactUuid)

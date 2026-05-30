import requests
import logging
import os
import queue
import re
import threading
import time
from playwright.sync_api import sync_playwright
from core.httpClient import refreshDynamicHeaders
from flask import Flask, request
import cv2
import random

app = Flask(__name__)

_smsQueue = queue.Queue()
_serverStarted = False
_serverLock = threading.Lock()


def extractMobileFromPage(page):
    selectors = [
        "a[href^='tel:']",
        "text=/09[0-9]{9}/",
    ]

    try:
        telLinks = page.locator("a[href^='tel:']")

        for index in range(telLinks.count()):
            href = telLinks.nth(index).get_attribute("href")

            if href and href.startswith("tel:"):
                mobile = href.replace("tel:", "").strip()

                if mobile:
                    return mobile

    except Exception:
        pass

    try:
        bodyText = page.locator("body").inner_text(timeout=3000)
        match = re.search(r"09\d{9}", bodyText)

        if match:
            return match.group(0)

    except Exception:
        pass

    return None


# -----------------------------------------
# ********** CAPTCHA PART **********
# -----------------------------------------


def downloadImages(bg_url, piece_url):
    bg = requests.get(bg_url, timeout=15).content
    piece = requests.get(piece_url, timeout=15).content

    with open("bg.png", "wb") as f:
        f.write(bg)

    with open("piece.png", "wb") as f:
        f.write(piece)


def findPuzzleX():
    bg = cv2.imread("bg.png", 0)
    piece = cv2.imread("piece.png", 0)

    if bg is None or piece is None:
        raise Exception("captcha_images_not_loaded")

    bg = cv2.GaussianBlur(bg, (3, 3), 0)
    piece = cv2.GaussianBlur(piece, (3, 3), 0)

    _, mask = cv2.threshold(piece, 40, 255, cv2.THRESH_BINARY)

    coords = cv2.findNonZero(mask)

    if coords is None:
        raise Exception("puzzle_mask_empty")

    x, y, w, h = cv2.boundingRect(coords)

    piece_crop = piece[y : y + h, x : x + w]
    mask_crop = mask[y : y + h, x : x + w]

    result = cv2.matchTemplate(
        bg,
        piece_crop,
        cv2.TM_CCOEFF_NORMED,
        mask=mask_crop,
    )

    candidates = []

    for _ in range(8):
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        candidates.append(
            {
                "x": int(max_loc[0]),
                "confidence": float(max_val),
            }
        )

        cv2.rectangle(
            result,
            (max_loc[0] - 20, max_loc[1] - 20),
            (max_loc[0] + 20, max_loc[1] + 20),
            -999,
            -1,
        )

    best = candidates[0]

    logging.info(f"[captcha] candidates: {candidates}")

    return {
        "x": best["x"],
        "confidence": best["confidence"],
        "piece_width": w,
    }


def humanDrag(page, slider, distance):

    box = slider.bounding_box()

    if not box:
        raise Exception("slider_box_missing")

    start_x = box["x"] + box["width"] / 2
    start_y = box["y"] + box["height"] / 2

    page.mouse.move(
        start_x + random.uniform(-2, 2),
        start_y + random.uniform(-2, 2),
        steps=random.randint(20, 40),
    )

    time.sleep(random.uniform(0.3, 0.8))

    page.mouse.down()

    current = 0

    while current < distance:

        remain = distance - current

        if remain > 120:
            move = random.uniform(12, 18)

        elif remain > 60:
            move = random.uniform(6, 10)

        elif remain > 20:
            move = random.uniform(2, 5)

        else:
            move = random.uniform(0.5, 2)

        current += move

        curve_y = random.uniform(-1.2, 1.2)

        page.mouse.move(
            start_x + current,
            start_y + curve_y,
            steps=random.randint(1, 3),
        )

        time.sleep(random.uniform(0.008, 0.03))

    for _ in range(random.randint(2, 5)):

        offset = random.uniform(-2, 2)

        page.mouse.move(
            start_x + distance + offset,
            start_y + random.uniform(-1, 1),
            steps=2,
        )

        time.sleep(random.uniform(0.03, 0.08))

    time.sleep(random.uniform(0.1, 0.3))

    page.mouse.up()

    page.wait_for_timeout(random.randint(1800, 2600))


def detectContactResult(page, timeout=90000):

    start = time.time()

    while time.time() - start < timeout / 1000:

        try:

            if page.locator(".arc-puzzle:visible").count() > 0:
                return "puzzle"

            if (
                page.locator("input[name='otp']:visible").count() > 0
                or page.locator("input[aria-label='کد امنیتی']:visible").count() > 0
                or page.locator("button:has-text('ثبت کد امنیتی'):visible").count() > 0
                or page.locator("button:has-text('درخواست مجدد'):visible").count() > 0
                or page.locator("text=کد امنیتی").count() > 0
                or page.locator("text=کد تایید").count() > 0
                or page.locator("text=کد تأیید").count() > 0
            ):
                return "otp"

            if (
                page.locator("a[href^='tel:']").count() > 0
                or page.locator("text=تماس با").count() > 0
            ):
                return "contact_opened"

            if (
                page.locator("text=خطا").count() > 0
                or page.locator("text=محدود").count() > 0
            ):
                return "error_or_limit"

        except Exception:
            pass

        page.wait_for_timeout(1500)

    return "unknown"


def captchaResult(status, reason=None, token=None, extra=None):

    return {
        "ok": status == "success",
        "status": status,
        "reason": reason,
        "token": token,
        "extra": extra or {},
    }


def solveCaptcha(token):

    playwright = sync_playwright().start()

    browser_context = None

    try:

        logging.info(f"[captcha] starting for {token}")

        profileDir = os.getenv(
            "DIVAR_PROFILE_DIR",
            "/app/profiles/phone1",
        )

        os.makedirs(profileDir, exist_ok=True)

        headless = os.getenv(
            "PLAYWRIGHT_HEADLESS",
            "true",
        ).lower() in {
            "1",
            "true",
            "yes",
        }

        browser_context = playwright.chromium.launch_persistent_context(
            user_data_dir=profileDir,
            headless=headless,
            executable_path=os.getenv(
                "CHROMIUM_PATH",
                "/usr/bin/chromium",
            ),
            viewport={
                "width": 1400,
                "height": 900,
            },
            locale="fa-IR",
            timezone_id="Asia/Tehran",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--start-maximized",
            ],
        )

        page = (
            browser_context.pages[0]
            if browser_context.pages
            else browser_context.new_page()
        )

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        """)

        page.set_default_timeout(30000)

        target_url = f"https://divar.ir/v/{token}"

        page.goto(
            target_url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_timeout(3000)

        contact_button = page.locator("button.post-actions__get-contact").first

        contact_button.wait_for(
            state="visible",
            timeout=30000,
        )

        if not contact_button.is_enabled():

            return captchaResult(
                "failed",
                reason="contact_button_disabled",
                token=token,
            )

        contact_button.click(timeout=15000)

        page.wait_for_timeout(2000)

        result = None

        for _ in range(12):

            result = detectContactResult(
                page,
                timeout=4000,
            )

            if result in ["otp", "contact_opened"]:

                return {
                    "ok": True,
                    "status": "success",
                    "reason": result,
                    "token": token,
                    "page": page,
                    "context": browser_context,
                    "playwright": playwright,
                }

            if result == "error_or_limit":

                return captchaResult(
                    "blocked",
                    reason="error_or_limit",
                    token=token,
                )

            if result == "puzzle":
                break

            page.wait_for_timeout(1500)

        if result != "puzzle":

            return captchaResult(
                "unknown",
                reason=f"last_result={result}",
                token=token,
            )

        page.wait_for_selector(
            ".arc-puzzle",
            state="visible",
            timeout=15000,
        )

        bg_url = page.locator(".arc-puzzle img").nth(0).get_attribute("src")

        piece_url = page.locator("img.puzzle").get_attribute("src")

        failedCount = 0
        if not bg_url or not piece_url:
            if failedCount > 3:
                solveCaptcha(token)
                failedCount += 1
            return captchaResult(
                "failed",
                reason="captcha_images_missing",
                token=token,
            )

        downloadImages(
            bg_url,
            piece_url,
        )

        bg_img = cv2.imread("bg.png")

        piece_img = cv2.imread("piece.png")

        if bg_img is None or piece_img is None:

            return captchaResult(
                "failed",
                reason="captcha_image_read_failed",
                token=token,
            )

        match = findPuzzleX()

        x = match["x"]
        confidence = match["confidence"]

        logging.info(f"[captcha] x={x} confidence={confidence}")

        box = page.locator(".arc-puzzle").bounding_box()

        if not box:

            return captchaResult(
                "failed",
                reason="puzzle_box_empty",
                token=token,
            )

        display_width = box["width"]

        real_width = bg_img.shape[1]

        slider = page.locator(".draggable").first

        slider.wait_for(
            state="visible",
            timeout=10000,
        )

        slider_box = slider.bounding_box()

        if not slider_box:

            return captchaResult(
                "failed",
                reason="slider_box_empty",
                token=token,
            )

        track_distance = display_width - slider_box["width"]

        base_distance = (x / real_width) * track_distance

        if confidence < 0.60:

            offsets = [
                -18,
                -14,
                -10,
                -7,
                -5,
                -3,
                0,
                3,
                5,
                7,
                10,
                14,
                18,
            ]

        else:

            offsets = [-6, -3, 0, 3, 6]

        attempt_distances = [base_distance + off for off in offsets]

        logging.info(f"[captcha] drag attempts: {attempt_distances}")

        for idx, dist in enumerate(attempt_distances):

            logging.info(f"[captcha] drag attempt {idx} distance={dist}")

            try:

                humanDrag(
                    page,
                    slider,
                    dist,
                )

            except Exception as e:

                logging.warning(f"[captcha] drag exception: {e}")

                continue

            page.wait_for_timeout(3500)

            result = detectContactResult(
                page,
                timeout=6000,
            )

            logging.info(f"[captcha] result after drag: {result}")

            if result in ["otp", "contact_opened"]:

                return {
                    "ok": True,
                    "status": "success",
                    "reason": result,
                    "token": token,
                    "page": page,
                    "context": browser_context,
                    "playwright": playwright,
                }

            try:

                slider = page.locator(".draggable").first

                slider.wait_for(
                    state="visible",
                    timeout=5000,
                )

            except Exception:
                break

        return captchaResult(
            "failed",
            reason="all_drag_attempts_failed",
            token=token,
            extra={
                "confidence": confidence,
                "base_distance": base_distance,
            },
        )

    except Exception as e:

        logging.exception(f"[captcha] failed for token {token}: {e}")

        try:
            if browser_context:
                browser_context.close()
        except Exception:
            pass

        try:
            playwright.stop()
        except Exception:
            pass

        return captchaResult(
            "failed",
            reason=str(e),
            token=token,
        )


# -----------------------------------------
# ************ SMS / OTP PART ************
# -----------------------------------------

_smsEvents = []
_smsCondition = threading.Condition()


def normalizeText(value):
    if value is None:
        return ""

    return (
        str(value)
        .replace("\u200f", "")
        .replace("\u200e", "")
        .replace("\u200c", " ")
        .replace("\u200d", " ")
        .replace("ي", "ی")
        .replace("ك", "ک")
        .strip()
    )


def extractSmsCode(message):
    message = normalizeText(message)

    patterns = [
        r"Code\s*:\s*([0-9]{4,8})",
        r"code\s*:\s*([0-9]{4,8})",
        r"کد\s*[:：]?\s*([0-9]{4,8})",
        r"(?<!\d)([0-9]{6})(?!\d)",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            return match.group(1)

    return None


@app.route("/sms", methods=["GET", "POST"])
def sms():
    sender = (
        request.args.get("from")
        or request.args.get("sender")
        or request.form.get("from")
        or request.form.get("sender")
    )

    msg = (
        request.args.get("msg")
        or request.args.get("message")
        or request.form.get("msg")
        or request.form.get("message")
    )

    if request.is_json:
        body = request.get_json(silent=True) or {}
        sender = sender or body.get("from") or body.get("sender")
        msg = msg or body.get("msg") or body.get("message") or body.get("text")

    sender = normalizeText(sender)
    msg = normalizeText(msg)
    code = extractSmsCode(msg)

    logging.info(f"New SMS received. sender={sender}, code={code}")

    if code:
        event = {
            "sender": sender,
            "message": msg,
            "code": code,
            "received_at": time.time(),
        }

        with _smsCondition:
            _smsEvents.append(event)
            # keep memory bounded and avoid very old OTP reuse
            del _smsEvents[:-50]
            _smsCondition.notify_all()

    return "OK"


def startSmsServer():
    global _serverStarted

    with _serverLock:
        if _serverStarted:
            return

        host = os.getenv("SMS_WEBHOOK_HOST", "0.0.0.0")
        port = int(os.getenv("SMS_WEBHOOK_PORT", "5000"))

        thread = threading.Thread(
            target=lambda: app.run(
                host=host,
                port=port,
                debug=False,
                use_reloader=False,
            ),
            daemon=True,
            name=f"sms-webhook-{port}",
        )

        thread.start()
        _serverStarted = True

        logging.info(f"SMS webhook server started on {host}:{port}")


def getSmsCode(timeout=None, since=None):
    """
    Wait for an SMS OTP without consuming it from a global Queue.
    This fixes the race where an old listener thread could steal the current OTP.
    """
    startSmsServer()

    if timeout is None:
        timeout = int(os.getenv("SMS_CODE_TIMEOUT", "300"))

    if since is None:
        since = time.time()

    deadline = time.time() + timeout
    logging.info(f"Waiting for SMS code for {timeout} seconds...")

    with _smsCondition:
        while True:
            for item in reversed(_smsEvents):
                if item.get("received_at", 0) >= since and item.get("code"):
                    code = item.get("code")
                    logging.info(f"OTP code received from SMS: {code}")
                    return code

            remaining = deadline - time.time()
            if remaining <= 0:
                logging.warning("SMS code timeout.")
                return None

            _smsCondition.wait(timeout=min(remaining, 2))



def clickOtpResendIfAvailable(page, wait_seconds=None):
    """
    Click Divar's OTP resend button after its cooldown.
    Divar usually enables "درخواست مجدد" about 2 minutes after the first SMS.
    """
    if page is None:
        return False

    if wait_seconds is None:
        wait_seconds = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "120"))

    selectors = [
        "button[aria-label='درخواست مجدد']",
        "button.resend-button",
        "button:has-text('درخواست مجدد')",
        "text=درخواست مجدد",
    ]

    logging.info(f"[otp] waiting {wait_seconds}s before clicking resend")
    if wait_seconds > 0:
        page.wait_for_timeout(wait_seconds * 1000)

    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() == 0:
                continue

            locator.wait_for(state="visible", timeout=3000)

            enabled_deadline = time.time() + 15
            while time.time() < enabled_deadline:
                try:
                    if not locator.is_disabled():
                        locator.click(timeout=5000)
                        logging.info(f"[otp] resend clicked: {selector}")
                        page.wait_for_timeout(1500)
                        return True
                except Exception:
                    break

                page.wait_for_timeout(500)

        except Exception as e:
            logging.debug(f"[otp] resend selector skipped {selector}: {e}")

    logging.warning("[otp] resend button was not found/enabled")
    return False


def getOtpCode(token=None, started_at=None, page=None):
    """
    Listen for the first SMS OTP. If it is not received, wait for Divar's
    2-minute resend cooldown, click "درخواست مجدد", then listen again.
    Telegram/manual input is still kept as the last fallback.
    """
    if started_at is None:
        started_at = time.time()

    auto_timeout = int(os.getenv("AUTO_SMS_OTP_TIMEOUT", "45"))
    after_resend_timeout = int(os.getenv("AUTO_SMS_OTP_AFTER_RESEND_TIMEOUT", "90"))
    manual_timeout = int(os.getenv("MANUAL_TELEGRAM_OTP_TIMEOUT", "180"))
    resend_cooldown = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "120"))

    # 1) First listen: covers the normal "OTP modal opened, SMS received" path.
    code = getSmsCode(timeout=auto_timeout, since=started_at)
    if code:
        return code, "sms"

    # 2) No SMS yet: click resend, but only after Divar's 2-minute cooldown.
    resend_clicked = False
    if page is not None:
        elapsed = time.time() - started_at
        wait_before_resend = max(0, resend_cooldown - int(elapsed))
        resend_clicked = clickOtpResendIfAvailable(
            page,
            wait_seconds=wait_before_resend,
        )

        if resend_clicked:
            resend_started_at = time.time()
            code = getSmsCode(timeout=after_resend_timeout, since=resend_started_at)
            if code:
                return code, "sms_resend"

    # 3) Manual Telegram fallback after both automatic listens failed.
    try:
        from core.notifier import waitTelegramOtp

        code = waitTelegramOtp(
            token=token,
            timeout=manual_timeout,
            prompt=True,
        )
        if code:
            return code, "telegram"

    except Exception as e:
        logging.warning(f"Telegram manual OTP fallback failed: {e}")

    # Last short check: maybe SMS arrived while the operator prompt was being sent.
    code = getSmsCode(timeout=5, since=started_at)
    if code:
        return code, "sms_late"

    return None, None

def findOtpInput(page, timeout=30000):
    selectors = [
        "input[name='otp']",
        "input[autocomplete='one-time-code']",
        "input[type='tel']",
        "input[inputmode='numeric']",
        "input:visible",
    ]

    deadline = time.time() + (timeout / 1000)

    while time.time() < deadline:
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if locator.count() > 0:
                    locator.wait_for(state="visible", timeout=1000)
                    return locator
            except Exception:
                pass

        page.wait_for_timeout(300)

    raise Exception("otp_input_not_found")


def clickOtpSubmitIfPresent(page):
    submit_selectors = [
        "button:has-text('ثبت کد امنیتی')",
        "button:has-text('تایید')",
        "button:has-text('تأیید')",
        "button[type='submit']",
    ]

    for selector in submit_selectors:
        try:
            button = page.locator(selector).first
            if button.count() == 0:
                continue

            button.wait_for(state="visible", timeout=1500)

            wait_start = time.time()
            while button.is_disabled() and time.time() - wait_start < 8:
                page.wait_for_timeout(250)

            if button.is_enabled():
                button.click(timeout=5000)
                logging.info(f"[otp] submit clicked: {selector}")
                return True

        except Exception as e:
            logging.debug(f"[otp] submit selector skipped {selector}: {e}")

    return False


def submitOtpWithPlaywright(page, otpCode):
    try:
        logging.info(f"[otp] submitting otp: {otpCode}")

        otp_input = findOtpInput(page, timeout=30000)
        page.wait_for_timeout(random.randint(500, 1200))

        otp_input.click(timeout=5000)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(str(otpCode), delay=random.randint(50, 120))

        logging.info("[otp] otp typed")

        # The OTP input can disappear immediately after auto-submit. Do not fail on that.
        verified_or_detached = False
        verify_deadline = time.time() + 8

        while time.time() < verify_deadline:
            result = detectContactResult(page, timeout=1000)
            if result == "contact_opened":
                return {"ok": True, "status": "success", "mode": "auto_submit"}

            try:
                value = otp_input.input_value(timeout=1000)
                if value == str(otpCode):
                    verified_or_detached = True
                    break
            except Exception:
                # DOM changed after typing; this is common in auto-submit flows.
                verified_or_detached = True
                break

            page.wait_for_timeout(250)

        if not verified_or_detached:
            logging.warning(
                "[otp] could not verify input value, continuing to result checks"
            )

        page.wait_for_timeout(1500)

        result = detectContactResult(page, timeout=5000)
        if result == "contact_opened":
            return {"ok": True, "status": "success", "mode": "auto_submit"}

        clickOtpSubmitIfPresent(page)

        result = detectContactResult(page, timeout=12000)
        logging.info(f"[otp] result={result}")

        if result == "contact_opened":
            return {"ok": True, "status": "success", "mode": "button_submit"}

        invalid_texts = ["نامعتبر", "اشتباه", "کد صحیح نیست", "کد امنیتی"]
        for txt in invalid_texts:
            try:
                if page.locator(f"text={txt}").count() > 0:
                    return {"ok": False, "status": "invalid_otp"}
            except Exception:
                pass

        if result == "error_or_limit":
            return {"ok": False, "status": "blocked"}

        return {"ok": False, "status": "unknown", "last_result": result}

    except Exception as e:
        logging.exception(f"[otp] submit failed: {e}")
        return {"ok": False, "status": "exception", "reason": str(e)}


def closeCaptchaResources(captcha_result):
    for key, closer in [
        ("context", lambda obj: obj.close()),
        ("playwright", lambda obj: obj.stop()),
    ]:
        obj = captcha_result.get(key) if isinstance(captcha_result, dict) else None
        if obj:
            try:
                closer(obj)
            except Exception:
                pass


def captchaBreakMain(session, res, token=None):
    logging.info("Start contact challenge check...")
    startSmsServer()
    challenge_started_at = time.time()
    captcha_result = {}

    try:
        captcha_result = solveCaptcha(token)
        status = captcha_result.get("status")
        reason = captcha_result.get("reason")
        extra = captcha_result.get("extra", {})

        logging.info(
            f"[captchaBreakMain] token={token}, status={status}, reason={reason}"
        )

        if status != "success":
            if status == "blocked":
                return {
                    "ok": False,
                    "status": "blocked",
                    "reason": reason,
                    "token": token,
                    "extra": extra,
                }

            return {
                "ok": False,
                "status": status or "failed",
                "reason": reason,
                "token": token,
                "extra": extra,
            }

        page = captcha_result.get("page")

        if not page:
            return {
                "ok": False,
                "status": "page_missing",
                "reason": reason,
                "token": token,
            }

        # حالت ۱: شماره مستقیم باز شده و OTP لازم نیست
        if reason == "contact_opened":
            mobile = extractMobileFromPage(page)

            if mobile:
                return {
                    "ok": True,
                    "status": "success",
                    "reason": "contact_opened",
                    "token": token,
                    "mobile": mobile,
                    "otp_source": None,
                    "otp_result": {
                        "ok": True,
                        "status": "not_required",
                    },
                }

            return {
                "ok": False,
                "status": "no_mobile",
                "reason": "contact_opened_but_mobile_not_found",
                "token": token,
            }

        # حالت ۲: OTP لازم شده
        if reason == "otp":
            logging.info(f"Contact challenge opened OTP step for token {token}")

            otp, otp_source = getOtpCode(
                token=token,
                started_at=challenge_started_at,
                page=page,
            )

            if not otp:
                return {
                    "ok": False,
                    "status": "otp_timeout",
                    "reason": "sms_and_telegram_otp_not_received",
                    "token": token,
                }

            logging.info(
                f"[otp] OTP received for token {token} from {otp_source}: {otp}"
            )

            otp_response = submitOtpWithPlaywright(
                page=page,
                otpCode=otp,
            )

            if not otp_response or not otp_response.get("ok"):
                first_failure_reason = (
                    otp_response.get("status")
                    if isinstance(otp_response, dict)
                    else "otp_response_empty"
                )

                # If an old/wrong OTP was consumed, request a fresh code once.
                if first_failure_reason in ["invalid_otp", "unknown"]:
                    logging.warning(
                        f"[otp] first OTP failed for token {token}: {first_failure_reason}. "
                        "Trying resend once."
                    )

                    resend_clicked = clickOtpResendIfAvailable(page, wait_seconds=None)
                    if resend_clicked:
                        resend_started_at = time.time()
                        retry_otp, retry_source = getSmsCode(
                            timeout=int(os.getenv("AUTO_SMS_OTP_AFTER_RESEND_TIMEOUT", "90")),
                            since=resend_started_at,
                        ), "sms_resend_after_invalid"

                        if retry_otp:
                            retry_response = submitOtpWithPlaywright(
                                page=page,
                                otpCode=retry_otp,
                            )
                            if retry_response and retry_response.get("ok"):
                                otp = retry_otp
                                otp_source = retry_source
                                otp_response = retry_response
                            else:
                                return {
                                    "ok": False,
                                    "status": "otp_submit_failed",
                                    "reason": (
                                        retry_response.get("status")
                                        if isinstance(retry_response, dict)
                                        else "retry_otp_response_empty"
                                    ),
                                    "token": token,
                                    "otp_source": retry_source,
                                    "otp_result": retry_response,
                                    "first_otp_source": otp_source,
                                    "first_otp_result": otp_response,
                                }
                        else:
                            return {
                                "ok": False,
                                "status": "otp_timeout",
                                "reason": "otp_invalid_then_resend_sms_not_received",
                                "token": token,
                                "otp_source": otp_source,
                                "otp_result": otp_response,
                            }
                    else:
                        return {
                            "ok": False,
                            "status": "otp_submit_failed",
                            "reason": "otp_failed_and_resend_not_available",
                            "token": token,
                            "otp_source": otp_source,
                            "otp_result": otp_response,
                        }

                if not otp_response or not otp_response.get("ok"):
                    return {
                        "ok": False,
                        "status": "otp_submit_failed",
                        "reason": first_failure_reason,
                        "token": token,
                        "otp_source": otp_source,
                        "otp_result": otp_response,
                    }

            mobile = extractMobileFromPage(page)

            if mobile:
                return {
                    "ok": True,
                    "status": "success",
                    "reason": "otp",
                    "token": token,
                    "mobile": mobile,
                    "otp_source": otp_source,
                    "otp_result": otp_response,
                }

            return {
                "ok": False,
                "status": "no_mobile",
                "reason": "otp_success_but_mobile_not_found",
                "token": token,
                "otp_source": otp_source,
                "otp_result": otp_response,
            }

        return {
            "ok": False,
            "status": "unknown_success_reason",
            "reason": reason,
            "token": token,
            "extra": extra,
        }

    except Exception as e:
        logging.exception(f"Contact challenge check failed: {e}")

        return {
            "ok": False,
            "status": "exception",
            "reason": str(e),
            "token": token,
        }

    finally:
        closeCaptchaResources(captcha_result)

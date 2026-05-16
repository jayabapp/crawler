import asyncio
import json
import logging
import random
from pathlib import Path

from playwright.async_api import async_playwright


def getStorageStatePath():
    rootStatePath = Path.cwd() / "divar_state.json"

    if rootStatePath.exists():
        return str(rootStatePath)

    vehicleStatePath = Path.cwd() / "categories" / "vehicleRental" / "divar_state.json"

    if vehicleStatePath.exists():
        logging.warning(
            "divar_state.json is inside categories/vehicleRental. "
            "Move it to project root."
        )
        return str(vehicleStatePath)

    return None


async def fetchContactAsync(token, contactUuid):
    browser = None

    try:
        storageStatePath = getStorageStatePath()

        if not storageStatePath:
            logging.warning("divar_state.json not found. Cannot fetch contact.")
            return None

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            context = await browser.new_context(
                storage_state=storageStatePath,
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/137.0.0.0 Safari/537.36"
                ),
            )

            page = await context.new_page()

            await page.goto("https://divar.ir", wait_until="networkidle")
            await page.wait_for_timeout(random.randint(2000, 4000))

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

            if result["status"] != 200:
                logging.warning(
                    f"Contact request failed for token {token}. Status: {result['status']}"
                )
                await browser.close()
                return None

            try:
                body = json.loads(result["body"])
            except json.JSONDecodeError:
                logging.warning(f"Invalid contact JSON for token {token}")
                await browser.close()
                return None

            widgetList = body.get("widget_list", [])

            for item in widgetList:
                if item.get("widget_type") != "UNEXPANDABLE_ROW":
                    continue

                payload = item.get("data", {}).get("action", {}).get("payload", {})
                phoneNumber = payload.get("phone_number")

                if phoneNumber:
                    await browser.close()
                    return phoneNumber

            await browser.close()
            return None

    except Exception as e:
        logging.error(f"Get contact mobile number failed for token {token}: {e}")

        try:
            if browser:
                await browser.close()
        except Exception:
            pass

        return None


def getContactSync(token, contactUuid):
    try:
        return asyncio.run(fetchContactAsync(token, contactUuid))
    except RuntimeError:
        loop = asyncio.new_event_loop()

        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(fetchContactAsync(token, contactUuid))
        finally:
            loop.close()

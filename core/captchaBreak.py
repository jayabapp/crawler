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
import numpy as np
import random

app = Flask(__name__)

_smsQueue = queue.Queue()
_serverStarted = False
_serverLock = threading.Lock()


def downloadImages(bg_url, piece_url):

    bg = requests.get(bg_url).content
    piece = requests.get(piece_url).content

    with open("bg.png", "wb") as f:
        f.write(bg)

    with open("piece.png", "wb") as f:
        f.write(piece)


def findPuzzleX():

    bg = cv2.imread("bg.png")
    piece = cv2.imread("piece.png")

    bg_gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)
    piece_gray = cv2.cvtColor(piece, cv2.COLOR_BGR2GRAY)

    # edge detect
    bg_edge = cv2.Canny(bg_gray, 100, 200)
    piece_edge = cv2.Canny(piece_gray, 100, 200)

    # remove transparent borders
    _, thresh = cv2.threshold(piece_edge, 50, 255, cv2.THRESH_BINARY)

    coords = cv2.findNonZero(thresh)

    x, y, w, h = cv2.boundingRect(coords)

    cropped_piece = piece_edge[y : y + h, x : x + w]

    result = cv2.matchTemplate(bg_edge, cropped_piece, cv2.TM_CCOEFF_NORMED)

    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    final_x = max_loc[0]

    print("MATCH X:", final_x)
    print("CONFIDENCE:", max_val)

    return final_x


def humanDrag(page, slider, distance):

    box = slider.bounding_box()

    start_x = box["x"] + box["width"] / 2
    start_y = box["y"] + box["height"] / 2

    page.mouse.move(start_x, start_y)

    time.sleep(random.uniform(0.2, 0.5))

    page.mouse.down()

    current = 0

    while current < distance:

        move = random.randint(3, 8)

        current += move

        if current > distance:
            current = distance

        jitter_y = random.randint(-1, 1)

        page.mouse.move(start_x + current, start_y + jitter_y)

        time.sleep(random.uniform(0.01, 0.03))

    time.sleep(random.uniform(0.1, 0.3))

    page.mouse.up()


def solveCaptcha(token):

    try:

        with sync_playwright() as p:

            browser = p.chromium.launch(
                headless=True,
                executable_path="/usr/bin/chromium",
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            context = browser.new_context(
                viewport={"width": 1400, "height": 900},
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="fa-IR",
            )

            page = context.new_page()

            url = f"https://divar.ir/{token}"

            print("OPEN:", url)

            page.goto(url, wait_until="domcontentloaded")

            # صبر برای لود کامل صفحه
            page.wait_for_timeout(3000)

            print("CLICK CONTACT BUTTON")

            # کلیک روی اطلاعات تماس
            contact_btn = page.get_by_text("اطلاعات تماس")
            contact_btn.click()
            # contact_btn = page.locator("button.post-actions__get-contact")

            # contact_btn.wait_for(timeout=10000)

            # contact_btn.scroll_into_view_if_needed()

            # page.wait_for_timeout(1000)

            # contact_btn.click(delay=200)

            print("WAIT CAPTCHA MODAL")

            # صبر تا کپچا ظاهر شود
            page.wait_for_selector(".arc-puzzle", timeout=15000)

            page.wait_for_timeout(2000)

            print("CAPTCHA OPENED")

            # گرفتن لینک عکس‌ها
            bg_url = page.locator(".arc-puzzle img").nth(0).get_attribute("src")

            piece_url = page.locator("img.puzzle").get_attribute("src")

            print("BG:", bg_url)
            print("PIECE:", piece_url)

            if not bg_url or not piece_url:
                raise Exception("Captcha images not found")

            # دانلود عکس‌ها
            downloadImages(bg_url, piece_url)

            # پیدا کردن x
            x = findPuzzleX()

            print("RAW X:", x)

            # عرض نمایش کپچا
            # display_width = 260
            captcha_box = page.locator(".arc-puzzle").bounding_box()
            display_width = captcha_box["width"]

            # عرض واقعی عکس
            bg_img = cv2.imread("bg.png")

            real_width = bg_img.shape[1]

            scale = display_width / real_width

            # distance = x * scale
            distance = (x * display_width / real_width) - 6

            # correction
            distance -= 6

            print("FINAL DISTANCE:", distance)

            # slider
            # slider = page.locator(".draggable")
            slider = page.locator('[role="slider"]')

            slider.wait_for(timeout=10000)

            print("DRAGGING...")

            humanDrag(page, slider, distance)

            print("WAIT RESULT")

            # صبر برای verify شدن
            page.wait_for_timeout(5000)

            # چک موفقیت
            if page.locator(".arc-puzzle").count() == 0:
                print("CAPTCHA SOLVED")
            else:
                print("CAPTCHA MAYBE FAILED")

            logging.info("Captcha done!")

            browser.close()

            return True

    except Exception as e:

        logging.error(f"Solve captcha failed: {e}")

        return False


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
        r"([0-9]{6})",
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

    print("NEW SMS")
    print("FROM:", sender)
    print("TEXT:", msg)
    print("CODE:", code)
    print("-" * 30)

    logging.info(f"New SMS received. sender={sender}, code={code}")

    if code:
        _smsQueue.put(
            {
                "sender": sender,
                "message": msg,
                "code": code,
                "received_at": time.time(),
            }
        )

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


def getSmsCode(timeout=None):

    startSmsServer()

    if timeout is None:
        timeout = int(os.getenv("SMS_CODE_TIMEOUT", "300"))

    logging.info(f"Waiting for SMS code for {timeout} seconds...")

    try:
        item = _smsQueue.get(timeout=timeout)
        code = item.get("code")

        print("OTP CODE:", code)
        logging.info(f"OTP code received: {code}")

        return code

    except queue.Empty:
        logging.warning("SMS code timeout.")
        return None


def sendSmsCode(session, token, res, otp):
    def findValueByKey(data, targetKeys):
        if isinstance(data, dict):
            for key, value in data.items():
                if key in targetKeys and value:
                    return value

                foundValue = findValueByKey(value, targetKeys)

                if foundValue:
                    return foundValue

        elif isinstance(data, list):
            for item in data:
                foundValue = findValueByKey(item, targetKeys)

                if foundValue:
                    return foundValue

        return None

    contactToken = findValueByKey(
        res,
        {
            "contact_token",
            "contactToken",
            "contactTokenV2",
        },
    )

    if not contactToken:
        logging.warning(
            f"OTP solved request skipped for token {token}: contact_token not found."
        )
        return {
            "sent": False,
            "status_code": None,
            "response": None,
            "error": "contact_token_not_found",
        }

    url = "https://api.divar.ir/v8/postcontact/hip/otp-solved"

    payload = {
        "contact_token": contactToken,
        "otp": str(otp),
    }

    try:
        refreshDynamicHeaders(session)

        response = session.post(
            url,
            json=payload,
            timeout=(5, 10),
        )

        if response.status_code == 200:
            return response.json()

        logging.warning(
            f"otp-solved request failed. "
            f"status_code={response.status_code}, response={response.text[:300]}"
        )

    except requests.exceptions.RequestException as e:
        logging.warning(f"otp-solved request error: {e}")


def captchaBreakMain(session, res, token=None):
    logging.info("Start breake captcha...")
    try:
        breakCaptcha = solveCaptcha(token)

        if breakCaptcha:
            startSmsServer()

            code = getSmsCode()

            if code:
                logging.info("captchaBreakMain received SMS code.")
                sendSmsCode(session, token, res, code)
            else:
                logging.warning("captchaBreakMain did not receive SMS code.")

            return True
        return False
    except Exception as e:
        print(f"Captcha breaking failed. Error: {e}")
        return False

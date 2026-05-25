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
                page.locator("text=کد تایید").count() > 0
                or page.locator("input[type='tel']").count() > 0
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

        if not bg_url or not piece_url:

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
# ************ SMS PART ************
# -----------------------------------------


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


def submitOtpWithPlaywright(page, otpCode):

    try:

        logging.info(f"[otp] submitting otp: {otpCode}")

        otp_input = page.locator("input[name='otp']").first

        otp_input.wait_for(
            state="visible",
            timeout=30000,
        )

        page.wait_for_timeout(random.randint(1200, 2200))

        otp_input.click()

        page.wait_for_timeout(random.randint(150, 350))

        otp_input.fill("")

        page.wait_for_timeout(random.randint(100, 250))

        otp_input.type(
            str(otpCode),
            delay=random.randint(80, 160),
        )

        logging.info("[otp] otp typed")

        # مطمئن شو کامل تایپ شده
        wait_start = time.time()

        while True:

            current_value = otp_input.input_value()

            if current_value == str(otpCode):
                break

            if time.time() - wait_start > 10:
                raise Exception("otp_input_value_not_set")

            page.wait_for_timeout(200)

        # -----------------------------
        # AUTO SUBMIT CHECK
        # -----------------------------

        page.wait_for_timeout(5000)

        if page.locator("a[href^='tel:']").count() > 0:

            logging.info("[otp] auto submit success")

            return {
                "ok": True,
                "status": "success",
            }

        result = detectContactResult(
            page,
            timeout=5000,
        )

        if result == "contact_opened":

            logging.info("[otp] auto submit success")

            return {
                "ok": True,
                "status": "success",
            }

        # -----------------------------
        # MANUAL SUBMIT BUTTON
        # -----------------------------

        submit_btn = page.locator("button:has-text('ثبت کد امنیتی')").first

        if submit_btn.count() > 0:

            logging.info("[otp] submit button exists")

            try:

                submit_btn.wait_for(
                    state="visible",
                    timeout=5000,
                )

                wait_start = time.time()

                while submit_btn.is_disabled():

                    if time.time() - wait_start > 10:
                        break

                    page.wait_for_timeout(300)

                if submit_btn.is_enabled():

                    page.wait_for_timeout(random.randint(300, 800))

                    submit_btn.click()

                    logging.info("[otp] submit clicked")

            except Exception as e:

                logging.warning(f"[otp] submit button flow failed: {e}")

        else:

            logging.info("[otp] submit button not present, assuming auto submit flow")

        # -----------------------------
        # FINAL RESULT CHECK
        # -----------------------------

        page.wait_for_timeout(4000)

        if page.locator("a[href^='tel:']").count() > 0:

            logging.info("[otp] success")

            return {
                "ok": True,
                "status": "success",
            }

        invalid_texts = [
            "نامعتبر",
            "اشتباه",
            "کد صحیح نیست",
        ]

        for txt in invalid_texts:

            if page.locator(f"text={txt}").count() > 0:

                logging.warning("[otp] invalid otp")

                return {
                    "ok": False,
                    "status": "invalid_otp",
                }

        result = detectContactResult(
            page,
            timeout=15000,
        )

        logging.info(f"[otp] result={result}")

        if result == "contact_opened":

            return {
                "ok": True,
                "status": "success",
            }

        if result == "error_or_limit":

            return {
                "ok": False,
                "status": "blocked",
            }

        return {
            "ok": False,
            "status": "unknown",
        }

    except Exception as e:

        logging.exception(f"[otp] submit failed: {e}")

        return {
            "ok": False,
            "status": "exception",
            "reason": str(e),
        }


def captchaBreakMain(session, res, token=None):

    logging.info("Start contact challenge check...")

    otp_result_holder = {
        "code": None,
    }

    otp_thread_error = {
        "error": None,
    }

    captcha_result = {}

    def otpListener():

        try:

            code = getSmsCode(timeout=300)

            otp_result_holder["code"] = code

            if code:

                logging.info(f"[sms] OTP captured early: {code}")

        except Exception as e:

            otp_thread_error["error"] = str(e)

            logging.warning(f"[sms] listener failed: {e}")

    try:

        # start sms listener BEFORE captcha
        sms_thread = threading.Thread(
            target=otpListener,
            daemon=True,
        )

        sms_thread.start()

        logging.info("[sms] listener started before captcha")

        # solve captcha
        captcha_result = solveCaptcha(token)

        status = captcha_result.get("status")

        reason = captcha_result.get("reason")

        extra = captcha_result.get("extra", {})

        logging.info(
            f"[captchaBreakMain] token={token}, "
            f"status={status}, "
            f"reason={reason}"
        )

        # success
        if status == "success":

            logging.info(f"CAPTCHA solved successfully for token {token}")

            wait_start = time.time()

            while not otp_result_holder["code"]:

                if time.time() - wait_start > 30:
                    break

                time.sleep(0.5)

            otp = otp_result_holder["code"]

            if not otp:

                logging.warning(f"[sms] OTP not received for token {token}")

                return {
                    "ok": False,
                    "status": "otp_timeout",
                    "reason": "sms_code_not_received",
                    "token": token,
                }

            logging.info(f"[sms] OTP received for token {token}: {otp}")

            page = captcha_result.get("page")

            if not page:

                return {
                    "ok": False,
                    "status": "page_missing",
                    "token": token,
                }

            otp_response = submitOtpWithPlaywright(
                page=page,
                otpCode=otp,
            )

            if not otp_response or not otp_response.get("ok"):

                return {
                    "ok": False,
                    "status": "otp_submit_failed",
                    "reason": (
                        otp_response.get("status")
                        if isinstance(otp_response, dict)
                        else "otp_response_empty"
                    ),
                    "token": token,
                    "otp": otp,
                    "otp_result": otp_response,
                }

            return {
                "ok": True,
                "status": "success",
                "reason": reason,
                "token": token,
                "otp": otp,
                "otp_result": otp_response,
            }

        # blocked
        if status == "blocked":

            return {
                "ok": False,
                "status": "blocked",
                "reason": reason,
                "token": token,
                "extra": extra,
            }

        # other failures
        return {
            "ok": False,
            "status": status or "failed",
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

        try:

            page = captcha_result.get("page")

            if page:
                page.close()

        except Exception:
            pass

        try:

            context = captcha_result.get("context")

            if context:
                context.close()

        except Exception:
            pass

        try:

            playwright = captcha_result.get("playwright")

            if playwright:
                playwright.stop()

        except Exception:
            pass

import logging
import os
import threading
import time

captcha_event = threading.Event()
captcha_until = 0
captcha_lock = threading.Lock()


def activateCaptchaPause(categoryName=None, token=None):
    global captcha_until

    cooldownSeconds = int(os.getenv("CONTACT_CAPTCHA_COOLDOWN_SECONDS", "3600"))

    with captcha_lock:
        captcha_until = max(captcha_until, time.time() + cooldownSeconds)
        captcha_event.set()

    logging.error(
        f"Global CAPTCHA pause activated for {cooldownSeconds} seconds. "
        f"category={categoryName}, token={token}"
    )


def waitIfCaptchaPause():
    global captcha_until

    while captcha_event.is_set():
        remaining = int(captcha_until - time.time())

        if remaining <= 0:
            with captcha_lock:
                if time.time() >= captcha_until:
                    captcha_event.clear()
                    captcha_until = 0
                    logging.info("Global CAPTCHA pause finished.")
                    return

        logging.warning(
            f"Global CAPTCHA pause is active. Waiting {max(remaining, 1)} seconds..."
        )

        time.sleep(min(max(remaining, 1), 60))

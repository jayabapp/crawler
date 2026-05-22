import logging
import os
import time

import requests

_last_telegram_sent_at = 0
proxies = {
    "http": "socks5h://127.0.0.1:10808",
    "https": "socks5h://127.0.0.1:10808",
}


def sendTelegram(message, throttleSeconds=300):
    """
    برای جلوگیری از اسپم، پیش‌فرض هر ۵ دقیقه فقط یک پیام کپچا می‌فرستد.
    """
    global _last_telegram_sent_at

    botToken = os.getenv("TELEGRAM_BOT_TOKEN")
    chatId = os.getenv("TELEGRAM_CHAT_ID")

    if not botToken or not chatId:
        logging.warning("Telegram env vars are not set.")
        return False

    now = time.time()

    if now - _last_telegram_sent_at < throttleSeconds:
        logging.info("Telegram notification skipped because of throttle.")
        return False

    url = f"https://api.telegram.org/bot{botToken}/sendMessage"

    try:
        response = requests.post(
            url,
            json={
                "chat_id": chatId,
                "text": message,
                "parse_mode": "HTML",
            },
            timeout=10,
            proxies=proxies,
        )

        if response.status_code != 200:
            logging.warning(f"Telegram notification failed: {response.text}")
            return False

        _last_telegram_sent_at = now
        return True

    except Exception as e:
        logging.warning(f"Telegram notification error: {e}")
        return False

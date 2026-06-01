import logging
import os
import re
import time

import requests

_last_telegram_sent_at = 0
_last_update_id = None

PLACEHOLDER_VALUES = {
    "telegram bot token",
    "telegram_bot_token",
    "your telegram bot token",
    "your_bot_token",
    "bot token",
    "token",
    "telegram chat id",
    "your_chat_id",
    "chat id",
}


def _clean(value):
    return (value or "").strip()


def _is_placeholder(value):
    value = _clean(value)
    if not value:
        return True
    return value.lower() in PLACEHOLDER_VALUES or " " in value


def _telegram_config():
    botToken = _clean(os.getenv("TELEGRAM_BOT_TOKEN"))
    chatId = _clean(os.getenv("TELEGRAM_CHAT_ID"))

    if _is_placeholder(botToken) or _is_placeholder(chatId):
        logging.warning(
            "Telegram is not configured correctly. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."
        )
        return None, None

    return botToken, chatId


def sendTelegram(message, throttleSeconds=300):
    """
    Send a Telegram message. Set throttleSeconds=0 for important interactive messages.
    """
    global _last_telegram_sent_at

    botToken, chatId = _telegram_config()
    if not botToken or not chatId:
        return False

    now = time.time()

    if throttleSeconds and now - _last_telegram_sent_at < throttleSeconds:
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
                "disable_web_page_preview": True,
            },
            timeout=10,
        )

        if response.status_code != 200:
            logging.warning(f"Telegram notification failed: {response.text}")
            return False

        _last_telegram_sent_at = now
        return True

    except Exception as e:
        logging.warning(f"Telegram notification error: {e}")
        return False


def _extract_otp(text):
    if not text:
        return None

    match = re.search(r"(?<!\d)(\d{4,8})(?!\d)", str(text))
    return match.group(1) if match else None


def _get_latest_update_offset(botToken):
    """Return next offset so old Telegram messages are ignored."""
    global _last_update_id

    if _last_update_id is not None:
        return _last_update_id + 1

    try:
        url = f"https://api.telegram.org/bot{botToken}/getUpdates"
        response = requests.get(url, params={"timeout": 1}, timeout=5)
        if response.status_code != 200:
            logging.warning(f"Telegram getUpdates failed: {response.text}")
            return None

        updates = response.json().get("result", [])
        if updates:
            _last_update_id = max(item.get("update_id", 0) for item in updates)
            return _last_update_id + 1

    except Exception as e:
        logging.warning(f"Telegram getUpdates init error: {e}")

    return None


def waitTelegramOtp(token=None, timeout=180, prompt=True):
    """
    Ask the configured Telegram chat for an OTP and wait for a 4-8 digit reply.
    Only messages from TELEGRAM_CHAT_ID are accepted.
    """
    global _last_update_id

    botToken, chatId = _telegram_config()
    if not botToken or not chatId:
        return None

    offset = _get_latest_update_offset(botToken)

    if prompt:
        token_line = f"\nToken: <code>{token}</code>" if token else ""
        sendTelegram(
            "⚠️ OTP به‌صورت خودکار دریافت نشد.\n"
            f"لطفاً فقط کد OTP را همینجا در تلگرام بفرست.{token_line}",
            throttleSeconds=0,
        )

    deadline = time.time() + timeout
    get_url = f"https://api.telegram.org/bot{botToken}/getUpdates"

    while time.time() < deadline:
        try:
            response = requests.get(
                get_url,
                params={"timeout": 10, "offset": offset},
                timeout=15,
            )

            if response.status_code != 200:
                logging.warning(f"Telegram getUpdates failed: {response.text}")
                time.sleep(3)
                continue

            updates = response.json().get("result", [])

            for update in updates:
                update_id = update.get("update_id")
                if update_id is not None:
                    _last_update_id = update_id
                    offset = update_id + 1

                message = update.get("message") or update.get("edited_message") or {}
                chat = message.get("chat") or {}
                incoming_chat_id = str(chat.get("id", ""))

                if incoming_chat_id != str(chatId):
                    continue

                text = message.get("text") or message.get("caption") or ""
                code = _extract_otp(text)

                if code:
                    logging.info("Manual OTP received from Telegram.")
                    return code

        except Exception as e:
            logging.warning(f"Telegram OTP polling error: {e}")
            time.sleep(3)

    logging.warning("Manual Telegram OTP timeout.")
    return None

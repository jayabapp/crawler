import random

SCREEN_SIZES = [
    "1920x1080",
    "1366x768",
    "1536x864",
    "1440x900",
    "1600x900",
]


USER_AGENTS = [
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
]


def getRandomScreenSize():
    return random.choice(SCREEN_SIZES)


def getRandomUserAgent():
    return random.choice(USER_AGENTS)


def buildHeaders(referer="https://divar.ir/"):
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
        "content-type": "application/json",
        "origin": "https://divar.ir",
        "referer": referer or "https://divar.ir/",
        "priority": "u=1, i",
        "sec-ch-ua": '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": getRandomUserAgent(),
        "x-render-type": "CSR",
        "x-standard-divar-error": "true",
        "x-screen-size": getRandomScreenSize(),
    }


headers = buildHeaders()

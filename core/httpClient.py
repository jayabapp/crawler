import logging
import random
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.header import buildHeaders, getRandomScreenSize, getRandomUserAgent


def randomSleep(minSec=2, maxSec=6):
    time.sleep(random.uniform(minSec, maxSec))


def createSession(
    referer="https://divar.ir/",
    allowedMethods=None,
    totalRetries=3,
    backoffFactor=2,
    poolConnections=10,
    poolMaxSize=10,
):
    if allowedMethods is None:
        allowedMethods = ["GET", "POST"]

    session = requests.Session()

    retryStrategy = Retry(
        total=totalRetries,
        backoff_factor=backoffFactor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=allowedMethods,
    )

    adapter = HTTPAdapter(
        max_retries=retryStrategy,
        pool_connections=poolConnections,
        pool_maxsize=poolMaxSize,
    )

    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update(buildHeaders(referer))

    return session


def refreshDynamicHeaders(session, referer=None):
    dynamicHeaders = {
        "x-screen-size": getRandomScreenSize(),
        "user-agent": getRandomUserAgent(),
    }

    if referer:
        dynamicHeaders["referer"] = referer

    session.headers.update(dynamicHeaders)


def safeRequest(
    session,
    method,
    url,
    maxRetries=3,
    timeout=(5, 20),
    rateLimitSleepRange=(900, 1800),
    baseBackoffRange=(60, 120),
    **kwargs,
):
    retries = 0
    baseBackoffTime = random.randint(*baseBackoffRange)

    while retries < maxRetries:
        try:
            refreshDynamicHeaders(session)

            response = session.request(
                method=method,
                url=url,
                timeout=timeout,
                **kwargs,
            )

            if response.status_code == 429:
                sleepTime = random.uniform(*rateLimitSleepRange)
                logging.warning(
                    f"429 rate limit detected. Sleeping {int(sleepTime)} seconds..."
                )
                time.sleep(sleepTime)
                retries += 1
                continue

            return response

        except requests.exceptions.RequestException as e:
            retries += 1

            waitTime = (baseBackoffTime * (2**retries)) + random.uniform(5, 30)

            logging.warning(
                f"Request failed: {e}. Retrying in {int(waitTime)} seconds "
                f"({retries}/{maxRetries})..."
            )

            time.sleep(waitTime)

    return None

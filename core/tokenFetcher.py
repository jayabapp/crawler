import logging
import random
import time
import traceback

from core.adFetcher import processAds
from core.httpClient import createSession, randomSleep, refreshDynamicHeaders

visitedTokensByCategory = {}


def getConfigValue(configModule, camelName, upperName, default=None):
    if hasattr(configModule, camelName):
        return getattr(configModule, camelName)

    if hasattr(configModule, upperName):
        return getattr(configModule, upperName)

    return default


def buildSearchPayload(categoryConfig, paginationData=None):
    divarCategory = getConfigValue(
        categoryConfig,
        "divarCategory",
        "DIVAR_CATEGORY",
    )

    cityIds = getConfigValue(
        categoryConfig,
        "cityIds",
        "CITY_IDS",
        ["715"],
    )

    sortValue = getConfigValue(
        categoryConfig,
        "sortValue",
        "SORT_VALUE",
        "sort_date",
    )

    payload = {
        "city_ids": cityIds,
        "source_view": "CATEGORY",
        "disable_recommendation": False,
        "map_state": {"camera_info": {"bbox": {}}},
        "search_data": {
            "form_data": {
                "data": {
                    "category": {
                        "str": {
                            "value": divarCategory,
                        }
                    }
                }
            },
            "server_payload": {
                "@type": "type.googleapis.com/widgets.SearchData.ServerPayload",
                "additional_form_data": {
                    "data": {
                        "sort": {
                            "str": {
                                "value": sortValue,
                            }
                        }
                    }
                },
            },
        },
        "previous_place_ids": [],
    }

    if paginationData:
        payload["pagination_data"] = paginationData

    return payload


def extractTokens(responseData):
    try:
        return responseData["action_log"]["server_side_info"]["info"]["tokens"]
    except (KeyError, TypeError):
        return []


def getNewTokens(categoryName, tokens):
    if categoryName not in visitedTokensByCategory:
        visitedTokensByCategory[categoryName] = set()

    visitedTokens = visitedTokensByCategory[categoryName]

    newTokens = []

    for token in tokens:
        if token in visitedTokens:
            continue

        visitedTokens.add(token)
        newTokens.append(token)

    return newTokens


def fetchTokenPage(session, payload):
    url = "https://api.divar.ir/v8/postlist/w/search"

    randomSleep(2, 6)
    refreshDynamicHeaders(session)

    response = session.post(
        url,
        json=payload,
        timeout=(5, 15),
    )

    return response


def fetchTokens(
    conn,
    categoryName,
    categoryConfig,
    extractorModule,
    filtersModule,
    repositoryModule,
):
    referer = getConfigValue(
        categoryConfig,
        "referer",
        "REFERER",
        "https://divar.ir/",
    )

    session = createSession(
        referer=referer,
        allowedMethods=["GET", "POST"],
    )

    try:
        logging.info(f"Start fetching advertisement tokens for {categoryName}...")

        session.get("https://divar.ir/", timeout=10)

        paginationData = None

        # تعداد دفعاتی که توکن جدید پیدا نشده
        noNewTokenCount = 0

        while True:
            try:
                payload = buildSearchPayload(
                    categoryConfig=categoryConfig,
                    paginationData=paginationData,
                )

                response = fetchTokenPage(session, payload)

                if response.status_code == 429:
                    sleepTime = random.uniform(900, 1800)

                    logging.warning(
                        f"{categoryName} token fetch rate limited. "
                        f"Sleeping {int(sleepTime)} seconds..."
                    )

                    time.sleep(sleepTime)
                    continue

                if response.status_code != 200:
                    logging.warning(
                        f"{categoryName} token fetch bad response: {response.status_code}"
                    )

                    randomSleep(3, 9)
                    continue

                data = response.json()

                tokens = extractTokens(data)
                if not tokens:
                    logging.info(
                        f"{categoryName}: empty token page. Resetting pagination."
                    )
                    paginationData = None
                    noNewTokenCount += 1
                    randomSleep(20, 60)
                    continue

                paginationData = data.get("pagination_data")

                newTokens = getNewTokens(categoryName, tokens)

                if newTokens:
                    noNewTokenCount = 0

                    logging.info(f"{categoryName}: {len(newTokens)} new tokens found.")

                    processAds(
                        conn=conn,
                        tokens=newTokens,
                        categoryName=categoryName,
                        categoryConfig=categoryConfig,
                        extractorModule=extractorModule,
                        filtersModule=filtersModule,
                        repositoryModule=repositoryModule,
                    )

                else:
                    noNewTokenCount += 1

                    logging.info(
                        f"{categoryName}: no new tokens found "
                        f"({noNewTokenCount}/2)."
                    )

                    # اگر دو بار پشت سر هم توکن جدید پیدا نشد
                    # pagination ریست میشه و دوباره از اول شروع میکنه
                    if noNewTokenCount >= 2:
                        logging.info(
                            f"{categoryName}: restarting pagination from beginning and clearing visited tokens..."
                        )

                        paginationData = None
                        noNewTokenCount = 0

                        # مهم:
                        # tokenهای seen شده را پاک می‌کنیم تا صفحه اول دوباره بررسی شود.
                        # آگهی‌هایی که قبلاً ذخیره شده‌اند، در processAds با filterTokens از دیتابیس حذف می‌شوند.
                        visitedTokensByCategory[categoryName] = set()

                        randomSleep(20, 60)
                        continue

                waitTime = random.uniform(3, 8)

                logging.info(
                    f"{categoryName}: waiting {int(waitTime)} seconds "
                    f"before next token page..."
                )

                time.sleep(waitTime)

            except Exception as loopError:
                logging.error(f"{categoryName} token loop error: {loopError}")
                logging.error(traceback.format_exc())

                sleepTime = random.uniform(60, 180)

                logging.info(
                    f"{categoryName}: sleeping {int(sleepTime)} seconds "
                    f"after token loop error..."
                )

                time.sleep(sleepTime)

    except Exception as e:
        logging.error(f"{categoryName} fetchAds failed: {e}")
        logging.error(traceback.format_exc())
        raise

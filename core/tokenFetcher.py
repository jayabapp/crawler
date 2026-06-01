import hashlib
import json
import logging
import os
import random
import time
import traceback

from core.adFetcher import processAds
from core.httpClient import createSession, randomSleep, refreshDynamicHeaders

visitedTokensByCategory = {}

MAX_VISITED_TOKENS_PER_CATEGORY = int(
    os.getenv("MAX_VISITED_TOKENS_PER_CATEGORY", "5000")
)

STATE_DIR = os.getenv("PAGINATION_STATE_DIR", "state")


def savePaginationState(categoryName, workerIndex, workerCount, state):
    os.makedirs(STATE_DIR, exist_ok=True)

    path = os.path.join(
        STATE_DIR,
        f"pagination_{categoryName}_{workerIndex}_of_{workerCount}.json",
    )

    tmpPath = f"{path}.tmp"

    try:
        with open(tmpPath, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)

        os.replace(tmpPath, path)

        logging.info(
            f"{categoryName}: pagination state saved for "
            f"worker {workerIndex}/{workerCount}."
        )

    except Exception as e:
        logging.warning(f"{categoryName}: failed to save pagination state: {e}")


def loadPaginationState(categoryName, workerIndex, workerCount):
    path = os.path.join(
        STATE_DIR,
        f"pagination_{categoryName}_{workerIndex}_of_{workerCount}.json",
    )

    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)

        if not isinstance(state, dict):
            return {}

        logging.info(
            f"{categoryName}: pagination state loaded for "
            f"worker {workerIndex}/{workerCount}."
        )

        return state

    except Exception as e:
        logging.warning(f"{categoryName}: failed to load pagination state: {e}")
        return {}


def getConfigValue(configModule, camelName, upperName, default=None):
    if hasattr(configModule, camelName):
        return getattr(configModule, camelName)

    if hasattr(configModule, upperName):
        return getattr(configModule, upperName)

    return default


def getWorkerCount():
    try:
        return max(1, int(os.getenv("WORKER_COUNT", "1")))
    except ValueError:
        return 1


def getWorkerIndex():
    try:
        return max(0, int(os.getenv("WORKER_INDEX", "0")))
    except ValueError:
        return 0


def shouldProcessToken(token):
    workerCount = getWorkerCount()
    workerIndex = getWorkerIndex()

    if workerCount <= 1:
        return True

    tokenHash = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)

    return tokenHash % workerCount == workerIndex


def getVisitedKey(categoryName):
    workerCount = getWorkerCount()
    workerIndex = getWorkerIndex()

    return f"{categoryName}:worker:{workerIndex}:of:{workerCount}"


def trimVisitedTokens(visitedTokens):
    if len(visitedTokens) <= MAX_VISITED_TOKENS_PER_CATEGORY:
        return visitedTokens

    keepCount = max(100, MAX_VISITED_TOKENS_PER_CATEGORY // 2)

    trimmedTokens = set(list(visitedTokens)[-keepCount:])

    logging.info(
        f"Visited token cache trimmed from {len(visitedTokens)} "
        f"to {len(trimmedTokens)} tokens."
    )

    return trimmedTokens


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
        ["905", "888", "899"],
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
        tokens = responseData["action_log"]["server_side_info"]["info"]["tokens"]

        if not isinstance(tokens, list):
            return []

        return [token for token in tokens if token]

    except (KeyError, TypeError):
        return []


def getAssignedTokens(tokens):
    assignedTokens = []
    seenTokens = set()

    for token in tokens:
        if token in seenTokens:
            continue

        seenTokens.add(token)

        if shouldProcessToken(token):
            assignedTokens.append(token)

    return assignedTokens


def getNewTokens(categoryName, tokens):
    visitedKey = getVisitedKey(categoryName)

    if visitedKey not in visitedTokensByCategory:
        visitedTokensByCategory[visitedKey] = set()

    visitedTokens = visitedTokensByCategory[visitedKey]
    newTokens = []

    for token in tokens:
        if token in visitedTokens:
            continue

        visitedTokens.add(token)
        newTokens.append(token)

    visitedTokensByCategory[visitedKey] = trimVisitedTokens(visitedTokens)

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
    workerIndex = getWorkerIndex()
    workerCount = getWorkerCount()

    paginationState = loadPaginationState(categoryName, workerIndex, workerCount)

    newestPaginationData = None
    backlogPaginationData = paginationState.get("backlogPaginationData")
    loopCount = int(paginationState.get("loopCount") or 0)

    noNewTokenCount = 0
    emptyTokenPageCount = 0
    newestPageDepth = 0

    NEWEST_CHECK_EVERY_N_LOOPS = int(os.getenv("NEWEST_CHECK_EVERY_N_LOOPS", "3"))

    NEWEST_MAX_PAGES = int(os.getenv("NEWEST_MAX_PAGES", "1"))

    NO_NEW_TOKEN_SLEEP_THRESHOLD = int(os.getenv("NO_NEW_TOKEN_SLEEP_THRESHOLD", "20"))

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

        if backlogPaginationData:
            logging.info(
                f"{categoryName}: restored backlog pagination from saved state."
            )
        else:
            logging.info(
                f"{categoryName}: no saved backlog pagination. "
                f"Backlog will start from beginning."
            )

        try:
            session.get("https://divar.ir/", timeout=10)
        except Exception as e:
            logging.warning(
                f"{categoryName}: initial divar homepage request failed: {e}"
            )

        while True:
            try:
                loopCount += 1

                shouldCheckNewest = (
                    loopCount == 1 or loopCount % NEWEST_CHECK_EVERY_N_LOOPS == 0
                )

                if shouldCheckNewest:
                    mode = "newest"

                    if newestPageDepth >= NEWEST_MAX_PAGES:
                        newestPaginationData = None
                        newestPageDepth = 0

                    currentPaginationData = newestPaginationData

                else:
                    mode = "backlog"
                    currentPaginationData = backlogPaginationData

                logging.info(
                    f"{categoryName}: fetching token page. "
                    f"mode={mode}, loopCount={loopCount}, "
                    f"hasPagination={bool(currentPaginationData)}."
                )

                payload = buildSearchPayload(
                    categoryConfig=categoryConfig,
                    paginationData=currentPaginationData,
                )

                response = fetchTokenPage(session, payload)

                if response.status_code == 429:
                    savePaginationState(
                        categoryName,
                        workerIndex,
                        workerCount,
                        {
                            "backlogPaginationData": backlogPaginationData,
                            "loopCount": loopCount,
                        },
                    )

                    sleepTime = random.uniform(900, 1800)

                    logging.warning(
                        f"{categoryName} token fetch rate limited. "
                        f"Sleeping {int(sleepTime)} seconds..."
                    )

                    time.sleep(sleepTime)
                    continue

                if response.status_code != 200:
                    logging.warning(
                        f"{categoryName} token fetch bad response: "
                        f"{response.status_code}, body={response.text[:300]}"
                    )

                    randomSleep(10, 30)
                    continue

                data = response.json()
                tokens = extractTokens(data)

                if not tokens:
                    emptyTokenPageCount += 1

                    logging.info(
                        f"{categoryName}: empty token page in mode={mode} "
                        f"({emptyTokenPageCount}/5)."
                    )

                    if mode == "newest":
                        newestPaginationData = None
                        newestPageDepth = 0
                    else:
                        backlogPaginationData = None

                        savePaginationState(
                            categoryName,
                            workerIndex,
                            workerCount,
                            {
                                "backlogPaginationData": backlogPaginationData,
                                "loopCount": loopCount,
                            },
                        )

                    if emptyTokenPageCount >= 5:
                        sleepTime = random.uniform(120, 300)

                        logging.info(
                            f"{categoryName}: too many empty token pages. "
                            f"Sleeping {int(sleepTime)} seconds..."
                        )

                        emptyTokenPageCount = 0
                        time.sleep(sleepTime)
                    else:
                        randomSleep(20, 60)

                    continue

                emptyTokenPageCount = 0
                nextPaginationData = data.get("pagination_data")

                if mode == "newest":
                    newestPageDepth += 1

                    if newestPageDepth >= NEWEST_MAX_PAGES:
                        newestPaginationData = None
                        newestPageDepth = 0
                    else:
                        newestPaginationData = nextPaginationData

                else:
                    backlogPaginationData = nextPaginationData

                    if not backlogPaginationData:
                        logging.info(
                            f"{categoryName}: backlog pagination ended. "
                            f"Restarting backlog from beginning."
                        )
                        backlogPaginationData = None

                    savePaginationState(
                        categoryName,
                        workerIndex,
                        workerCount,
                        {
                            "backlogPaginationData": backlogPaginationData,
                            "loopCount": loopCount,
                        },
                    )

                assignedTokens = getAssignedTokens(tokens)

                logging.info(
                    f"{categoryName}: mode={mode}, "
                    f"token page received={len(tokens)}, "
                    f"assigned_to_this_worker={len(assignedTokens)}, "
                    f"newestPageDepth={newestPageDepth}, "
                    f"hasBacklogPagination={bool(backlogPaginationData)}."
                )

                if not assignedTokens:
                    noNewTokenCount += 1

                    logging.info(
                        f"{categoryName}: no assigned tokens on this page "
                        f"({noNewTokenCount}/{NO_NEW_TOKEN_SLEEP_THRESHOLD})."
                    )

                    if noNewTokenCount >= NO_NEW_TOKEN_SLEEP_THRESHOLD:
                        noNewTokenCount = 0

                        sleepTime = random.uniform(60, 180)

                        logging.info(
                            f"{categoryName}: many pages had no assigned tokens. "
                            f"Keeping backlog pagination state. "
                            f"Sleeping {int(sleepTime)} seconds..."
                        )

                        time.sleep(sleepTime)
                        continue

                    waitTime = random.uniform(5, 12)

                    logging.info(
                        f"{categoryName}: waiting {int(waitTime)} seconds "
                        f"before next token page..."
                    )

                    time.sleep(waitTime)
                    continue

                newTokens = getNewTokens(categoryName, assignedTokens)

                if newTokens:
                    noNewTokenCount = 0

                    logging.info(
                        f"{categoryName}: {len(newTokens)} new assigned tokens found."
                    )

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
                        f"{categoryName}: no new assigned tokens found "
                        f"({noNewTokenCount}/{NO_NEW_TOKEN_SLEEP_THRESHOLD})."
                    )

                    if noNewTokenCount >= NO_NEW_TOKEN_SLEEP_THRESHOLD:
                        noNewTokenCount = 0

                        sleepTime = random.uniform(120, 300)

                        logging.info(
                            f"{categoryName}: many pages had no new tokens. "
                            f"Keeping backlog pagination state and sleeping "
                            f"{int(sleepTime)} seconds..."
                        )

                        time.sleep(sleepTime)
                        continue

                waitTime = random.uniform(5, 12)

                logging.info(
                    f"{categoryName}: waiting {int(waitTime)} seconds "
                    f"before next token page..."
                )

                time.sleep(waitTime)

            except Exception as loopError:
                logging.error(f"{categoryName} token loop error: {loopError}")
                logging.error(traceback.format_exc())

                savePaginationState(
                    categoryName,
                    workerIndex,
                    workerCount,
                    {
                        "backlogPaginationData": backlogPaginationData,
                        "loopCount": loopCount,
                    },
                )

                sleepTime = random.uniform(60, 180)

                logging.info(
                    f"{categoryName}: sleeping {int(sleepTime)} seconds "
                    f"after token loop error..."
                )

                time.sleep(sleepTime)

    except Exception as e:
        logging.error(f"{categoryName} fetchAds failed: {e}")
        logging.error(traceback.format_exc())

        savePaginationState(
            categoryName,
            workerIndex,
            workerCount,
            {
                "backlogPaginationData": backlogPaginationData,
                "loopCount": loopCount,
            },
        )

        raise

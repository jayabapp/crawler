import datetime
import logging
import os
import random
import re
import threading
import time
import traceback
import requests
import hashlib
from core.contactBrowser import CONTACT_CAPTCHA, getContactSync
from core.notifier import sendTelegram
from core.httpClient import createSession, randomSleep, refreshDynamicHeaders
from core.captchaState import activateCaptchaPause, waitIfCaptchaPause

MAX_RETRIES = 3
BASE_BACKOFF_TIME = random.randint(20, 30)
REQUEST_DELAY = random.randint(20, 30)

CONTACT_REQUEST_LOCK = threading.Lock()
LAST_CONTACT_REQUEST_AT = 0
CONTACT_REQUEST_COUNT = 0


def shouldProcessToken(token):
    workerCount = int(os.getenv("WORKER_COUNT", "1"))
    workerIndex = int(os.getenv("WORKER_INDEX", "0"))

    if workerCount <= 1:
        return True

    tokenHash = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)

    return tokenHash % workerCount == workerIndex


def getConfigValue(configModule, camelName, upperName, default=None):
    if hasattr(configModule, camelName):
        return getattr(configModule, camelName)

    if hasattr(configModule, upperName):
        return getattr(configModule, upperName)

    return default


def getSection(res, sectionName):
    return next(
        (
            section
            for section in res.get("sections", [])
            if section.get("section_name") == sectionName
        ),
        None,
    )


def getSectionWidgets(res, sectionName):
    section = getSection(res, sectionName)

    if not section:
        return None

    return section.get("widgets")


def getMapData(res):
    widgets = getSectionWidgets(res, "MAP")

    if not widgets:
        return None

    return widgets[0].get("data")


def getCoordinates(mapData):
    if not mapData:
        return 0, 0

    try:
        point = mapData["location"]["exact_data"]["point"]
    except KeyError:
        try:
            point = mapData["location"]["fuzzy_data"]["point"]
        except KeyError:
            return 0, 0

    return point.get("latitude", 0), point.get("longitude", 0)


def getTitle(titleSection):
    try:
        return titleSection["widgets"][0]["data"]["title"]
    except (KeyError, IndexError, TypeError):
        return None


def getDescription(descriptionSection):
    try:
        widgets = descriptionSection.get("widgets", [])

        for widget in widgets:
            if widget.get("widget_type") != "DESCRIPTION_ROW":
                continue

            text = widget.get("data", {}).get("text")

            if text and text.strip() and text.strip() != "توضیحات":
                return text.strip()

        return None

    except (KeyError, IndexError, TypeError, AttributeError):
        return None


def cleanPersianDateText(value):
    if value is None:
        return None

    return str(value).replace("،", "").replace(",", "").replace("\u200c", " ").strip()


def getPublishedAt(res):
    try:
        from core.convertTime import convertDate
    except ModuleNotFoundError:
        from core.timeConverter import convertDate

    try:
        seoTitle = res.get("seo", {}).get("title", "")

        if " - " in seoTitle:
            dateText = seoTitle.split(" - ")[1]
            dateText = cleanPersianDateText(dateText)
            return convertDate(dateText)

    except Exception:
        pass

    try:
        titleWidgets = getSectionWidgets(res, "TITLE")

        if not titleWidgets:
            return None

        for widget in titleWidgets:
            if widget.get("widget_type") != "EXPANDABLE_SECTION":
                continue

            widgetList = widget.get("data", {}).get("widget_list", [])

            for childWidget in widgetList:
                if childWidget.get("widget_type") != "DESCRIPTION_ROW":
                    continue

                text = childWidget.get("data", {}).get("text", "")

                for line in text.split("\n"):
                    line = line.strip()

                    if line.startswith("انتشار آگهی:"):
                        dateText = line.replace("انتشار آگهی:", "").strip()
                        dateText = cleanPersianDateText(dateText)
                        return convertDate(dateText)

    except Exception as e:
        logging.warning(f"Could not parse published_at from TITLE section: {e}")

    return None


def getMobile(res, token):
    global LAST_CONTACT_REQUEST_AT
    global CONTACT_REQUEST_COUNT

    waitIfCaptchaPause()

    try:
        contactUuid = res["contact"]["action_log"]["server_side_info"]["info"][
            "contact_uuid"
        ]

        with CONTACT_REQUEST_LOCK:
            minDelay = int(os.getenv("CONTACT_REQUEST_MIN_DELAY", "45"))
            maxExtraDelay = int(os.getenv("CONTACT_REQUEST_MAX_EXTRA_DELAY", "35"))

            elapsed = time.time() - LAST_CONTACT_REQUEST_AT

            if LAST_CONTACT_REQUEST_AT > 0 and elapsed < minDelay:
                sleepTime = (minDelay - elapsed) + random.uniform(0, maxExtraDelay)

                logging.info(
                    f"Waiting {int(sleepTime)} seconds before next contact request..."
                )

                time.sleep(sleepTime)

            CONTACT_REQUEST_COUNT += 1

            contactsBeforeCooldown = int(
                os.getenv("CONTACTS_BEFORE_LONG_COOLDOWN", "12")
            )

            if CONTACT_REQUEST_COUNT % contactsBeforeCooldown == 0:
                cooldownMin = int(os.getenv("CONTACT_LONG_COOLDOWN_MIN", "300"))
                cooldownMax = int(os.getenv("CONTACT_LONG_COOLDOWN_MAX", "700"))

                cooldown = random.uniform(cooldownMin, cooldownMax)

                logging.info(
                    f"Long contact cooldown after {CONTACT_REQUEST_COUNT} requests: "
                    f"{int(cooldown)} seconds..."
                )

                time.sleep(cooldown)

            mobile = getContactSync(token, contactUuid)

            LAST_CONTACT_REQUEST_AT = time.time()

            return mobile

    except Exception as e:
        logging.warning(f"Get contact number failed for token {token}: {e}")
        return None


def validateTableName(tableName):
    if not tableName:
        raise ValueError("tableName is required in category config.")

    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", tableName):
        raise ValueError(f"Invalid tableName: {tableName}")

    return tableName


def filterTokens(cur, tokens, tableName):
    tableName = validateTableName(tableName)

    cur.execute(f'SELECT "token_id" FROM {tableName}')

    existingTokens = {row[0] for row in cur.fetchall()}
    seenTokens = set()
    filteredTokens = []

    for token in tokens:
        if token in existingTokens or token in seenTokens:
            continue

        seenTokens.add(token)
        filteredTokens.append(token)

    return filteredTokens


def isDuplicateAd(cur, tableName, title, description, mobile):
    tableName = validateTableName(tableName)

    cur.execute(
        f"""
        SELECT id
        FROM {tableName}
        WHERE title = %s AND description = %s AND mobile = %s
        LIMIT 1
        """,
        (
            title,
            description,
            mobile,
        ),
    )

    return cur.fetchone() is not None


def normalizeValue(value):
    if isinstance(value, list):
        return "، ".join(str(item) for item in value if item is not None)

    return value


def normalizeData(data):
    return {key: normalizeValue(value) for key, value in data.items()}


def getWebengageValue(webengage, *keys, default=None):
    for key in keys:
        value = webengage.get(key)

        if value is not None:
            return value

    return default


def buildCommonData(
    token,
    res,
    title,
    description,
    mobile,
    latitude,
    longitude,
    categoryName,
):
    webengage = res.get("webengage", {})

    commonData = {
        "token_id": token,
        "city": getWebengageValue(webengage, "city", default=None),
        "title": title,
        "description": description,
        "district": getWebengageValue(webengage, "district", default=None),
        "latitude": latitude,
        "longitude": longitude,
        "mobile": mobile,
        "published_at": getPublishedAt(res),
        "created_at": datetime.datetime.now(),
    }

    if categoryName == "villaRental":
        commonData["rent"] = getWebengageValue(webengage, "rent", "price", default=0)
        commonData["deposit"] = getWebengageValue(
            webengage,
            "credit",
            "deposit",
            default=0,
        )

    elif categoryName == "vehicleRental":
        commonData["rent"] = getWebengageValue(webengage, "price", "rent", default=0)
        commonData["deposit"] = getWebengageValue(
            webengage,
            "credit",
            "deposit",
            default=0,
        )

    elif categoryName == "tourAndCharter":
        commonData["price"] = getWebengageValue(webengage, "price", default=0)

    return commonData


def callInsert(repositoryModule, conn, data, categoryName):
    candidateNames = [
        "insertAd",
        "insertData",
        "insertAdvertisement",
    ]

    if categoryName == "villaRental":
        candidateNames.extend(["insertVillaAd", "advertisementTable"])

    if categoryName == "vehicleRental":
        candidateNames.extend(["insertVehicleAd", "vehicleTable"])

    for functionName in candidateNames:
        insertFunction = getattr(repositoryModule, functionName, None)

        if insertFunction:
            return insertFunction(conn, data)

    raise AttributeError(
        f"No insert function found in repository for {categoryName}. "
        f"Use insertAd(conn, data)."
    )


def fetchAdData(session, token):
    url = f"https://api.divar.ir/v8/posts-v2/web/{token}"
    retries = 0

    while retries < MAX_RETRIES:
        try:
            refreshDynamicHeaders(session)

            response = session.get(
                url,
                timeout=(5, 10),
            )

            if response.status_code == 429:
                sleepTime = random.uniform(900, 1800)

                logging.warning(
                    f"429 rate limit detected for ad {token}. "
                    f"Sleeping {int(sleepTime)} seconds..."
                )

                time.sleep(sleepTime)
                retries += 1
                continue

            if response.status_code == 200:
                return response.json()

            raise requests.exceptions.RequestException(
                f"Received status code {response.status_code}"
            )

        except (requests.exceptions.RequestException, ValueError) as e:
            retries += 1

            waitTime = (BASE_BACKOFF_TIME * (2**retries)) + random.uniform(5, 30)

            logging.warning(
                f"Request failed for token {token}: {e}. "
                f"Retrying in {int(waitTime)} seconds "
                f"({retries}/{MAX_RETRIES})..."
            )

            time.sleep(waitTime)

    logging.error(f"Max retries reached for token {token}. Skipping.")

    return None


def processAds(
    conn,
    tokens,
    categoryName,
    categoryConfig,
    extractorModule,
    filtersModule,
    repositoryModule,
):
    tableName = getConfigValue(
        categoryConfig,
        "tableName",
        "TABLE_NAME",
        None,
    )

    referer = getConfigValue(
        categoryConfig,
        "referer",
        "REFERER",
        "https://divar.ir/",
    )

    session = createSession(
        referer=referer,
        allowedMethods=["GET"],
    )

    cur = conn.cursor()

    try:
        logging.info(f"{categoryName}: start getting advertisement data...")

        tokens = filterTokens(cur, tokens, tableName)

        tokens = [token for token in tokens if shouldProcessToken(token)]

        logging.info(
            f"{categoryName}: {len(tokens)} tokens assigned to this worker after partition."
        )

        logging.info(f"{categoryName}: {len(tokens)} tokens after database filter.")

        for index, token in enumerate(tokens):
            randomSleep(3, 9)

            if index % random.randint(7, 12) == 0 and index != 0:
                longSleep = random.uniform(10, 30)
                logging.info(
                    f"{categoryName}: cooling down for {int(longSleep)} seconds..."
                )
                time.sleep(longSleep)

            res = fetchAdData(session, token)

            if not res:
                logging.warning(f"{categoryName}: no response for token {token}")
                continue

            listData = getSectionWidgets(res, "LIST_DATA")
            mapData = getMapData(res)
            titleSection = getSection(res, "TITLE")
            descriptionSection = getSection(res, "DESCRIPTION")

            if not listData or not titleSection or not descriptionSection:
                logging.warning(
                    f"{categoryName}: missing sections for token {token}. "
                    f"listData={bool(listData)}, titleSection={bool(titleSection)}, "
                    f"descriptionSection={bool(descriptionSection)}"
                )
                continue

            title = getTitle(titleSection)
            description = getDescription(descriptionSection)

            if not title or not description:
                logging.warning(
                    f"{categoryName}: missing title or description for token {token}. "
                    f"title={bool(title)}, description={bool(description)}"
                )
                continue

            extractAdData = getattr(extractorModule, "extractAdData", None)

            if not extractAdData:
                raise AttributeError(
                    f"extractAdData(listData, description=None) not found in {categoryName}/extractor.py"
                )

            try:
                specificData = extractAdData(
                    listData=listData,
                    description=description,
                    rawAd=res,
                )
            except TypeError:
                specificData = extractAdData(
                    listData=listData,
                    description=description,
                )

            if specificData is None:
                logging.warning(
                    f"{categoryName}: extractor returned None for token {token}"
                )
                continue

            # logging.info(
            #     f"{categoryName}: extracted data for token {token}: {specificData}"
            # )

            isValidAd = getattr(filtersModule, "isValidAd", None)
            if isValidAd:
                isValid = isValidAd(
                    rawAd=res,
                    commonData={
                        "title": title,
                        "description": description,
                    },
                    specificData=specificData,
                )

                if not isValid:
                    logging.warning(
                        f"{categoryName}: ad rejected by filter for token {token}. "
                        f"specificData={specificData}"
                    )
                    continue

            randomSleep(20, 60)

            mobile = getMobile(res, token)

            if mobile == CONTACT_CAPTCHA:
                from core.captchaBreak import captchaBreakMain

                captchaRes = captchaBreakMain(session=session, res=res, token=token)

                if captchaRes is True:
                    logging.info(f"CAPTCHA/contact challenge passed for token {token}")
                    return True

                if isinstance(captchaRes, dict):
                    status = captchaRes.get("status")
                    reason = captchaRes.get("reason")

                    if status == "manual_required":
                        logging.warning(
                            f"{categoryName}: manual CAPTCHA required for token {token}. "
                            f"reason={reason}. Skipping this token without global cooldown."
                        )
                        continue

                    if status == "blocked":
                        logging.warning(
                            f"{categoryName}: blocked/limited while getting mobile for token {token}. "
                            f"Cooling down for shorter period..."
                        )
                        time.sleep(900)
                        continue

                    logging.warning(
                        f"{categoryName}: contact challenge failed for token {token}. "
                        f"status={status}, reason={reason}. Skipping token."
                    )
                    continue

                logging.warning(
                    f"{categoryName}: unknown captcha result for token {token}. Skipping token."
                )
                continue

            if mobile is None:
                logging.warning(f"{categoryName}: mobile not found for token {token}")
                continue

            if isValidAd:
                isValidAfterMobile = isValidAd(
                    rawAd=res,
                    commonData={
                        "title": title,
                        "description": description,
                        "mobile": mobile,
                    },
                    specificData=specificData,
                )

                if not isValidAfterMobile:
                    logging.warning(
                        f"{categoryName}: ad rejected after mobile check for token {token}."
                    )
                    continue

            if isDuplicateAd(cur, tableName, title, description, mobile):
                logging.info(f"{categoryName}: duplicate advertisement found.")
                continue

            latitude, longitude = getCoordinates(mapData)

            commonData = buildCommonData(
                token=token,
                res=res,
                title=title,
                description=description,
                mobile=mobile,
                latitude=latitude,
                longitude=longitude,
                categoryName=categoryName,
            )

            data = {
                **commonData,
                **specificData,
            }

            if categoryName == "vehicleRental":
                vehicleDeposit = specificData.get("deposit")

                if vehicleDeposit not in [None, 0, "0"]:
                    data["deposit"] = vehicleDeposit

            data = normalizeData(data)

            try:
                insertResult = callInsert(
                    repositoryModule=repositoryModule,
                    conn=conn,
                    data=data,
                    categoryName=categoryName,
                )

                if insertResult is not True:
                    logging.warning(
                        f"{categoryName}: failed to insert advertisement for token {token}."
                    )
                else:
                    logging.info(
                        f"{categoryName}: successfully processed advertisement for token {token}."
                    )

            except Exception as e:
                logging.error(
                    f"{categoryName}: database insert error for token {token}: {e}"
                )
                logging.error(traceback.format_exc())
                conn.rollback()
                continue

            waitTime = random.uniform(
                max(5, REQUEST_DELAY - 5),
                REQUEST_DELAY + 2,
            )

            logging.info(
                f"{categoryName}: waiting {int(waitTime)} seconds before next ad..."
            )

            time.sleep(waitTime)

        logging.info(f"{categoryName}: data processing completed successfully.")

    except Exception as e:
        failedToken = token if "token" in locals() else None

        logging.error(f"{categoryName}: process failed for token {failedToken}: {e}")
        logging.error(traceback.format_exc())

        conn.rollback()

    finally:
        cur.close()

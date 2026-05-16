import re


def normalizeText(value):
    if value is None:
        return None

    return (
        str(value)
        .replace("\u200f", "")
        .replace("\u200e", "")
        .replace("\u200c", " ")
        .replace("\u200d", " ")
        .replace("ي", "ی")
        .replace("ك", "ک")
        .replace("：", ":")
        .strip()
    )


def persianToEnglishNumber(value):
    if value is None:
        return None

    return str(value).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))


def normalizeSpaces(value):
    if value is None:
        return None

    return re.sub(r"\s+", " ", str(value)).strip()


def parseBool(value):
    if value is None:
        return None

    value = normalizeText(value)

    trueValues = {
        "هستم",
        "هست",
        "دارد",
        "بله",
        "مجاز",
        "قابل مذاکره",
        "قابل معاوضه",
        "مقطوع",
    }

    falseValues = {
        "نیستم",
        "نیست",
        "ندارد",
        "خیر",
        "غیر قابل مذاکره",
        "غیرقابل مذاکره",
        "غیر قابل معاوضه",
        "غیرقابل معاوضه",
    }

    if value in trueValues:
        return True

    if value in falseValues:
        return False

    return None


def getChips(data):
    chips = data.get("chip_list", {}).get("chips", [])
    result = []

    for chip in chips:
        text = normalizeText(chip.get("text"))

        if text:
            result.append(text)

    return result


def chipsToString(chips):
    if not chips:
        return None

    return "، ".join(chips)


def mapTitleToField(title):
    title = normalizeText(title)

    titleMap = {
        "نوع حمل و نقل": "transport_type",
        "نوع حمل ونقل": "transport_type",
        "نوع حمل‌ونقل": "transport_type",
        "نوع وسیله نقلیه": "transport_type",
        "وسیله نقلیه": "transport_type",
        "نوع تور": "tour_type",
        "خدمات تور": "tour_services",
        "مایل به معاوضه": "open_to_trade",
        "قابل معاوضه": "open_to_trade",
        "درجه هتل": "hotel_rating",
        "ستاره هتل": "hotel_rating",
        "رتبه هتل": "hotel_rating",
        "تاریخ حرکت": "departure_date",
        "تاریخ رفت": "departure_date",
        "تاریخ شروع": "departure_date",
        "تاریخ برگشت": "return_date",
        "تاریخ بازگشت": "return_date",
        "تاریخ پایان": "return_date",
        "مدت اقامت": "days_of_stay",
        "مدت سفر": "days_of_stay",
    }

    return titleMap.get(title)


def extractFixedPriceFromPriceText(value):
    if value is None:
        return None

    value = normalizeText(value)

    if "مقطوع" in value:
        return True

    if "توافقی" in value:
        return False

    return None


def extractDaysOfStayFromDescription(description):
    if not description:
        return None

    description = normalizeText(description)
    description = persianToEnglishNumber(description)
    description = normalizeSpaces(description)

    patterns = [
        r"\d+\s*شب\s*و\s*\d+\s*روز",
        r"\d+\s*روز\s*و\s*\d+\s*شب",
        r"\d+\s*روزه",
        r"\d+\s*روز",
        r"\d+\s*شب",
    ]

    for pattern in patterns:
        match = re.search(pattern, description)

        if match:
            return match.group(0).strip()

    return None


def extractDepartureDateFromDescription(description):
    if not description:
        return None

    description = normalizeText(description)

    patterns = [
        r"تاریخ\s*حرکت\s*:\s*([^\n\r]+)",
        r"تاریخ\s*رفت\s*:\s*([^\n\r]+)",
        r"حرکت\s*:\s*([^\n\r]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, description)

        if match:
            value = normalizeText(match.group(1))

            if value:
                return value

    return None


def extractNumberFromDaysOfStay(daysOfStay):
    if not daysOfStay:
        return None

    value = persianToEnglishNumber(daysOfStay)
    numbers = re.findall(r"\d+", value)

    if not numbers:
        return None

    return int(numbers[0])


def guessReturnDate(departureDate, daysOfStay):
    if not departureDate or not daysOfStay:
        return None

    departureDate = normalizeText(departureDate)
    daysNumber = extractNumberFromDaysOfStay(daysOfStay)

    if daysNumber is None:
        return None

    if "همه روزه" in departureDate or "هر روز" in departureDate:
        return f"{daysNumber} روز بعد از حرکت"

    return f"{daysNumber} روز بعد از {departureDate}"


def updateResultByField(result, fieldName, value):
    if fieldName is None:
        return

    value = normalizeText(value)

    if value is None:
        return

    if fieldName == "open_to_trade":
        result[fieldName] = parseBool(value)
        return

    result[fieldName] = value


def extractUnexpandableRow(data, result):
    title = data.get("title")
    value = data.get("value")

    fieldName = mapTitleToField(title)

    if fieldName:
        updateResultByField(result, fieldName, value)

    if normalizeText(title) == "قیمت":
        fixedPrice = extractFixedPriceFromPriceText(value)

        if fixedPrice is not None:
            result["fixed_price"] = fixedPrice


def extractWrapperRow(previousTitle, data, result):
    fieldName = mapTitleToField(previousTitle)

    if fieldName is None:
        return

    chips = getChips(data)

    if not chips:
        return

    if fieldName in ["tour_type", "tour_services"]:
        result[fieldName] = chipsToString(chips)


def extractSelectorModal(data, result):
    action = data.get("action", {})
    payload = action.get("payload", {})
    modalPage = payload.get("modal_page")

    if not modalPage:
        return

    for widget in modalPage.get("widget_list", []):
        widgetType = widget.get("widget_type")
        widgetData = widget.get("data", {})

        if widgetType == "UNEXPANDABLE_ROW":
            fieldName = mapTitleToField(widgetData.get("title"))
            updateResultByField(
                result=result,
                fieldName=fieldName,
                value=widgetData.get("value"),
            )

        elif widgetType == "WRAPPER_ROW":
            fieldName = mapTitleToField(widgetData.get("title"))
            chips = getChips(widgetData)

            if fieldName and chips:
                result[fieldName] = chipsToString(chips)


def extractDescriptionHints(description, result):
    if result.get("departure_date") is None:
        result["departure_date"] = extractDepartureDateFromDescription(description)

    if result.get("days_of_stay") is None:
        result["days_of_stay"] = extractDaysOfStayFromDescription(description)

    if result.get("return_date") is None:
        result["return_date"] = guessReturnDate(
            departureDate=result.get("departure_date"),
            daysOfStay=result.get("days_of_stay"),
        )


def extractAdData(listData, description=None):
    result = {
        "transport_type": None,
        "tour_type": None,
        "tour_services": None,
        "fixed_price": None,
        "open_to_trade": None,
        "hotel_rating": None,
        "departure_date": None,
        "return_date": None,
        "days_of_stay": None,
    }

    previousDescriptionTitle = None

    for item in listData:
        widgetType = item.get("widget_type")
        data = item.get("data", {})

        if widgetType == "UNEXPANDABLE_ROW":
            extractUnexpandableRow(data, result)
            previousDescriptionTitle = None
            continue

        if widgetType == "DESCRIPTION_ROW":
            previousDescriptionTitle = data.get("text")
            continue

        if widgetType == "WRAPPER_ROW":
            extractWrapperRow(
                previousTitle=previousDescriptionTitle,
                data=data,
                result=result,
            )
            previousDescriptionTitle = None
            continue

        if widgetType == "SELECTOR_ROW":
            extractSelectorModal(data, result)
            previousDescriptionTitle = None
            continue

    extractDescriptionHints(description, result)

    return result

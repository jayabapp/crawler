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


def parseBool(value):
    if value is None:
        return None

    value = normalizeText(value)

    falseValues = {
        "خیر",
        "نه",
        "نیست",
        "ندارد",
        "ندارم",
        "غیرمجاز",
        "غیر مجاز",
        "ممنوع",
        "امکان ندارد",
        "امکان پذیر نیست",
        "امکان‌پذیر نیست",
    }

    trueValues = {
        "بله",
        "هست",
        "دارد",
        "دارم",
        "مجاز",
        "امکان دارد",
        "امکان پذیر است",
        "امکان‌پذیر است",
    }

    if value in falseValues:
        return False

    if value in trueValues:
        return True

    return None


def mapTitleToField(title):
    title = normalizeText(title)

    titleMap = {
        "تخصص ها": "specialities",
        "تخصص‌ها": "specialties",
        "تخصص": "specialties",
        "ساعت کاری": "working_hours",
        "ساعات کاری": "working_hours",
        "زمان کاری": "working_hours",
        "حداقل سفارش": "minimum_order",
        "حداقل تعداد سفارش": "minimum_order",
        "ظرفیت پذیرایی": "guest_capacity",
        "ظرفیت": "guest_capacity",
        "ظرفیت مهمان": "guest_capacity",
        "امکان تست غذا": "food_tasting",
        "تست غذا": "food_tasting",
        "امکان مزه غذا": "food_tasting",
    }

    return titleMap.get(title)


def updateResultByField(result, fieldName, value):
    if fieldName is None:
        return

    value = normalizeText(value)

    if value is None:
        return

    if fieldName == "specialities":
        fieldName = "specialties"

    if fieldName == "food_tasting":
        result[fieldName] = parseBool(value)
        return

    result[fieldName] = value


def extractTitleDescriptionPairs(listData, result):
    previousTitle = None

    for item in listData:
        widgetType = item.get("widget_type")
        data = item.get("data", {})

        if widgetType == "TITLE_ROW":
            previousTitle = data.get("text")
            continue

        if widgetType == "DESCRIPTION_ROW":
            fieldName = mapTitleToField(previousTitle)
            value = data.get("text")

            updateResultByField(
                result=result,
                fieldName=fieldName,
                value=value,
            )

            previousTitle = None
            continue

        previousTitle = None


def extractUnexpandableRow(data, result):
    title = data.get("title")
    value = data.get("value")

    fieldName = mapTitleToField(title)

    updateResultByField(
        result=result,
        fieldName=fieldName,
        value=value,
    )


def extractModalFeatures(data, result):
    action = data.get("action", {})
    payload = action.get("payload", {})
    modalPage = payload.get("modal_page")

    if not modalPage:
        return

    for widget in modalPage.get("widget_list", []):
        widgetType = widget.get("widget_type")
        widgetData = widget.get("data", {})

        if widgetType == "UNEXPANDABLE_ROW":
            extractUnexpandableRow(widgetData, result)


def extractDescriptionHints(description, result):
    if not description:
        return

    description = normalizeText(description)

    if result.get("specialties") is None:
        keywords = []

        possibleSpecialties = [
            "آشپزی",
            "غذای ایرانی",
            "غذای بین الملل",
            "غذای بین‌الملل",
            "پذیرایی",
            "مراسم",
            "عروسی",
            "تولد",
            "مجلس",
            "قهوه",
            "چای",
        ]

        for keyword in possibleSpecialties:
            if keyword in description:
                keywords.append(keyword)

        if keywords:
            result["specialties"] = "، ".join(sorted(set(keywords)))

    if result.get("food_tasting") is None:
        negativePatterns = [
            "تست غذا ندارد",
            "امکان تست غذا ندارد",
            "تست غذا نداریم",
        ]

        positivePatterns = [
            "تست غذا دارد",
            "امکان تست غذا دارد",
            "تست غذا",
        ]

        if any(pattern in description for pattern in negativePatterns):
            result["food_tasting"] = False
        elif any(pattern in description for pattern in positivePatterns):
            result["food_tasting"] = True


def extractAdData(listData, description=None, rawAd=None):
    result = {
        "specialties": None,
        "working_hours": None,
        "minimum_order": None,
        "guest_capacity": None,
        "food_tasting": None,
    }

    extractTitleDescriptionPairs(
        listData=listData,
        result=result,
    )

    for item in listData:
        widgetType = item.get("widget_type")
        data = item.get("data", {})

        if widgetType == "UNEXPANDABLE_ROW":
            extractUnexpandableRow(data, result)
            continue

        if widgetType == "SELECTOR_ROW":
            extractModalFeatures(data, result)
            continue

    extractDescriptionHints(
        description=description,
        result=result,
    )

    return result

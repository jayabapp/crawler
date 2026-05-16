def persianToEnglishNumber(value):
    if value is None:
        return None

    return str(value).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))


def parseInt(value, default=None):
    if value is None:
        return default

    try:
        englishValue = persianToEnglishNumber(value)
        englishValue = englishValue.replace(",", "")
        englishValue = englishValue.split(" ")[0]
        return int(englishValue)
    except Exception:
        return default


def extractChips(listData):
    descriptionToVariableMap = {
        "مناسب برای": "good_for",
        "مدت زمان اجاره": "rental_period",
    }

    variables = {
        "good_for": [],
        "rental_period": [],
    }

    lastDescriptionText = None

    for item in listData:
        widgetType = item.get("widget_type")
        data = item.get("data", {})

        if widgetType == "DESCRIPTION_ROW":
            lastDescriptionText = data.get("text")

        elif widgetType == "WRAPPER_ROW":
            if lastDescriptionText in descriptionToVariableMap:
                variableName = descriptionToVariableMap[lastDescriptionText]
                chips = data.get("chip_list", {}).get("chips", [])

                for chip in chips:
                    chipText = chip.get("text")

                    if chipText:
                        variables[variableName].append(chipText)

            lastDescriptionText = None

    return variables


def extractModalFeatures(listData):
    result = {
        "insurance_status": None,
        "build_year": None,
        "daily_kilometer_limit": None,
        "deposit": 0,
    }

    for item in listData:
        widgetType = item.get("widget_type")
        data = item.get("data", {})

        if widgetType != "SELECTOR_ROW":
            continue

        action = data.get("action", {})
        payload = action.get("payload", {})
        modalPage = payload.get("modal_page")

        if not modalPage:
            continue

        for feature in modalPage.get("widget_list", []):
            featureData = feature.get("data", {})
            title = featureData.get("title")
            value = featureData.get("value")

            if title == "سال ساخت خودرو":
                result["build_year"] = parseInt(value)

            elif title == "مبلغ ضمانت":
                result["deposit"] = parseInt(value, default=0)

            elif title == "وضعیت بیمه":
                result["insurance_status"] = value

            elif title == "محدودیت کیلومتر (روزانه)":
                result["daily_kilometer_limit"] = parseInt(value, default=None)

    return result


def extractMainRows(listData):
    result = {
        "brand_and_model": None,
        "rental_type": None,
    }

    for item in listData:
        data = item.get("data", {})
        title = data.get("title")
        value = data.get("value")

        if title == "برند و مدل":
            result["brand_and_model"] = value

        elif title == "نوع اجاره":
            result["rental_type"] = value

    return result


def extractAdData(listData, description=None):
    mainRows = extractMainRows(listData)
    chips = extractChips(listData)
    modalFeatures = extractModalFeatures(listData)

    return {
        "brand_and_model": mainRows["brand_and_model"],
        "rental_type": mainRows["rental_type"],
        "rental_period": chips["rental_period"],
        "good_for": chips["good_for"],
        "insurance_status": modalFeatures["insurance_status"],
        "build_year": modalFeatures["build_year"],
        "daily_kilometer_limit": modalFeatures["daily_kilometer_limit"],
        "deposit": modalFeatures["deposit"],
    }

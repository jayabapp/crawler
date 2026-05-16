from unidecode import unidecode


def persianToEnglishNumber(value):
    if value is None:
        return None

    return str(value).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))


def parseInt(value, default=0):
    if value is None:
        return default

    try:
        englishValue = persianToEnglishNumber(value)
        englishValue = unidecode(englishValue)
        englishValue = englishValue.replace(",", "")
        englishValue = englishValue.split(" ")[0]
        return int(englishValue)
    except Exception:
        return default


def normalizeDescription(description):
    if not description:
        return ""

    return (
        description.replace("‌", " ")
        .replace("ي", "ی")
        .replace("ك", "ک")
        .replace("\n", " ")
    )


def findFeaturesFromDescription(
    description,
    floorMaterial=None,
    wc=None,
    cooler=None,
    heater=None,
    hotWaterSupplier=None,
    direction=None,
):
    description = normalizeDescription(description)
    words = description.split()

    keywords = {
        "کف": "floorMaterial",
        "جهت": "direction",
        "آب": "hotWaterSupplier",
        "گرمایش": "heater",
        "سرمایش": "cooler",
        "دستشویی": "wc",
        "سرویس": "wc",
    }

    for index, word in enumerate(words):
        if word not in keywords:
            continue

        if index + 1 >= len(words):
            continue

        value = words[index + 1]
        target = keywords[word]

        if target == "floorMaterial" and floorMaterial is None:
            floorMaterial = value

        elif target == "direction" and direction is None:
            direction = value

        elif target == "hotWaterSupplier" and hotWaterSupplier is None:
            hotWaterSupplier = value

        elif target == "heater" and heater is None:
            heater = value

        elif target == "cooler" and cooler is None:
            cooler = value

        elif target == "wc" and wc is None:
            wc = value

    return {
        "floor_material": floorMaterial,
        "wc": wc,
        "cooler": cooler,
        "heater": heater,
        "hot_water_supplier": hotWaterSupplier,
        "direction": direction,
    }


def extractGroupInfoRow(data):
    result = {
        "area": 0,
        "year": 0,
        "rooms": 0,
    }

    for feature in data.get("items", []):
        title = feature.get("title")
        value = feature.get("value", "")

        if title == "متراژ":
            result["area"] = parseInt(value)

        elif title == "ساخت":
            result["year"] = parseInt(value)

        elif title == "اتاق":
            result["rooms"] = parseInt(value)

    return result


def extractGroupFeatureRow(data):
    result = {
        "parking": False,
        "warehouse": False,
        "balcony": False,
    }

    for feature in data.get("items", []):
        iconName = feature.get("icon", {}).get("icon_name")
        available = feature.get("available", False)

        if iconName == "PARKING":
            result["parking"] = available

        elif iconName == "CABINET":
            result["warehouse"] = available

        elif iconName == "BALCONY":
            result["balcony"] = available

    return result


def extractSelectorRow(data):
    result = {
        "renovated": None,
        "floor_material": None,
        "wc": None,
        "cooler": None,
        "heater": None,
        "hot_water_supplier": None,
        "direction": None,
        "good_for": None,
        "pets_allowed": None,
        "furnished": None,
    }

    action = data.get("action", {})
    payload = action.get("payload", {})
    modalPage = payload.get("modal_page")

    if not modalPage:
        return result

    for feature in modalPage.get("widget_list", []):
        widgetType = feature.get("widget_type")
        featureData = feature.get("data", {})
        title = featureData.get("title")
        value = featureData.get("value")

        if title == "جهت ساختمان":
            result["direction"] = value

        elif widgetType == "WRAPPER_ROW":
            result["good_for"] = [
                chip.get("text")
                for chip in featureData.get("chip_list", {}).get("chips", [])
                if chip.get("text")
            ]

        elif title == "حیوان خانگی مجاز":
            result["pets_allowed"] = value

        elif title in ["بازسازی‌ شده", "بازسازی شده"]:
            result["renovated"] = value == "هست"

        elif title == "مبله":
            result["furnished"] = value == "هست"

        else:
            iconName = featureData.get("icon", {}).get("icon_name")

            if iconName == "TEXTURE":
                result["floor_material"] = title

            elif iconName == "WC":
                result["wc"] = title

            elif iconName == "SUNNY":
                result["heater"] = title

            elif iconName == "SNOWFLAKE":
                result["cooler"] = title

            elif iconName == "THERMOMETER":
                result["hot_water_supplier"] = title

    return result


def extractAdData(listData, description=None):
    result = {
        "area": 0,
        "land_area": 0,
        "year": 0,
        "rooms": 0,
        "parking": False,
        "warehouse": False,
        "balcony": False,
        "renovated": None,
        "floor_material": None,
        "wc": None,
        "cooler": None,
        "heater": None,
        "hot_water_supplier": None,
        "direction": None,
        "good_for": None,
        "pets_allowed": None,
        "furnished": None,
    }

    for item in listData:
        widgetType = item.get("widget_type")
        data = item.get("data", {})

        if widgetType == "GROUP_INFO_ROW":
            result.update(extractGroupInfoRow(data))

        elif widgetType == "GROUP_FEATURE_ROW":
            result.update(extractGroupFeatureRow(data))

        elif widgetType == "UNEXPANDABLE_ROW" and data.get("title") == "متراژ زمین":
            result["land_area"] = parseInt(data.get("value"), default=0)

        elif widgetType == "SELECTOR_ROW":
            selectorData = extractSelectorRow(data)

            for key, value in selectorData.items():
                if value is not None:
                    result[key] = value

    descriptionFeatures = findFeaturesFromDescription(
        description=description,
        floorMaterial=result["floor_material"],
        wc=result["wc"],
        cooler=result["cooler"],
        heater=result["heater"],
        hotWaterSupplier=result["hot_water_supplier"],
        direction=result["direction"],
    )

    result.update(descriptionFeatures)

    return result

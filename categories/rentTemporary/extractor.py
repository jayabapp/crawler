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


def normalizeSpaces(value):
    if value is None:
        return None

    return re.sub(r"\s+", " ", str(value)).strip()


def persianToEnglishNumber(value):
    if value is None:
        return None

    return str(value).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))


def parseNumber(value, default=None):
    if value is None:
        return default

    try:
        value = normalizeText(value)
        value = persianToEnglishNumber(value)
        value = value.replace(",", "")

        numbers = re.findall(r"\d+", value)

        if not numbers:
            return default

        return int(numbers[0])

    except Exception:
        return default


def parsePrice(value, default=None):
    if value is None:
        return default

    try:
        value = normalizeText(value)
        value = persianToEnglishNumber(value)
        value = value.replace(",", "")
        value = value.replace("تومان", "")
        value = value.replace("/شب", "")
        value = value.replace("/روز", "")
        value = value.replace("شب", "")
        value = value.replace("روز", "")
        value = value.strip()

        numbers = re.findall(r"\d+", value)

        if not numbers:
            return default

        return int(numbers[0])

    except Exception:
        return default


def parseRooms(value, default=0):
    if value is None:
        return default

    value = normalizeText(value)

    if value in ["بدون اتاق", "بدون خواب"]:
        return 0

    return parseNumber(value, default=default)


def parseBool(value):
    if value is None:
        return None

    value = normalizeText(value)

    trueValues = {
        "بله",
        "هست",
        "دارد",
        "دارم",
        "مجاز",
        "دارد.",
        "مبله",
    }

    falseValues = {
        "خیر",
        "نیست",
        "ندارد",
        "ندارم",
        "غیرمجاز",
        "غیر مجاز",
        "ممنوع",
    }

    if value in trueValues:
        return True

    if value in falseValues:
        return False

    return None


def chipsToString(chips):
    if not chips:
        return None

    return "، ".join(chips)


def getChips(data):
    chips = data.get("chip_list", {}).get("chips", [])
    result = []

    for chip in chips:
        text = normalizeText(chip.get("text"))

        if text:
            result.append(text)

    return result


def getCategoryFromRawAd(rawAd=None):
    if not rawAd:
        return None

    webengage = rawAd.get("webengage", {})
    category = webengage.get("category")

    if category:
        return category

    analytics = rawAd.get("analytics", {})
    category = analytics.get("cat3")

    if category:
        return category

    try:
        parentItems = rawAd["sections"][0]["widgets"][0]["data"]["parent_items"]

        for item in reversed(parentItems):
            category = (
                item.get("action", {})
                .get("payload", {})
                .get("search_data", {})
                .get("form_data", {})
                .get("data", {})
                .get("category", {})
                .get("str", {})
                .get("value")
            )

            if category in ["suite-apartment", "villa", "workspace"]:
                return category

    except Exception:
        pass

    return None


def getDefaultFeatures(category):
    if category == "suite-apartment":
        return {
            "floor": None,
            "elevator": None,
            "parking": None,
            "pets_allowed": None,
            "rental_period": None,
            "cooler_and_heater": None,
            "facilities": None,
            "check_in_time": None,
            "minimum_stay_requirement": None,
            "check_out_time": None,
            "damage_deposit": None,
            "full_furnished": None,
        }

    if category == "villa":
        return {
            "land_area": None,
            "view": None,
            "pets_allowed": None,
            "pool_type": None,
            "parking_type": None,
            "grill": None,
            "pergola": None,
            "green_space": None,
            "pool": None,
        }

    if category == "workspace":
        return {
            "space_type": None,
            "rental_period": None,
            "parking": None,
            "equipment": None,
            "minimum_rental_period": None,
            "pantry": None,
        }

    return {}


def mapTitleToCommonField(title):
    title = normalizeText(title)

    titleMap = {
        "متراژ": "area",
        "متراژ ویلا": "area",
        "اتاق": "rooms",
        "ظرفیت استاندارد": "standard_capacity",
        "ظرفیت اضافه": "extra_capacity",
        "روزهای عادی": "weekday_rate",
        "روزهای عادی (شنبه تا سه شنبه)": "weekday_rate",
        "روزهای عادی (شنبه تا سه‌شنبه)": "weekday_rate",
        "آخر هفته": "weekend_rate",
        "تعطیلات و مناسبت ها": "special_dates_rate",
        "تعطیلات و مناسبت‌ها": "special_dates_rate",
        "روزهای خاص (تعطیلات و مناسبت ها)": "special_dates_rate",
        "روزهای خاص (تعطیلات و مناسبت‌ها)": "special_dates_rate",
        "هزینه هر نفر اضافه": "extra_person_charge",
        "هزینهٔ هر نفر اضافه": "extra_person_charge",
    }

    return titleMap.get(title)


def mapTitleToFeatureField(title, category):
    title = normalizeText(title)

    suiteApartmentMap = {
        "طبقه": "floor",
        "آسانسور": "elevator",
        "پارکینگ": "parking",
        "حیوان خانگی مجاز": "pets_allowed",
        "دوره اجاره": "rental_period",
        "دورهٔ اجاره": "rental_period",
        "سیستم گرمایش/سرمایش": "cooler_and_heater",
        "سرمایش و گرمایش": "cooler_and_heater",
        "سیستم سرمایش/گرمایش": "cooler_and_heater",
        "امکانات": "facilities",
        "امکانات رفاهی": "facilities",
        "ساعت ورود": "check_in_time",
        "حداقل مدت اقامت": "minimum_stay_requirement",
        "ساعت خروج": "check_out_time",
        "ودیعه خسارت": "damage_deposit",
        "مبله": "full_furnished",
        "مبله کامل": "full_furnished",
    }

    villaMap = {
        "متراژ زمین": "land_area",
        "چشم انداز": "view",
        "چشم‌انداز": "view",
        "حیوان خانگی مجاز": "pets_allowed",
        "نوع استخر": "pool_type",
        "تعداد پارکینگ": "parking_type",
        "پارکینگ": "parking_type",
        "باربیکیو": "grill",
        "آلاچیق": "pergola",
        "فضای سبز": "green_space",
        "فضای سبز/باغ": "green_space",
        "باغ": "green_space",
        "استخر": "pool",
    }

    workspaceMap = {
        "نوع فضا": "space_type",
        "دوره اجاره": "rental_period",
        "دورهٔ اجاره": "rental_period",
        "پارکینگ": "parking",
        "تجهیزات موجود": "equipment",
        "تجهیزات": "equipment",
        "حداقل مدت اجاره": "minimum_rental_period",
        "آبدارخانه/آشپزخانه": "pantry",
        "آبدارخانه": "pantry",
        "آشپزخانه": "pantry",
    }

    if category == "suite-apartment":
        return suiteApartmentMap.get(title)

    if category == "villa":
        return villaMap.get(title)

    if category == "workspace":
        return workspaceMap.get(title)

    return None


def setCommonValue(result, fieldName, value):
    if fieldName is None:
        return

    value = normalizeText(value)

    if fieldName == "area":
        result[fieldName] = parseNumber(value, default=0)
        return

    if fieldName == "rooms":
        result[fieldName] = parseRooms(value, default=0)
        return

    if fieldName in [
        "weekday_rate",
        "weekend_rate",
        "special_dates_rate",
        "extra_person_charge",
    ]:
        result[fieldName] = parsePrice(value, default=None)
        return

    result[fieldName] = value


def setFeatureValue(features, fieldName, value):
    if fieldName is None:
        return

    value = normalizeText(value)

    if fieldName in [
        "elevator",
        "parking",
        "pets_allowed",
        "full_furnished",
        "grill",
        "pergola",
        "green_space",
        "pool",
        "pantry",
    ]:
        parsedBool = parseBool(value)

        if parsedBool is not None:
            features[fieldName] = parsedBool
        else:
            features[fieldName] = value

        return

    if fieldName in ["land_area"]:
        features[fieldName] = parseNumber(value, default=None)
        return

    if fieldName in ["damage_deposit"]:
        features[fieldName] = parsePrice(value, default=None)
        return

    features[fieldName] = value


def extractGroupInfoRow(data, result):
    for item in data.get("items", []):
        title = item.get("title")
        value = item.get("value")

        fieldName = mapTitleToCommonField(title)
        setCommonValue(result, fieldName, value)


def extractUnexpandableRow(data, result, features, category):
    title = data.get("title")
    value = data.get("value")

    commonFieldName = mapTitleToCommonField(title)

    if commonFieldName:
        setCommonValue(result, commonFieldName, value)
        return

    featureFieldName = mapTitleToFeatureField(title, category)

    if featureFieldName:
        setFeatureValue(features, featureFieldName, value)


def extractWrapperRow(previousTitle, data, features, category):
    featureFieldName = mapTitleToFeatureField(previousTitle, category)

    if not featureFieldName:
        return

    chips = getChips(data)

    if not chips:
        return

    features[featureFieldName] = chipsToString(chips)


def extractModalFeatures(data, features, category):
    action = data.get("action", {})
    payload = action.get("payload", {})
    modalPage = payload.get("modal_page")

    if not modalPage:
        return

    previousTitle = None

    for widget in modalPage.get("widget_list", []):
        widgetType = widget.get("widget_type")
        widgetData = widget.get("data", {})

        if widgetType == "DESCRIPTION_ROW":
            previousTitle = widgetData.get("text")
            continue

        if widgetType == "WRAPPER_ROW":
            extractWrapperRow(
                previousTitle=previousTitle,
                data=widgetData,
                features=features,
                category=category,
            )
            previousTitle = None
            continue

        if widgetType == "UNEXPANDABLE_ROW":
            extractUnexpandableRow(
                data=widgetData,
                result={},
                features=features,
                category=category,
            )
            previousTitle = None
            continue

        previousTitle = None


def extractDescriptionHints(description, result, features, category):
    if not description:
        return

    description = normalizeText(description)

    if category == "suite-apartment":
        if features.get("parking") is None and "پارکینگ" in description:
            features["parking"] = True

        if features.get("elevator") is None and "آسانسور" in description:
            features["elevator"] = True

        if features.get("pets_allowed") is None:
            if "حیوان خانگی" in description and "ممنوع" in description:
                features["pets_allowed"] = False

        if features.get("cooler_and_heater") is None:
            foundItems = []

            keywords = [
                "سرمایشی",
                "گرمایشی",
                "سرمایش",
                "گرمایش",
                "بخاری",
                "کولر",
                "اسپیلت",
                "اسپلیت",
            ]

            for keyword in keywords:
                if keyword in description:
                    foundItems.append(keyword)

            if foundItems:
                features["cooler_and_heater"] = "، ".join(sorted(set(foundItems)))

        if features.get("facilities") is None:
            facilities = []

            keywords = [
                "تلویزیون",
                "یخچال",
                "اجاق",
                "لوازم آشپزی",
                "سرویس بهداشتی",
                "حمام",
                "بالکن",
                "حوله",
                "ملحفه",
            ]

            for keyword in keywords:
                if keyword in description:
                    facilities.append(keyword)

            if facilities:
                features["facilities"] = "، ".join(sorted(set(facilities)))

    if category == "villa":
        if features.get("pool") is None:
            if "استخر" in description or "استخردار" in description:
                features["pool"] = True

        if features.get("pool_type") is None:
            poolTypes = []

            for keyword in ["سرپوشیده", "روباز", "آبگرم", "آب گرم"]:
                if keyword in description:
                    poolTypes.append(keyword)

            if poolTypes:
                features["pool_type"] = "، ".join(sorted(set(poolTypes)))

        if features.get("grill") is None:
            if (
                "باربیکیو" in description
                or "باربیکو" in description
                or "کباب" in description
            ):
                features["grill"] = True

        if features.get("pergola") is None:
            if "آلاچیق" in description:
                features["pergola"] = True

        if features.get("green_space") is None:
            if (
                "فضای سبز" in description
                or "روف گاردن" in description
                or "باغ" in description
            ):
                features["green_space"] = True

        if features.get("pets_allowed") is None:
            if "حیوانات" in description and "ممنوع" in description:
                features["pets_allowed"] = False

        if features.get("view") is None:
            views = []

            for keyword in ["دریا", "جنگل", "کوهستان", "کوه", "باغ", "شهر"]:
                if keyword in description:
                    views.append(keyword)

            if views:
                features["view"] = "، ".join(sorted(set(views)))

    if category == "workspace":
        if features.get("equipment") is None:
            equipment = []

            equipmentKeywords = [
                "ویدئو پروژکتور",
                "پروژکتور",
                "وایت برد",
                "سیستم صوت",
                "میکروفن",
                "تلویزیون",
                "مانیتور",
                "میز",
                "صندلی",
                "کامپیوتر",
                "لپ تاپ",
                "لپ‌تاپ",
                "پذیرایی",
            ]

            for keyword in equipmentKeywords:
                if keyword in description:
                    equipment.append(keyword)

            if equipment:
                features["equipment"] = "، ".join(sorted(set(equipment)))

        if features.get("parking") is None and "پارکینگ" in description:
            features["parking"] = True

        if features.get("pantry") is None:
            if "آبدارخانه" in description or "آشپزخانه" in description:
                features["pantry"] = True


def extractAdData(listData, description=None, rawAd=None):
    category = getCategoryFromRawAd(rawAd)

    result = {
        "category": category,
        "area": 0,
        "rooms": 0,
        "standard_capacity": None,
        "extra_capacity": None,
        "weekday_rate": None,
        "weekend_rate": None,
        "special_dates_rate": None,
        "extra_person_charge": None,
        "features": getDefaultFeatures(category),
    }

    previousTitle = None

    for item in listData:
        widgetType = item.get("widget_type")
        data = item.get("data", {})

        if widgetType == "GROUP_INFO_ROW":
            extractGroupInfoRow(data, result)
            previousTitle = None
            continue

        if widgetType == "UNEXPANDABLE_ROW":
            extractUnexpandableRow(
                data=data,
                result=result,
                features=result["features"],
                category=category,
            )
            previousTitle = None
            continue

        if widgetType == "DESCRIPTION_ROW":
            previousTitle = data.get("text")
            continue

        if widgetType == "WRAPPER_ROW":
            extractWrapperRow(
                previousTitle=previousTitle,
                data=data,
                features=result["features"],
                category=category,
            )
            previousTitle = None
            continue

        if widgetType == "SELECTOR_ROW":
            extractModalFeatures(
                data=data,
                features=result["features"],
                category=category,
            )
            previousTitle = None
            continue

        previousTitle = None

    extractDescriptionHints(
        description=description,
        result=result,
        features=result["features"],
        category=category,
    )

    return result

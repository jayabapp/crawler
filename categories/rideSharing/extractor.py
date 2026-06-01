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


def parsePrice(value, default=None):
    if value is None:
        return default

    value = normalizeText(value)

    if value in ["توافقی", "رایگان", "مجانی"]:
        return default

    try:
        value = persianToEnglishNumber(value)
        value = value.replace(",", "")
        value = value.replace("تومان", "")
        value = value.replace("ریال", "")
        value = value.strip()

        numbers = re.findall(r"\d+", value)

        if not numbers:
            return default

        return int(numbers[0])

    except Exception:
        return default


def parseBool(value):
    if value is None:
        return None

    value = normalizeText(value)

    falseValues = {
        "خیر",
        "نه",
        "نیست",
        "ندارد",
        "مجاز نیست",
        "غیرمجاز",
        "غیر مجاز",
        "ممنوع",
        "قبول نمی کنم",
        "قبول نمیکنم",
        "جا ندارد",
        "جا نداره",
    }

    trueValues = {
        "بله",
        "هست",
        "دارد",
        "مجاز است",
        "مجاز",
        "دارم",
        "امکان دارد",
        "قبول می کنم",
        "قبول میکنم",
        "جا دارد",
        "جا داره",
    }

    if value in falseValues:
        return False

    if value in trueValues:
        return True

    return None


def mapTitleToField(title):
    title = normalizeText(title)

    titleMap = {
        "قیمت": "price",
        "شهر مبدا": "departure_location",
        "شهر مبدأ": "departure_location",
        "مبدا": "departure_location",
        "مبدأ": "departure_location",
        "محل حرکت": "departure_location",
        "شهر مقصد": "destination",
        "مقصد": "destination",
        "تاریخ حرکت": "departure_date",
        "زمان حرکت": "departure_date",
        "تاریخ سفر": "departure_date",
        "تعداد همسفر": "number_of_companions",
        "تعداد همراه": "number_of_companions",
        "تعداد نفرات": "number_of_companions",
        "ظرفیت": "number_of_companions",
        "حیوان خانگی": "pets_allowed",
        "حیوان خانگی مجاز": "pets_allowed",
        "ظرفیت بار/صندوق": "includes_luggage_allowance",
        "ظرفیت بار": "includes_luggage_allowance",
        "صندوق": "includes_luggage_allowance",
        "بار": "includes_luggage_allowance",
    }

    return titleMap.get(title)


def updateResultByField(result, fieldName, value):
    if fieldName is None:
        return

    value = normalizeText(value)

    if fieldName == "price":
        result["price"] = parsePrice(value, default=None)
        return

    if fieldName in ["pets_allowed", "includes_luggage_allowance"]:
        result[fieldName] = parseBool(value)
        return

    result[fieldName] = value


def extractFromDescription(description, result):
    if not description:
        return

    description = normalizeText(description)

    if result.get("departure_location") is None or result.get("destination") is None:
        match = re.search(
            r"از\s+([^\s،,.]+)\s+به\s+سمت\s+([^\s،,.]+)",
            description,
        )

        if match:
            if result.get("departure_location") is None:
                result["departure_location"] = normalizeText(match.group(1))

            if result.get("destination") is None:
                result["destination"] = normalizeText(match.group(2))

    if result.get("departure_date") is None:
        match = re.search(
            r"در\s+تاریخ\s+([^\n\r.،]+)",
            description,
        )

        if match:
            result["departure_date"] = normalizeText(match.group(1))

    if result.get("number_of_companions") is None:
        patterns = [
            r"ظرفیت\s+([۰-۹0-9]+)\s*نفر",
            r"([۰-۹0-9]+)\s*همسفر",
            r"([۰-۹0-9]+)\s*هم مسیر",
            r"([۰-۹0-9]+)\s*هم‌مسیر",
        ]

        for pattern in patterns:
            match = re.search(pattern, description)

            if match:
                result["number_of_companions"] = f"{match.group(1)} نفر"
                break

    if result.get("pets_allowed") is None:
        if "حیوان خانگی" in description:
            negativePetPatterns = [
                "مجاز نیست",
                "مجاز نمی باشد",
                "مجاز نمی‌باشد",
                "غیر مجاز",
                "غیرمجاز",
                "ممنوع",
                "اجازه ندارد",
                "امکان ندارد",
            ]

            positivePetPatterns = [
                "مجاز است",
                "مجاز می باشد",
                "مجاز می‌باشد",
                "مجاز",
                "امکان دارد",
                "اجازه دارد",
            ]

            if any(pattern in description for pattern in negativePetPatterns):
                result["pets_allowed"] = False
            elif any(pattern in description for pattern in positivePetPatterns):
                result["pets_allowed"] = True

    if result.get("includes_luggage_allowance") is None:
        luggageKeywords = ["صندوق", "بار", "چمدان", "وسایل"]

        if any(keyword in description for keyword in luggageKeywords):
            negativeLuggagePatterns = [
                "جا ندارد",
                "جا نداره",
                "ندارد",
                "ظرفیت ندارد",
                "امکان ندارد",
            ]

            positiveLuggagePatterns = [
                "جا دارد",
                "جا داره",
                "دارد",
                "ظرفیت دارد",
                "امکان دارد",
            ]

            if any(pattern in description for pattern in negativeLuggagePatterns):
                result["includes_luggage_allowance"] = False
            elif any(pattern in description for pattern in positiveLuggagePatterns):
                result["includes_luggage_allowance"] = True


def extractAdData(listData, description=None, rawAd=None):
    result = {
        "price": None,
        "departure_location": None,
        "destination": None,
        "departure_date": None,
        "number_of_companions": None,
        "pets_allowed": None,
        "includes_luggage_allowance": None,
    }

    for item in listData:
        widgetType = item.get("widget_type")
        data = item.get("data", {})

        if widgetType != "UNEXPANDABLE_ROW":
            continue

        title = data.get("title")
        value = data.get("value")

        fieldName = mapTitleToField(title)

        updateResultByField(
            result=result,
            fieldName=fieldName,
            value=value,
        )

    extractFromDescription(
        description=description,
        result=result,
    )

    return result

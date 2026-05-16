def isEmpty(value):
    if value is None:
        return True

    if isinstance(value, str) and value.strip() == "":
        return True

    if isinstance(value, list) and len(value) == 0:
        return True

    return False


def isValidAd(rawAd, commonData, specificData):
    title = commonData.get("title")
    description = commonData.get("description")
    mobile = commonData.get("mobile")

    if isEmpty(title):
        return False

    if isEmpty(description):
        return False

    if isEmpty(mobile):
        return False

    if isEmpty(specificData.get("brand_and_model")):
        return False

    return True

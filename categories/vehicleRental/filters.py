def isEmpty(value):
    if value is None:
        return True

    if isinstance(value, str) and value.strip() == "":
        return True

    if isinstance(value, list) and len(value) == 0:
        return True

    return False


def isValidAd(rawAd, commonData, specificData):
    mobile = commonData.get("mobile")

    if isEmpty(mobile):
        return False

    return True

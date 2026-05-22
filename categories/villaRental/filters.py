# def normalizeDescription(description):
#     if not description:
#         return ""

#     return (
#         description.replace("‌", " ")
#         .replace("ي", "ی")
#         .replace("ك", "ک")
#         .replace("\n", " ")
#     )


# def detectInvalidCategory(description):
#     description = normalizeDescription(description)

#     if "اداری" in description:
#         return "edari"

#     if "پیش فروش" in description:
#         return "pishForosh"

#     if "پیشفروش" in description:
#         return "pishForosh"

#     return None


# def isEmpty(value):
#     if value is None:
#         return True

#     if isinstance(value, str) and value.strip() == "":
#         return True

#     if isinstance(value, list) and len(value) == 0:
#         return True

#     return False


# def isValidAd(rawAd, commonData, specificData):
#     title = commonData.get("title")
#     description = commonData.get("description")
#     mobile = commonData.get("mobile")

#     if isEmpty(title):
#         return False

#     if isEmpty(description):
#         return False

#     if isEmpty(mobile):
#         return False

#     invalidCategory = detectInvalidCategory(description)

#     if invalidCategory == "edari":
#         return False

#     if invalidCategory == "pishForosh":
#         return False

#     area = specificData.get("area", 0)
#     year = specificData.get("year", 0)

#     if not area or int(area) == 0:
#         return False

#     if not year or int(year) == 0:
#         return False

#     return True


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

    if "mobile" in commonData and isEmpty(mobile):
        return False

    return True

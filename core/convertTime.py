import jdatetime
from unidecode import unidecode


def convertDate(date):
    temp = date.split(" ")
    dd = unidecode(temp[0])
    mm = temp[1]
    yy = unidecode(temp[2])

    match mm:
        case "فروردین":
            mm = 1
        case "اردیبهشت":
            mm = 2
        case "خرداد":
            mm = 3
        case "تیر":
            mm = 4
        case "مرداد":
            mm = 5
        case "شهریور":
            mm = 6
        case "مهر":
            mm = 7
        case "آذر":
            mm = 8
        case "آبان":
            mm = 9
        case "دی":
            mm = 10
        case "بهمن":
            mm = 11
        case "اسفند":
            mm = 12

    gregorian_date = jdatetime.date(int(yy), int(mm), int(dd)).togregorian()
    return gregorian_date

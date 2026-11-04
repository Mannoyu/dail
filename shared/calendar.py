from datetime import date

from chinese_calendar import is_workday as cn_workday


def is_workday(day: date, calendar: str) -> bool:
    # Out-of-range holiday data must fail explicitly; never silently call a holiday a workday.
    return bool(cn_workday(day)) if calendar == "CN" else day.weekday() < 5

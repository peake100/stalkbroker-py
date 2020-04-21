import datetime
import pytz
import discord
from typing import Optional

from stalkbroker import models


ONE_DAY: datetime.timedelta = datetime.timedelta(days=1)


def parse_timezone(value: str) -> datetime.tzinfo:
    value = value.lower()
    if value == "pst":
        return pytz.timezone("US/Pacific")
    elif value == "est":
        return pytz.timezone("US/Eastern")
    elif value == "cst":
        return pytz.timezone("US/Central")

    return pytz.timezone(value)


def parse_date_arg(
    message: discord.Message, date: str, user_tz: datetime.tzinfo
) -> datetime.date:
    local_time = _message_local_datetime(message, user_tz)

    date_split = date.split("/")

    try:
        month = int(date_split[0])
        day = int(date_split[1])
    except IndexError:
        raise ValueError(f"'{date}' is not a properly formatted date")

    return datetime.date(year=local_time.year, month=month, day=day)


def _message_local_datetime(
    message: discord.Message, user_tz: datetime.tzinfo
) -> datetime.datetime:
    return message.created_at.replace(tzinfo=datetime.timezone.utc).astimezone(user_tz)


def previous_sunday(anchor_date: datetime.date) -> datetime.date:
    """
    Finds the date of the mose recent sunday. Used for calculating the date that turnips
    were purchased on.
    """

    i = 1
    candidate_date = anchor_date
    while True:
        i -= 1

        if candidate_date.weekday() == 6:
            break

        candidate_date = candidate_date - ONE_DAY

    return candidate_date


def deduce_date(
    message: discord.Message, user_tz: datetime.tzinfo, date_arg: Optional[str] = None
) -> datetime.date:
    if date_arg is not None:
        return parse_date_arg(message, date_arg, user_tz)
    else:
        return _message_local_datetime(message, user_tz).date()


def deduce_am_pm(
    message: discord.Message, user_tz: datetime.tzinfo, am_pm_arg: Optional[str]
) -> models.TimeOfDay:
    if am_pm_arg is not None:
        return models.TimeOfDay.from_str(am_pm_arg)

    msg_time = _message_local_datetime(message, user_tz)

    if msg_time.hour <= 12:
        return models.TimeOfDay.AM
    else:
        return models.TimeOfDay.PM

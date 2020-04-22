import datetime
import pytz
import discord
from typing import Optional

from stalkbroker import models


ONE_DAY: datetime.timedelta = datetime.timedelta(days=1)


def serialize_date(date: datetime.date) -> datetime.datetime:
    return datetime.datetime.combine(date, datetime.time())


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
    local_time = get_message_local_dt(message, user_tz)

    date_split = date.split("/")

    try:
        month = int(date_split[0])
        day = int(date_split[1])
    except IndexError:
        raise ValueError(f"'{date}' is not a properly formatted date")

    return datetime.date(year=local_time.year, month=month, day=day)


def get_message_local_dt(
    message: discord.Message, user_tz: datetime.tzinfo
) -> datetime.datetime:
    return message.created_at.replace(tzinfo=datetime.timezone.utc).astimezone(user_tz)


def is_price_phase(
    local_dt: datetime.datetime,
    phase_date: datetime.date,
    phase_time_of_day: models.TimeOfDay,
) -> bool:
    """Returns whether ``local_dt`` is within the sale phase of a given day/tim"""

    if local_dt.date() != phase_date:
        # If the two dates are different, then its false out of the gate
        return False
    elif local_dt.weekday() == 6:
        # There is only one phase on sunday, so if it's a sunday then we are a match
        return True
    elif phase_time_of_day is models.TimeOfDay.AM:
        # Otherwise if we're checking an AM phase, if we are before 12:00, then we are
        # g2g
        return local_dt.hour < 12
    else:
        # And finally if we are checking of PM, see if it is after 12:00
        return local_dt.hour > 12


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
        return get_message_local_dt(message, user_tz).date()


def deduce_am_pm(
    message: discord.Message, user_tz: datetime.tzinfo, am_pm_arg: Optional[str]
) -> models.TimeOfDay:
    if am_pm_arg is not None:
        return models.TimeOfDay.from_str(am_pm_arg)

    msg_time = get_message_local_dt(message, user_tz)

    if msg_time.hour <= 12:
        return models.TimeOfDay.AM
    else:
        return models.TimeOfDay.PM

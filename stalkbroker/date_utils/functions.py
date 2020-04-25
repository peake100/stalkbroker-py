import datetime
import pytz
import discord.ext.commands
from typing import Optional, Tuple

from stalkbroker import models, errors


ONE_DAY: datetime.timedelta = datetime.timedelta(days=1)
SUNDAY = 6


def validate_price_period(
    date: datetime.date, time_of_day: Optional[models.TimeOfDay]
) -> None:
    """
    Validates that a date / time of day combo as valid.

    :param date: date value.
    :param time_of_day: AM / PM.

    :raises ValueError: if this is not a sunday and time_of_day is ``None``.
    """
    if date.weekday() != SUNDAY and time_of_day is None:
        raise ValueError("No time of day given for non-sunday price period")


def serialize_date(date: datetime.date) -> datetime.datetime:
    """
    Serialize a date for pymongo.

    :param date: date to serialize.

    Mongodb does not have a date type, only a datetime type, so we are going to
    make a datetime witt a 00:00:00:00 time to store.

    :returns: datetime value for pymongo.
    """
    return datetime.datetime.combine(date, datetime.time())


def parse_timezone_arg(value: str) -> pytz.BaseTzInfo:
    """Parse a timezone argument supplied by a user."""
    value = value.lower()
    if value == "pst":
        return pytz.timezone("US/Pacific")
    elif value == "est":
        return pytz.timezone("US/Eastern")
    elif value == "cst":
        return pytz.timezone("US/Central")

    return pytz.timezone(value)


def _parse_date_arg_core(
    ctx: discord.ext.commands.Context, date_arg: str, user_tz: pytz.BaseTzInfo
) -> datetime.date:
    """
    Core logic for parsing a date argument.

    :param ctx: message context passed in by discord.py to the calling command.
    :param date_arg: date argument supplied by the user.
    :param user_tz: the local timezone of the user.

    :returns: parsed date.

    :raises ValueError: if a non-existent date has been passed.
    """

    local_time = get_context_local_dt(ctx, user_tz)

    date_split = date_arg.split("/")

    month = int(date_split[0])
    day = int(date_split[1])

    has_year_arg = False
    try:
        year = int(date_split[2])
    except IndexError:
        year = local_time.year
    else:
        has_year_arg = True

    date = datetime.date(year=year, month=month, day=day)

    # If this is today or a day from the past, then we can return
    if not date > local_time.date():
        return date

    if has_year_arg:
        # If the user specified a future year, then we need to raise an error
        raise errors.FutureDateError(ctx=ctx, bad_value=date_arg)
    else:
        # Otherwise we can assume they meant the last valid date rather than a future
        # date, and back the value up by a year
        return date.replace(year=date.year - 1)


def _parse_date_arg(
    ctx: discord.ext.commands.Context, date_arg: str, user_tz: pytz.BaseTzInfo
) -> datetime.date:
    """
    Parse a datetime argument into a date.

    :param ctx: message context passed in by discord.py to the calling command.
    :param date_arg: date argument supplied by the user.
    :param user_tz: the local timezone of the user.

    :returns: the parsed date

    :raises ImaginaryDateError: if a non-existent date has been passed.
    """
    try:
        return _parse_date_arg_core(ctx, date_arg, user_tz)
    except ValueError:
        raise errors.ImaginaryDateError(ctx=ctx, bad_value=date_arg)


def get_context_local_dt(
    ctx: discord.ext.commands.Context, user_tz: pytz.BaseTzInfo
) -> datetime.datetime:
    """
    Convert the command context's utc message creation time to the users local time.

    :param ctx: message context passed in by discord.py to the calling command.
    :param user_tz: the timezone of the user.

    :return: local time for the user.
    """
    message: discord.Message = ctx.message
    return message.created_at.astimezone(user_tz)


def is_price_period(
    local_dt: datetime.datetime,
    price_date: datetime.date,
    price_time_of_day: Optional[models.TimeOfDay],
) -> bool:
    """
    Returns whether ``local_dt`` is within the sale period described by ``price_date``
    and ``price_time_of_day``.

    :param local_dt: the user's local time of day.
    :param price_date: the date this price occurred on.
    :param price_time_of_day: the time of day (AM/PM) the price occured on.

    :return: True if ``local_dt`` falls within the price period.
    """

    if local_dt.date() != price_date:
        # If the two dates are different, then its false out of the gate
        return False
    elif local_dt.weekday() == 6:
        # There is only one phase on sunday, so if it's a sunday then we are a match
        return True
    elif price_time_of_day is models.TimeOfDay.AM:
        # Otherwise if we're checking an AM phase, if we are before 12:00, then we are
        # g2g
        return local_dt.hour < 12
    else:
        # And finally if we are checking of PM, see if it is after 12:00
        return local_dt.hour > 12


def previous_sunday(anchor_date: datetime.date) -> datetime.date:
    """
    Finds the date of the mose recent sunday.

    :param anchor_date: the date to get the preceding sunday from.

    Used for calculating the date that turnips were purchased on.

    :returns: the sunday preceding (or on) this date.
    """
    if isinstance(anchor_date, datetime.datetime):
        anchor_date = anchor_date.date()

    i = 1
    candidate_date = anchor_date
    while True:
        i -= 1

        if candidate_date.weekday() == SUNDAY:
            break

        candidate_date = candidate_date - ONE_DAY

    return candidate_date


def deduce_price_date(
    ctx: discord.ext.commands.Context,
    date_arg: Optional[str],
    user_tz: pytz.BaseTzInfo,
) -> datetime.date:
    """
    Extract a date from a message datetime or arguments.

    :param ctx: message context passed in by discord.py to the calling command.
    :param date_arg: the date argument passed in by the user.
    :param user_tz: the user's local timezone

    :returns: the datetime to use for a ticker update / fetch

    :raises ImaginaryDateError: if a non-existent date has been passed.
    """
    if date_arg is not None:
        return _parse_date_arg(ctx, date_arg, user_tz)
    else:
        return get_context_local_dt(ctx, user_tz).date()


def _deduce_price_time_of_day(
    ctx: discord.ext.commands.Context,
    time_of_day_arg: Optional[str],
    price_date: datetime.date,
    user_tz: pytz.BaseTzInfo,
) -> Optional[models.TimeOfDay]:
    """Like deduce_price_date, but deducing the time of day (AM/PM)"""
    if price_date.weekday() == SUNDAY:
        return None

    if time_of_day_arg is not None:
        return models.TimeOfDay.from_str(time_of_day_arg)

    msg_time = get_context_local_dt(ctx, user_tz)

    if msg_time.hour <= 12:
        return models.TimeOfDay.AM
    else:
        return models.TimeOfDay.PM


def deduce_price_period(
    ctx: discord.ext.commands.Context,
    date_arg: Optional[str],
    time_of_day_arg: Optional[str],
    user_tz: pytz.BaseTzInfo,
) -> Tuple[datetime.date, Optional[models.TimeOfDay]]:
    """
    Extract a price period from a message datetime or arguments.

    :param ctx: message context passed in by discord.py to the calling command.
    :param date_arg: the date argument passed in by the user.
    :param time_of_day_arg: the time of day (AM/PM) argument passed in by the user.
    :param user_tz: the user's local timezone

    :returns: the date, time of day to use for ticker updates or fetches.

    :raises ImaginaryDateError: if a non-existent date has been passed.
    """

    # Figure out if we are using the message date or the date user argument
    date = deduce_price_date(ctx, date_arg, user_tz)

    # If we are trying to get the price period for a non-sunday then we need to figure
    # out the price period
    if date.weekday() != SUNDAY:

        # If the user has not supplied a time of day, but is updating a previous date,
        # then we can't know whether it is a morning or afternoon price and have to
        # raise an error
        if not time_of_day_arg and date != get_context_local_dt(ctx, user_tz).date():
            raise errors.TimeOfDayRequiredError(ctx)

        # Otherwise figure out whether to use the message time of day or a supplied
        # argument
        time_of_day = _deduce_price_time_of_day(
            ctx=ctx, time_of_day_arg=time_of_day_arg, price_date=date, user_tz=user_tz
        )
        return date, time_of_day
    else:
        # If it's sunday, we don't need an AM / PM
        return date, None

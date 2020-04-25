import discord.ext.commands
import datetime
import pytz
from typing import Optional


from stalkbroker import models, date_utils, ac_names


from ._formatting import MESSAGE_DATE_FORMAT


# All the functions to generate confirmation messages sent back when a command has
# been executed successfully.


def confirmation_bulletins_channel(user: discord.User) -> str:
    """
    Confirmation message for setting the bulletin channel of a server.

    :param user: The discord user who invoked the command.

    :returns: the formatted message.
    """
    return (
        f"Noted, {user.mention}! We'll ring the bell here when there's news about"
        f" bells out there."
    )


def confirmation_timezone(user: discord.User, tz: pytz.BaseTzInfo) -> str:
    """
    Confirmation message for setting the local timezone for a user.

    :param user: The discord user who invoked the command.
    :param tz: The timezone.

    :returns: the formatted message.
    """
    return (
        f"I've made a note, {user.mention}! "
        f"You're growing your portfolio on {tz.zone} time"
    )


def confirmation_ticker_update(
    user: discord.User,
    price: int,
    price_date: datetime.date,
    price_time_of_day: Optional[models.TimeOfDay],
    message_datetime_local: datetime.datetime,
) -> str:
    """
    Confirmation message for updating a ticker with a new bell price.

    :param user: The user who's island this price was on.
    :param price: The new turnip price.
    :param price_date: The date this price is / was offered.
    :param price_time_of_day: The time of day (AM/PM) this price is / was offered.
    :param message_datetime_local: The local datetime of the message.

    :returns: the formatted message.
    """

    vendor: str
    sale_type: str

    date_utils.validate_price_period(price_date, price_time_of_day)

    price_time = price_date.strftime(MESSAGE_DATE_FORMAT)

    if price_date.weekday() == date_utils.SUNDAY:
        vendor = ac_names.DAISY_MAE + "'s"
        sale_type = "sale price"
    else:
        # This has been validated so we can do a type assertion here for mypy
        assert price_time_of_day is not None
        vendor = ac_names.THE_NOOKS + "'"
        sale_type = "offer"
        price_time = f"{price_time} ({price_time_of_day.name})"

    message = (
        f"Great, {user.mention}! I'll add {vendor} {sale_type} of {price} bells on"
        f" {price_time} to you island's historical data"
    )

    if date_utils.is_price_period(
        message_datetime_local, price_date, price_time_of_day,
    ):
        message += " and alert everyone to this exciting opportunity!"
    else:
        message += "."

    return message

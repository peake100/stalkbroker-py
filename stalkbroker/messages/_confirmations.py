import discord
import datetime


from stalkbroker import models, date_utils, ac_names


from ._formatting import MESSAGE_DATE_FORMAT


def confirmation_timezone(user: discord.User, tz: datetime.tzinfo) -> str:
    return (
        f"I've made a note, {user.mention}! "
        f"You're growing your portfolio on {tz.tzname(None)} time"
    )


def confirmation_ticker_update(
    user: discord.User,
    price: int,
    price_date: datetime.date,
    price_time_of_day: models.TimeOfDay,
    message_datetime_local: datetime.datetime,
) -> str:
    vendor: str
    sale_type: str

    if price_date.weekday() == 6:
        vendor = ac_names.DAISY_MAE + "'s"
        sale_type = "sale price"
    else:
        vendor = ac_names.THE_NOOKS + "'"
        sale_type = "offer"

    message = (
        f"Great, {user.mention}! I'll add {vendor} {sale_type} of {price} bells on"
        f" {price_date.strftime(MESSAGE_DATE_FORMAT)} to you island's historical data"
    )

    if date_utils.is_price_phase(
        message_datetime_local, price_date, price_time_of_day,
    ):
        message += " and alert everyone to this exciting opportunity!"
    else:
        message += "."

    return message

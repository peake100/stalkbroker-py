import datetime
import discord
from typing import Optional

from stalkbroker import models, ac_names, date_utils

from ._formatting import bulletin


def _bulletin_nook_price_update(
    discord_user: discord.User,
    price: int,
    date_local: datetime.date,
    time_of_day: models.TimeOfDay,
) -> str:
    """Generates a bulletin message for the nooks' buying price."""
    info = {
        "market": discord_user.mention,
        f"{ac_names.THE_NOOKS}' offer": f"{price}",
        "date": date_local,
        "period": time_of_day.name,
    }

    return bulletin("the market is moving", info)


def bulletin_price_update(
    discord_user: discord.User,
    price: int,
    date_local: datetime.date,
    time_of_day: Optional[models.TimeOfDay],
) -> str:
    """
    Creates the bulletin message to send out.

    :param discord_user: The user who's island this bulletin is for.
    :param price: The current price on offer for selling or buying.
    :param date_local: The local date of the user.
    :param time_of_day: The local AM / PM of the user.
    """
    if date_local.weekday() == date_utils.SUNDAY:
        raise ValueError("bulletins are not sent for buy prices")

    if time_of_day is None:
        raise ValueError("Must supply time of day for nook price bulletin.")

    return _bulletin_nook_price_update(discord_user, price, date_local, time_of_day)

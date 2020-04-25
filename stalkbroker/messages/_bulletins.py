import datetime
from typing import Optional

from stalkbroker import models, ac_names, date_utils

from ._formatting import bulletin


def _bulletin_daisey_mae_price_update(
    display_name: str, price: int, date_local: datetime.date,
) -> str:
    """Generates a bulletin message for daisey's buying price."""
    info = {
        "market": display_name,
        f"{ac_names.DAISY_MAE}'s deal": price,
        "date": date_local,
    }
    bulletin_text = bulletin("investment opportunity available", info)

    # Because we use the title formatting function, 'Daisy Mae'S', so we need to replace
    # that capital possessive s with a lower case one.
    return bulletin_text.replace("'S ", "'s ", 1)


def _bulletin_nook_price_update(
    display_name: str,
    price: int,
    date_local: datetime.date,
    time_of_day: models.TimeOfDay,
) -> str:
    """Generates a bulletin message for the nooks' buying price."""
    info = {
        "market": display_name,
        f"{ac_names.THE_NOOKS}' offer": f"{price}",
        "date": date_local,
        "period": time_of_day.name,
    }
    return bulletin("the market is moving", info)


def bulletin_price_update(
    display_name: str,
    price: int,
    date_local: datetime.date,
    time_of_day: Optional[models.TimeOfDay],
) -> str:
    """
    Creates the bulletin message to send out.

    :param display_name: The display name of the user who's island this bulletin is
        for.
    :param price: The current price on offer for selling or buying.
    :param date_local: The local date of the user.
    :param time_of_day: The local AM / PM of the user.
    """
    if date_local.weekday() == date_utils.SUNDAY:
        return _bulletin_daisey_mae_price_update(display_name, price, date_local)
    else:
        if time_of_day is None:
            raise ValueError("Must supply time of day for nook price bulletin.")
        return _bulletin_nook_price_update(display_name, price, date_local, time_of_day)

import datetime

from stalkbroker import models, ac_names

from ._formatting import bulletin


def bulletin_daisey_mae_price_update(
    display_name: str, price: int, date_local: datetime.date,
) -> str:
    info = {
        "market": display_name,
        f"{ac_names.DAISY_MAE}'s deal": price,
        "date": date_local,
    }
    return bulletin("investment opportunity available", info)


def bulletin_nook_price_update(
    display_name: str,
    price: int,
    date_local: datetime.date,
    time_of_day: models.TimeOfDay,
) -> str:
    info = {
        "market": display_name,
        f"{ac_names.THE_NOOKS}' offer": f"{price}",
        "date": date_local,
        "period": time_of_day.name,
    }
    return bulletin("the market is moving", info)

import datetime
from typing import Dict, Any, Union

from stalkbroker import models

from ._formatting import format_report


def report_ticker(
    display_name: str,
    week_of: datetime.date,
    ticker: models.Ticker,
    message_date_local: datetime.date,
) -> str:
    info: Dict[str, Any] = {
        "Market": display_name,
        "Week of": week_of.strftime("%m/%d"),
    }

    if ticker.purchase_price is None:
        info["Daisey's Deal"] = "?"
    else:
        info["Daisey's Deal"] = ticker.purchase_price

    for phase in ticker:
        if phase.date > message_date_local:
            break

        if phase.price is None:
            price_report: Union[str, int] = "?"
        else:
            price_report = phase.price

        info[phase.name] = price_report

    return format_report("market report", info=info)

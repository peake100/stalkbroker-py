import datetime
import discord
from typing import Dict, Any, Union

from stalkbroker import models
from protogen.stalk_proto import models_pb2 as backend

from ._formatting import format_report
from ._common import forecast_info_common


def report_ticker(
    display_name: str, ticker: models.Ticker, message_time_local: datetime.datetime,
) -> str:
    """
    Build and format a ticker report to send back to discord.

    :param display_name: the display name of the user who's island is being reported on.
    :param ticker: the price ticker to report.
    :param message_time_local: the local time the request message was sent.

    :returns: formatted report.
    """

    info: Dict[str, Any] = {
        "Market": display_name,
        "Week of": ticker.week_of.strftime("%m/%d/%y"),
    }

    if ticker.purchase_price is None:
        info["Daisey's Deal"] = "?"
    else:
        info["Daisey's Deal"] = ticker.purchase_price

    for phase in ticker:
        # We don't need to report prices that haven't happened yet
        if phase.date > message_time_local.date():
            break

        # We don't need to report prices for the PM of a day if it is currently the AM
        # of that day.
        if (
            phase.date == message_time_local.date()
            and phase.time_of_day is models.TimeOfDay.PM
            and message_time_local.hour < 12
        ):
            break

        if phase.price is None:
            price_report: Union[str, int] = "?"
        else:
            price_report = phase.price

        info[phase.name] = price_report

    return format_report("market report", info=info)


def report_forecast(
    discord_user: discord.User,
    ticker: models.Ticker,
    forecast: backend.Forecast,
    current_period: int,
) -> str:
    info = forecast_info_common(discord_user, ticker, forecast, current_period)
    return format_report("MARKET FORECAST", info)

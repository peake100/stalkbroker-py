import datetime
import discord
from typing import Dict, Any, Union, Optional

from stalkbroker import models
from protogen.stalk_proto import models_pb2 as backend

from ._formatting import format_report, format_chance, format_period_count


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
    most_likely: Optional[backend.PotentialPattern] = None
    big_spike: Optional[backend.PotentialPattern] = None
    small_spike: Optional[backend.PotentialPattern] = None

    pattern: backend.PotentialPattern
    for pattern in forecast.patterns:
        if most_likely is None or pattern.chance > most_likely.chance:
            most_likely = pattern

        if pattern.pattern == backend.PricePatterns.BIGSPIKE:
            big_spike = pattern
        elif pattern.pattern == backend.PricePatterns.SMALLSPIKE:
            small_spike = pattern

    assert most_likely is not None
    assert small_spike is not None
    assert big_spike is not None

    has_big = (
        len(big_spike.potential_weeks) > 0 and current_period <= forecast.spikes.big.end
    )
    has_small = (
        len(small_spike.potential_weeks) > 0
        and current_period <= forecast.spikes.small.end
    )
    has_any = has_big or has_small

    info = {
        "market": discord_user.mention,
        "Week of": ticker.week_of.strftime("%m/%d/%y"),
        "likely high": (
            f"{most_likely.prices_future.max} ({format_chance(most_likely.chance)})"
        ),
    }

    if has_big:
        info[
            "big spike"
        ] = f"{big_spike.prices_future.max} ({format_chance(big_spike.chance)})"

    if has_small:
        info[
            "small spike"
        ] = f"{small_spike.prices_future.max} ({format_chance(small_spike.chance)})"

    if has_any and current_period <= forecast.spikes.any.end:
        spike_earliest = forecast.spikes.any.start - current_period
        spike_earliest = max(spike_earliest, 0)
        info["earliest spike"] = format_period_count(spike_earliest)

    return format_report("MARKET FORECAST", info)

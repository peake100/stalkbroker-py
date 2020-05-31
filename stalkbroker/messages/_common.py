import discord
from typing import Dict, Any, Optional

from stalkbroker import models
from protogen.stalk_proto import models_pb2 as backend

from ._formatting import format_period_count, format_chance


def forecast_info_common(
    discord_user: discord.User,
    ticker: models.Ticker,
    forecast: backend.Forecast,
    current_period: int,
) -> Dict[str, Any]:
    """Used to make info form for both forecast reports and forecast bulletins."""
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

    likely_average_float = (
        most_likely.prices_future.max + most_likely.prices_future.guaranteed
    ) / 2
    likely_average = int(round(likely_average_float, 0))

    info: Dict[str, Any] = {
        "market": discord_user.mention,
        "week of": ticker.week_of.strftime("%m/%d/%y"),
        "heat": forecast.heat,
        "likely average": f"{likely_average} {format_chance(most_likely.chance)}",
    }

    if has_any and current_period <= forecast.spikes.any.end:
        spike_earliest = forecast.spikes.any.start - current_period
        spike_earliest = max(spike_earliest, 0)
        info["soonest spike"] = format_period_count(spike_earliest)

    return info

import discord.ext.commands
import dataclasses
import datetime
import grpclib.exceptions
from typing import Tuple, Optional

from protogen.stalk_proto import models_pb2 as backend

from stalkbroker import models, errors, date_utils
from ._bot import STALKBROKER
from ._consts import PATTERN_TO_BACKEND


@dataclasses.dataclass
class MessageTickerInfo:
    discord_user: discord.User
    stalk_user: models.User
    user_time: datetime.datetime
    ticker: models.Ticker


async def fetch_message_ticker_info(
    ctx: discord.ext.commands.Context, date_arg: Optional[str]
) -> MessageTickerInfo:
    message: discord.Message = ctx.message

    # If another user is mentioned in the message, we want to pull their ticker instead,
    # that way you can look up other's prices.
    try:
        discord_user: discord.User = next(m for m in message.mentions)
    except StopIteration:
        discord_user = message.author

    stalk_user = await STALKBROKER.db.fetch_user(discord_user, message.guild)
    # If we don't know the user's timezone, then we won't be able to adjust the message
    # time reliably.
    if stalk_user.timezone is None:
        raise errors.UnknownUserTimezoneError(ctx, discord_user)

    # Get the time of the message adjusted for the user's timezone
    message_time_local = date_utils.get_context_local_dt(ctx, stalk_user.timezone)

    # Decide whether to use the message time or a date included in the command
    requested_date = date_utils.deduce_price_date(ctx, date_arg, stalk_user.timezone)

    week_of = date_utils.previous_sunday(requested_date)
    user_ticker = await STALKBROKER.db.fetch_ticker(stalk_user, week_of)

    result = MessageTickerInfo(
        discord_user=discord_user,
        stalk_user=stalk_user,
        user_time=message_time_local,
        ticker=user_ticker,
    )

    return result


def current_period_for_backend(user_time_local: datetime.datetime) -> int:
    """Get the current period for a for backend operations."""
    current_period = models.Ticker.phase_from_datetime(user_time_local)
    if current_period is None:
        current_period = 0
    return current_period


async def get_forecast_from_backend(
    ctx: discord.ext.commands.Context, info: MessageTickerInfo
) -> Tuple[backend.Ticker, backend.Forecast]:
    """Gets forecast from backend based on user info."""
    # Now we need to submit that to the forecasting service
    current_period = current_period_for_backend(info.user_time)

    previous_pattern = await STALKBROKER.db.fetch_previous_pattern(
        user=info.stalk_user, week_of_current=info.ticker.week_of,
    )
    previous_pattern_backend = PATTERN_TO_BACKEND[previous_pattern]

    backend_ticker = info.ticker.to_backend(
        previous_pattern=previous_pattern_backend, current_period=current_period,
    )

    try:
        island_forecast = await STALKBROKER.client_forecaster.ForecastPrices(
            backend_ticker,
        )
    except grpclib.exceptions.GRPCError as error:
        raise errors.BackendError(ctx, error)

    return backend_ticker, island_forecast

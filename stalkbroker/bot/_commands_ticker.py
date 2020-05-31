import discord.ext.commands
import re
import asyncio
import datetime
import dataclasses
from typing import Optional, Tuple, List, Coroutine

from protogen.stalk_proto import models_pb2 as backend
from stalkbroker import date_utils, errors, messages, models, constants

from ._bot import STALKBROKER
from ._commands_utils import confirm_execution
from ._consts import PATTERN_FROM_BACKEND
from ._common import (
    fetch_message_ticker_info,
    get_forecast_from_backend,
    get_forecast_chart_from_backend,
    MessageTickerInfo,
)

_IMPORT_HELPER = None


# One nice thing about the data we need to get to update the ticker, is each argument
# has a unique format. We can make sense of '$ticker 112 AM 4/14' just as easily as
# '$ticker 4/14 AM 112'. In both It's easy to deduce that We are saying: 'price of
# bells in the morning on April the 14th was 112 bells'. We can even add a user mention
# and still not run into format collisions.
#
# Because we don't HAVE to know the order of these values to deduce which is which,
# lets make the experience for our end users a little easier by not enforcing argument
# order. Below are the REGEXES we are going to match against to work out which argument
# is which piece of data.
REGEX_ARG_PRICE = re.compile(r"\d+")
REGEX_ARG_DATE = re.compile(r"\d+/\d+(/\d+)?")
REGEX_ARG_TIME_OF_DAY = re.compile(r"AM|PM", flags=re.IGNORECASE)


@dataclasses.dataclass
class BulletinInfo(MessageTickerInfo):
    """Holds additional information for sending bulletins over MessageTickerInfo."""

    ctx: discord.ext.commands.Context
    """The message context."""
    price: int
    """The current price on the user's island."""
    price_date: datetime.date
    """The date this price belongs to."""
    price_time_of_day: Optional[models.TimeOfDay]
    """The time of day this price belongs to."""
    ticker_backend: backend.Ticker
    """The backend ticker object for this bulletin."""
    forecast: backend.Forecast
    """The forecast for this user."""


def get_bulletin_role(server: models.Server) -> discord.Role:
    guild: discord.Guild = STALKBROKER.get_guild(server.discord_id)

    bulletin_role: discord.Role = discord.utils.get(
        guild.roles, name=constants.BULLETIN_ROLE
    )
    return bulletin_role


def build_ticker_bulletin(server: models.Server, info: BulletinInfo,) -> Optional[str]:
    # If the price is bellow the minimum threshold for the server, then we can abort.
    if info.price < server.bulletin_minimum:
        return None

    # No price bulletins on Sunday.
    if info.price_date.weekday() == date_utils.SUNDAY:
        return None

    # We don't need to send an update if we are not updating the current price period
    if not date_utils.is_price_period(
        info.user_time, info.price_date, info.price_time_of_day
    ):
        return None

    assert info.price_time_of_day is not None

    bulletin = messages.bulletin_price_update(
        discord_user=info.discord_user,
        price=info.price,
        date_local=info.price_date,
        time_of_day=info.price_time_of_day,
    )
    return bulletin


async def build_forecast_bulletin(
    server: models.Server, info: BulletinInfo,
) -> Tuple[Optional[str], Optional[discord.File]]:
    """Returns bulletin text and forecast chart file embed if bulletin required."""
    heat = info.forecast.heat
    max_future = info.forecast.prices_future.max
    requirement = server.bulletin_minimum

    # If the heat or max price are below the serve threshold, do not send
    if heat < server.bulletin_minimum or max_future < requirement:
        return None, None

    # send a reaction to the client to indicate we are sending a forecast for this
    # ticker. We'll await this simultaneously with the request to get the chart.
    message: discord.Message = info.ctx.message
    react_coro = message.add_reaction(messages.REACTIONS.CONFIRM_FORECAST)

    # -1 values break the forecasting service, but are needed by the charting service
    # for cursor placement on sundays, so check here if we need to tweak the backend
    # ticker.
    if info.user_time.weekday() == date_utils.SUNDAY:
        info.ticker_backend.current_period = -1

    forecast_coro = get_forecast_chart_from_backend(
        info.ctx, info, info.ticker_backend, info.forecast,
    )

    # await both our forecast confirmation to the user and the chart request.
    chart_file: discord.File
    _, chart_file = await asyncio.gather(react_coro, forecast_coro)

    bulletin = messages.bulletin_forecast(
        info.discord_user,
        ticker=info.ticker,
        forecast=info.forecast,
        current_period=info.ticker_backend.current_period,
    )

    return bulletin, chart_file


async def send_bulletins_to_server(
    server: discord.Guild, bulletin_info: BulletinInfo,
) -> None:
    """
    Send a price update bulletin to the server.

    :param server: the discord server we need to send the bulletin to.
    :param bulletin_info: information required to send the bulletins.

    :raises NoBulletinChannelError: When the server does not have the channel it wants
        to receive bulletins on set.
    """
    server_info = await STALKBROKER.db.fetch_server(server)

    # If the server has not set a bulletin channel, raise an error to be returned to
    # the user.
    if server_info.bulletin_channel is None:
        raise errors.NoBulletinChannelError(ctx=bulletin_info.ctx, guild=server)

    bulletin_channel: discord.TextChannel = STALKBROKER.get_channel(
        server_info.bulletin_channel,
    )
    if bulletin_channel is None:
        raise errors.NoBulletinChannelError(ctx=bulletin_info.ctx, guild=server)

    # Get the bulletin role
    bulletin_role = get_bulletin_role(server_info)

    # Set the default file value to none
    file: Optional[discord.File] = None
    bulletin_text = build_ticker_bulletin(server_info, bulletin_info)

    # If there is no price bulletin, check for a forecast bulletin
    if bulletin_text is None:
        bulletin_text, file = await build_forecast_bulletin(server_info, bulletin_info)

    if bulletin_text is None:
        return

    bulletin = f"{bulletin_text}\n{bulletin_role.mention}"

    await bulletin_channel.send(bulletin, file=file)


async def send_bulletins_to_all_user_servers(bulletin_info: BulletinInfo,) -> None:
    """
    For a given user, send a price update bulletin to every server they are a part of
    that this bot is invited to.

    :param bulletin_info: All data needed to send server bulletins.
    """

    # Build a list of bulletins to send out.
    bulletin_coros: List[Coroutine] = list()
    for server_discord_id in bulletin_info.stalk_user.servers:
        server = STALKBROKER.get_guild(server_discord_id)
        # This user might be part of a server we don't have access to.
        if server is None:
            continue

        this_coro = send_bulletins_to_server(server, bulletin_info)
        bulletin_coros.append(this_coro)

    # Asynchronously send them all.
    done, _ = await asyncio.wait(bulletin_coros)

    # Check if we had any errors when sending (such as a server not having a bulletin
    # channel set)
    error_list: List[BaseException] = list()

    for future in done:
        try:
            future.result()
        except BaseException as error:
            # If there was an error, add it to the list
            error_list.append(error)

    if error_list:
        # If there were errors, raise them wrapped in a BulkResponseError
        raise errors.BulkResponseError(error_list)


def confirmed_pattern_from_forecast(forecast: backend.Forecast) -> models.Patterns:
    p: backend.PotentialPattern
    possible_patterns = [p for p in forecast.patterns if len(p.potential_weeks) > 0]
    if len(possible_patterns) == 1:
        backend_pattern = possible_patterns[0].pattern
    else:
        backend_pattern = backend.UNKNOWN

    return PATTERN_FROM_BACKEND[backend_pattern]


def is_bulletin_possible(bulletin_info: BulletinInfo,) -> bool:
    """CHeck whether a bulletin could go out for ANY server, regardless of settings."""
    # We don't need to send a price for a previous week
    if date_utils.previous_sunday(
        bulletin_info.price_date
    ) != date_utils.previous_sunday(bulletin_info.user_time.date()):
        return False

    # Otherwise let it pass to checking individual server criteria
    return True


async def update_ticker(
    ctx: discord.ext.commands.Context,
    *,
    price: int,
    price_date_arg: Optional[str],
    price_time_of_day_arg: Optional[str],
) -> None:
    """
    Updates the ticker for the given price period and user.

    :param ctx: message context passed in by discord.py to the calling command.
    :param price: the new price.
    :param price_date_arg: the date argument this price occurred on. If none, the
        current date is used.
    :param price_time_of_day_arg: the time of day this price occurred on (AM/PM). If
        none, then the current time of day is used.

    :raises UnknownUserTimezoneError: If the user's timezone is unknown and we cannot
        convert their message time.
    :raises ImaginaryDateError: If the user has specified a date that does not exist.
    :raises FutureDateError: If the user is trying to set the price for a date that
        has not happened yet.
    :raises TimeOfDayRequiredError: If the user has not supplied an AM/PM argument for a
        past date.
    """

    message: discord.Message = ctx.message
    stalk_user = await STALKBROKER.db.fetch_user(message.author, message.guild)

    # If we don't know the users timezone, raise a UnknownUserTimezoneError to warn the
    # user.
    if stalk_user.timezone is None:
        raise errors.UnknownUserTimezoneError(ctx, ctx.author)

    # Next we need to figure our what date and price period to use.
    message_time_local = date_utils.get_context_local_dt(ctx, stalk_user.timezone)

    price_date, price_time_of_day = date_utils.deduce_price_period(
        ctx, price_date_arg, price_time_of_day_arg, stalk_user.timezone,
    )

    week_of = date_utils.previous_sunday(price_date)

    user_ticker = await STALKBROKER.db.update_ticker_price(
        user=stalk_user,
        week_of=week_of,
        price_date=price_date,
        price_time_of_day=price_time_of_day,
        price=price,
    )

    # Now we need to make a forecast and check if we have a confirmed price pattern
    # so that we can update it.
    current_period = user_ticker.phase_from_datetime(message_time_local)
    if current_period is None:
        current_period = 0

    message_info = MessageTickerInfo(
        discord_user=message.author,
        stalk_user=stalk_user,
        price_date=price_date,
        user_time=message_time_local,
        ticker=user_ticker,
        current_period=current_period,
    )
    ticker_backend, forecast = await get_forecast_from_backend(ctx, message_info)

    # Update our weeks price pattern. It will be set as 'UNKNOWN' if there are multiple
    # possible prices.
    price_pattern = confirmed_pattern_from_forecast(forecast)
    await STALKBROKER.db.update_ticker_pattern(stalk_user, week_of, price_pattern)

    # Add confirmation reactions to the original message now that we are done.
    coroutines: List[Coroutine] = list()
    reactions = messages.REACTIONS.price_update_reactions(
        price_date=price_date,
        price_time_of_day=price_time_of_day,
        message_datetime_local=message_time_local,
    )
    confirm_coro = confirm_execution(ctx, reactions)
    coroutines.append(confirm_coro)

    # Get ready to send out bulletins.
    bulletin_info = BulletinInfo(
        ctx=ctx,
        stalk_user=stalk_user,
        discord_user=message.author,
        price=price,
        price_date=price_date,
        price_time_of_day=price_time_of_day,
        ticker=user_ticker,
        ticker_backend=ticker_backend,
        forecast=forecast,
        user_time=message_time_local,
        current_period=current_period,
    )

    # If a bulletin would never go out to any server, we don't need to do anything,
    # otherwise add it to our list of coroutines to execute.
    if is_bulletin_possible(bulletin_info):
        bulletin_coro = send_bulletins_to_all_user_servers(bulletin_info)
        coroutines.append(bulletin_coro)

    await asyncio.gather(*coroutines)


async def fetch_ticker(
    ctx: discord.ext.commands.Context, date_arg: Optional[str]
) -> None:
    """
    Fetches the ticker of a user and sends back a formatted report.

    :param ctx: message context passed in by discord.py to the calling command.
    :param date_arg: the date argument passed by the user for the week they want to
        fetch. If none, the current date will be used. This date does not have to
        match the ticker's ``week_of`` field, but can be any date for that week.

    :raises UnknownUserTimezoneError: If the user's timezone is unknown and we cannot
        convert their message time.
    :raises ImaginaryDateError: If the user has specified a date that does not exist.
    :raises FutureDateError: If the user is trying to set the price for a date that
        has not happened yet.
    """
    info = await fetch_message_ticker_info(ctx, date_arg)

    response = messages.report_ticker(
        display_name=info.discord_user.display_name,
        ticker=info.ticker,
        message_time_local=info.user_time,
    )

    await ctx.send(response)


def _parse_ticker_args(
    *args: str,
) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """
    Figures out which is which user argument is which ticker operation value.

    :returns: date, time-of-day (AM/PM), price
    """
    date_arg: Optional[str] = None
    am_pm: Optional[str] = None
    price: Optional[int] = None

    for arg in args:
        if REGEX_ARG_PRICE.fullmatch(arg):
            price = int(arg)
            continue

        if REGEX_ARG_DATE.fullmatch(arg):
            date_arg = arg
            continue

        if REGEX_ARG_TIME_OF_DAY.fullmatch(arg):
            am_pm = arg

    return date_arg, am_pm, price


@STALKBROKER.command(
    name="ticker",
    help=(
        "<price> <AM/PM> <date> update your turnip price. "
        + "Arguments can be passes in any order. "
        + "If <AM/PM> or <date> arguments are omitted, the current time is used. Call"
        + " without arguments to see your current ticker. Call with another user tagged"
        + " to get their ticker."
    ),
)
async def ticker(ctx: discord.ext.commands.Context, *args: str) -> None:
    """
    Handles responses to the ``'$ticker'`` command.

    :param ctx: message context passed in by discord.py.
    :param args: arguments passed by the user.

    To reduce the amount of typing needed to interact with this bot, both fetching and
    updating the ticker are controlled by this command.

    If a price value is included, this command is interpretted as an update request. If
    no price is included, it is considered a fetch request.

    When date or time of day arguments are omitted, the command assumes that the current
    day / period for the time the message was sent.

    See the Quickstart documentation for examples of how to invoke this command.
    """
    date_arg, time_of_day_arg, price = _parse_ticker_args(*args)

    if price is not None:
        await update_ticker(
            ctx,
            price=price,
            price_date_arg=date_arg,
            price_time_of_day_arg=time_of_day_arg,
        )
    else:
        await fetch_ticker(ctx, date_arg)

import discord.ext.commands
import re
import asyncio
from typing import Optional, Tuple, List, Coroutine

from stalkbroker import date_utils, errors, messages, models

from ._bot import STALKBROKER
from ._commands_utils import confirm_execution


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


async def send_bulletin_to_server(
    ctx: discord.ext.commands.Context, server: discord.Guild, bulletin: str, price: int,
) -> None:
    """
    Send a price update bulletin to the server.

    :param ctx: message context passed in by discord.py to the calling command.
    :param server: the discord server we need to send the bulletin to.
    :param bulletin: the text content to send.
    :param price: the current price.

    :raises NoBulletinChannelError: When the server does not have the channel it wants
        to receive bulletins on set.
    """
    server_info = await STALKBROKER.db.fetch_server(server)

    # If the price is bellow the minimum threshold for the server, then we can abort.
    if price < server_info.bulletin_minimum:
        return

    guild = STALKBROKER.get_guild(server_info.discord_id)
    # If the server has not set a bulletin channel, raise an error to be returned to
    # the user.
    if server_info.bulletin_channel is None:
        raise errors.NoBulletinChannelError(ctx=ctx, guild=guild)

    channel: discord.TextChannel = STALKBROKER.get_channel(server_info.bulletin_channel)
    await channel.send(bulletin)


async def send_bulletins_to_all_user_servers(
    ctx: discord.ext.commands.Context, user: models.User, bulletin: str, price: int,
) -> None:
    """
    For a given user, send a price update bulletin to every server they are a part of
    that this bot is invited to.

    :param ctx: message context passed in by discord.py to the calling command.
    :param user: The stalkbroker user data for the user with the price update.
    :param bulletin: the text content to send.
    :param price: the current price.
    """
    # Build a list of bulletins to send out.
    bulletin_coros: List[Coroutine] = list()
    for server_discord_id in user.servers:
        server = STALKBROKER.get_guild(server_discord_id)
        bulletin_coros.append(send_bulletin_to_server(ctx, server, bulletin, price))

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

    await STALKBROKER.db.update_ticker(
        user=stalk_user,
        week_of=week_of,
        price_date=price_date,
        price_time_of_day=price_time_of_day,
        price=price,
    )

    # Add confirmation reactions to the original message.
    reactions = messages.REACTIONS.price_update_reactions(
        price_date=price_date,
        price_time_of_day=price_time_of_day,
        message_datetime_local=message_time_local,
    )
    await confirm_execution(ctx, reactions)

    if not date_utils.is_price_period(
        message_time_local, price_date, price_time_of_day
    ):
        return

    if price_date.weekday() == date_utils.SUNDAY:
        return

    bulletin = messages.bulletin_price_update(
        discord_user=ctx.author,
        price=price,
        date_local=price_date,
        time_of_day=price_time_of_day,
    )
    await send_bulletins_to_all_user_servers(ctx, stalk_user, bulletin, price)


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

    response = messages.report_ticker(
        display_name=discord_user.display_name,
        ticker=user_ticker,
        message_time_local=message_time_local,
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

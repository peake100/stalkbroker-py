import discord.ext.commands
import re
from typing import Optional, Tuple

from ._bot import STALKBROKER, DB_CONNECTION
from stalkbroker import date_utils, schemas, errors, messages


_IMPORT_HELPER = None


REGEX_DATE_ARG = re.compile(r"\d+/\d+")
REGEX_TIME_OF_DAY_ARG = re.compile(r"AM|PM", flags=re.IGNORECASE)
REGEX_PRICE_ARG = re.compile(r"\d+")


SCHEMA_TICKER_DISPLAY = schemas.Ticker(exclude=["user_id", "week_of"])


async def update_ticker(
    ctx: discord.ext.commands.Context,
    price: int,
    am_pm: Optional[str],
    date: Optional[str],
) -> None:
    """updates a ticker for the given price period"""

    message: discord.Message = ctx.message
    user = await DB_CONNECTION.fetch_user(message.author.id, message.guild.id)

    # If we don't know the users timezone, raise a UnknownUserTimezoneError, and
    # our error handler will take care of the rest
    if user.timezone is None:
        raise errors.UnknownUserTimezoneError(ctx)

    time_of_day = date_utils.deduce_am_pm(message, user.timezone, am_pm)
    date_local = date_utils.deduce_date(message, user.timezone, date)

    week_of = date_utils.previous_sunday(date_local)
    await DB_CONNECTION.update_ticker(user, week_of, date_local, time_of_day, price)

    # If this isn't a sunday, then we are updating a sell price
    if date_local.weekday() != 6:
        response = messages.bulletin_nook_price_update(
            display_name=ctx.author.display_name,
            price=price,
            date_local=date_local,
            time_of_day=time_of_day,
        )
    else:
        # Otherwise we are updating the sunday sell price
        response = messages.bulletin_daisey_mae_price_update(
            display_name=ctx.author.display_name, price=price, date_local=date_local,
        )

    await ctx.send(response)


async def fetch_ticker(ctx: discord.ext.commands.Context, date: Optional[str]) -> None:
    message: discord.Message = ctx.message

    # If another user is mentioned in the message, we want to pull their ticker instead,
    # that way you can look up other's prices.
    if len(message.mentions) > 0:
        # TODO: Error when more than one message
        discord_user: discord.User = message.mentions[0]
    else:
        discord_user = ctx.author

    broker_user = await DB_CONNECTION.fetch_user(discord_user.id, message.guild.id)
    if broker_user.timezone is None:
        raise errors.UnknownUserTimezoneError(ctx)

    # Get the time of the message adjusted for the user's timezone
    message_date_local = date_utils.deduce_date(
        message, user_tz=broker_user.timezone, date_arg=date
    )

    week_of = date_utils.previous_sunday(message_date_local)
    user_ticker = await DB_CONNECTION.fetch_ticker(broker_user, week_of)

    response = messages.report_ticker(
        display_name=ctx.author.display_name,
        week_of=week_of,
        ticker=user_ticker,
        message_date_local=message_date_local,
    )

    await ctx.send(response)


def _parse_ticker_args(
    *args: str,
) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    date_arg: Optional[str] = None
    am_pm: Optional[str] = None
    price: Optional[int] = None

    for arg in args:
        if REGEX_PRICE_ARG.fullmatch(arg):
            price = int(arg)
            continue

        if REGEX_DATE_ARG.fullmatch(arg):
            date_arg = arg
            continue

        if REGEX_TIME_OF_DAY_ARG.fullmatch(arg):
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
    date, am_pm, price = _parse_ticker_args(*args)

    if price is not None:
        await update_ticker(ctx, price, am_pm, date)
    else:
        await fetch_ticker(ctx, date)

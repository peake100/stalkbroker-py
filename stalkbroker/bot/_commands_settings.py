import discord.ext.commands
import pytz.exceptions


from stalkbroker import date_utils, errors, messages
from ._bot import STALKBROKER
from ._commands_utils import confirm_execution, user_change_bulletin_subscription


_IMPORT_HELPER = None


@STALKBROKER.command(
    name="timezone",
    case_insensitive=True,
    help="<zone> Sets the timezone for your user (ie pst)",
)
async def set_user_timezone(ctx: discord.ext.commands.Context, zone_arg: str) -> None:
    """
    Sets a user's local timezone in the database.

    :param ctx: message context passed in by discord.py
    :param zone_arg: the timezone argument passed by the user

    :raises BadTimezoneError: if the ``zone_arg`` is not a valid timezone.
    """
    try:
        converted_tz = date_utils.parse_timezone_arg(zone_arg)
    except pytz.exceptions.UnknownTimeZoneError:
        # If the user has passed a value that pytz doesn't recognize, convert to a
        # stalkbroker error and re-raise.
        raise errors.BadTimezoneError(ctx, zone_arg)
    else:
        # Otherwise update the timezone then send a confirmation.
        await STALKBROKER.db.update_user_timezone(ctx.author, ctx.guild, converted_tz)
        # Let's add a four-o'clock emoji for flavor
        await confirm_execution(ctx, [messages.REACTIONS.CONFIRM_TIMEZONE])


# TODO: put this behind some sort of role check
@STALKBROKER.group(case_insensitive=True, pass_context=True)
async def bulletins(ctx: discord.ext.commands.Context) -> None:
    pass


@bulletins.command(
    name="here", pass_context=True, help="send bulletins to this channel",
)
async def set_bulletins_channel(ctx: discord.ext.commands.Context) -> None:
    """
    Sets the channel a server wishes bulletins to be sent to.

    :param ctx: message context passed in by discord.py. The channel on this context
        is used as the bulletin channel.
    """
    await STALKBROKER.db.server_set_bulletin_channel(ctx.guild, ctx.channel)
    await confirm_execution(ctx, [messages.REACTIONS.CONFIRM_BULLETIN_CHANNEL])


@bulletins.command(
    name="minimum",
    pass_context=True,
    help="set the minimum bell price for a bulletin to be sent to the bulletin channel",
)
async def set_bulletins_minimum(
    ctx: discord.ext.commands.Context, price_minimum: int,
) -> None:
    """
    Sets the channel a server wishes bulletins to be sent to.

    :param ctx: message context passed in by discord.py. The channel on this context
        is used as the bulletin channel.
    :param price_minimum: the minimum price to set for sending a bulletin about it.
    """
    await STALKBROKER.db.server_set_bulletin_minimum(ctx.guild, price_minimum)
    await confirm_execution(ctx, [messages.REACTIONS.CONFIRM_BULLETIN_MINIMUM])


@bulletins.command(
    name="heat",
    pass_context=True,
    help=(
        "set the minimum heat value for a forecast bulletin to be sent to the bulletin"
        " channel"
    ),
)
async def set_bulletins_minimum_heat(
    ctx: discord.ext.commands.Context, heat_minimum: int,
) -> None:
    """
    Sets the channel a server wishes bulletins to be sent to.

    :param ctx: message context passed in by discord.py. The channel on this context
        is used as the bulletin channel.
    :param heat_minimum: the minimum heat score to set for sending a forecast bulletin.
    """
    await STALKBROKER.db.server_set_heat_minimum(ctx.guild, heat_minimum)
    await confirm_execution(ctx, [messages.REACTIONS.CONFIRM_HEAT_MINIMUM])


@bulletins.command(
    name="subscribe",
    pass_context=True,
    help="Get notified when a high-price turnip offer occurs on another island. Signs"
    "you up for the 'stalk investor role'. This is a discord-wide subscription and"
    " will assign you to the role on every server you are a part of.",
)
async def bulletins_user_subscribe(ctx: discord.ext.commands.Context) -> None:
    """
    Assigns the user to the 'stalk investor' role so they get notified when bulletins
    are posted.
    """
    discord_user: discord.User = ctx.author
    await user_change_bulletin_subscription(discord_user, subscribe=True)
    await confirm_execution(ctx, [messages.REACTIONS.CONFIRM_BULLETINS_SUBSCRIBED])


@bulletins.command(
    name="unsubscribe",
    pass_context=True,
    help="stop being notified when a turnip price bulletin occurs. This change is "
    "applied to every server you are a part of.",
)
async def bulletins_user_unsubscribe(ctx: discord.ext.commands.Context) -> None:
    """
    Assigns the user to the 'stalk investor' role so they get notified when bulletins
    are posted.
    """
    discord_user: discord.User = ctx.author
    await user_change_bulletin_subscription(discord_user, subscribe=False)
    await confirm_execution(ctx, [messages.REACTIONS.CONFIRM_BULLETINS_UNSUBSCRIBED])

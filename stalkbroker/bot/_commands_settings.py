import discord.ext.commands
import pytz.exceptions


from stalkbroker import date_utils, errors, messages
from ._bot import STALKBROKER


_IMPORT_HELPER = None


@STALKBROKER.command(
    name="timezone", help="<zone> Sets the timezone for your user (ie pst)",
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
        await STALKBROKER.db.update_timezone(ctx.author.id, ctx.guild.id, converted_tz)
        await ctx.send(messages.confirmation_timezone(ctx.author, converted_tz))


# TODO: put this behind some sort of role check
@STALKBROKER.command(
    name="bulletins_here", help="send bulletins to this channel",
)
async def set_bulletins_channel(ctx: discord.ext.commands.Context) -> None:
    """
    Sets the channel a server wishes bulletins to be sent to.

    :param ctx: message context passed in by discord.py. The channel on this context
        is used as the bulletin channel.
    """
    await STALKBROKER.db.server_set_bulletin_channel(ctx.guild.id, ctx.channel.id)
    await ctx.send(messages.confirmation_bulletins_channel(ctx.author))

import discord.ext.commands
import pytz.exceptions


from stalkbroker import date_utils, errors, messages
from ._bot import STALKBROKER, DB_CONNECTION


_IMPORT_HELPER = None


@STALKBROKER.command(
    name="timezone", help="<zone> Sets the timezone for your user (ie pst)",
)
async def set_user_timezone(ctx: discord.ext.commands.Context, zone: str) -> None:
    try:
        converted_tz = date_utils.parse_timezone(zone)
    except pytz.exceptions.UnknownTimeZoneError:
        raise errors.BadTimezoneError(ctx, zone)
    else:
        await DB_CONNECTION.update_timezone(ctx.author.id, ctx.guild.id, converted_tz)
        await ctx.send(messages.confirmation_timezone(ctx.author, converted_tz))

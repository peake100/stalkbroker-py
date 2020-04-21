import discord.ext.commands
import pytz.exceptions


from stalkbroker import dates
from .bot import STALKBROKER, DB_CONNECTION


_IMPORT_HELPER = None


@STALKBROKER.command(
    name="timezone", help="<zone> Sets the timezone for your user (ie pst)",
)
async def set_user_timezone(ctx: discord.ext.commands.Context, zone: str) -> None:
    try:
        converted_tz = dates.parse_timezone(zone)
    except pytz.exceptions.UnknownTimeZoneError:
        await ctx.send(
            f"{ctx.author.display_name}, I don't recognize the timezone '{zone}',"
            f" try a timezone from: "
            "https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
        )
    else:
        await DB_CONNECTION.update_timezone(ctx.author.id, ctx.guild.id, converted_tz)
        await ctx.send(
            f"I've made a note, {ctx.author.display_name}! "
            f"You're growing your portfolio on {converted_tz.tzname(None)} time"
        )

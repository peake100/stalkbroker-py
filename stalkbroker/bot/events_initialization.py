import asyncio
import discord
from typing import Coroutine, List

from .bot import STALKBROKER, DB_CONNECTION


_IMPORT_HELPER = None


# Initially, I planned on only adding discord users lazily, in order to reduce the
# startup overhead if we are connected to lots of servers. However, we need to be able
# to track when a user is part of more than one server, so that all servers can be
# notified on high sell prices.
#
# If we were to add users lazily, it's possible that if a user only sent updates from
# one of their servers, we would miss that they are part of the other.
async def add_all_guild_members(guild: discord.Guild, timeout: int) -> None:
    """Adds all the users on a server to the db."""
    # We're going to build a list of coroutines to execute these updates then run
    # them all at once.
    print("Adding users for:", repr(guild))
    user_coros: List[Coroutine] = list()

    user: discord.Member
    for member in guild.members:
        user_coros.append(DB_CONNECTION.add_user(member.id, guild.id))

    await asyncio.gather(*user_coros)
    print("Users added:", len(user_coros))


@STALKBROKER.event
async def on_ready() -> None:
    """
    When the bot starts up, we want to go through all of the servers we are connected
    to and make sure they are saved in our database.
    """
    print(f"{STALKBROKER.user} has connected to Discord!")
    await DB_CONNECTION.connect()
    print(f"connected to database")

    guild_coros: List[Coroutine] = list()
    for guild in STALKBROKER.guilds:
        guild_coros.append(add_all_guild_members(guild, timeout=30))

    await asyncio.gather(*guild_coros)


@STALKBROKER.event
async def on_guild_join(guild: discord.Guild) -> None:
    """When a new guild joins the bot, we need to add it's members."""
    await add_all_guild_members(guild, timeout=30)


@STALKBROKER.event
async def on_member_join(member: discord.Member) -> None:
    """Add any new members that join."""
    await DB_CONNECTION.add_user(member.id, member.guild.id)

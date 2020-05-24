import asyncio
import discord.ext.commands
from typing import Coroutine, List

from stalkbroker import errors, constants, models

from ._bot import STALKBROKER
from ._commands_utils import user_update_guild_roles


_IMPORT_HELPER = None


@STALKBROKER.event
async def on_command_error(
    ctx: discord.ext.commands.Context, error: BaseException
) -> None:
    """Invoked by the discord.py when an error occurs while processing a command."""
    await errors.handle_command_error(ctx, error)


# Initially, I planned on only adding discord users lazily, in order to reduce the
# startup overhead if we are connected to lots of servers. However, we need to be able
# to track when a user is part of more than one server, so that all servers can be
# notified on high sell prices.
#
# If we were to add users lazily, it's possible that if a user only sent updates from
# one of their servers, we would miss that they are part of the other.
async def _add_all_guild_members(guild: discord.Guild) -> None:
    """Adds all the users on a server to the db."""
    # We're going to build a list of coroutines to execute these updates then run
    # them all at once.
    user_coros: List[Coroutine] = list()

    user: discord.Member
    for member in guild.members:
        user_coros.append(STALKBROKER.db.add_user(member, guild))

    # Create / fetch all the user records
    users: List[models.User] = await asyncio.gather(*user_coros)

    # Now we want to update all the user roles on this server in case it is a new server
    roles_coros: List[Coroutine] = list()
    for stalk_user in users:
        guild_member = guild.get_member(stalk_user.discord_id)
        roles_coros.append(user_update_guild_roles(guild, stalk_user, guild_member))

    await asyncio.gather(*roles_coros)


async def _add_roles(guild: discord.Guild) -> None:
    """Creates any roles on the server that the bot will need."""
    # If the role already exists we don't want to have to create it again, as this will
    # result in a duplicate role.
    if discord.utils.get(guild.roles, name=constants.BULLETIN_ROLE):
        return

    await guild.create_role(
        name=constants.BULLETIN_ROLE,
        mentionable=True,
        reason="This role will be mentioned in turnip price bulletins from stalkbroker",
    )


async def _add_guild(guild: discord.Guild) -> None:
    """Add a single guild and it's users to stalkbroker's database."""
    guild_add_coro = STALKBROKER.db.add_server(guild)
    member_add_coro = _add_all_guild_members(guild)
    create_server_roles_coro = _add_roles(guild)

    await asyncio.gather(guild_add_coro, member_add_coro, create_server_roles_coro)


async def _initialize() -> None:
    """
    When the bot starts up, we want to go through all of the servers we are connected
    to and make sure they are saved in our database, along with all their users.

    This event is invoked by discord.py when the bot client is ready to start sending
    and receiving messages, whether for the first time or when resuming a session.
    """
    print("doing some bookkeeping")
    guild_coros: List[Coroutine] = list()
    for guild in STALKBROKER.guilds:
        guild_coros.append(_add_guild(guild))

    await asyncio.gather(*guild_coros)
    print("bookkeeping done!")


@STALKBROKER.event
async def on_ready() -> None:
    """Called the first time the bot spins up."""
    print("starting up resources")
    await STALKBROKER.start_resources()
    await _initialize()
    STALKBROKER.started.set()


@STALKBROKER.event
async def on_resumed() -> None:
    """Called when the bot reconnects to discord after looses the connection."""
    await _initialize()


@STALKBROKER.event
async def on_guild_join(guild: discord.Guild) -> None:
    """When a new guild joins the bot, we need to add it's members."""
    await _add_guild(guild)


@STALKBROKER.event
async def on_member_join(member: discord.Member) -> None:
    """Add any new members that join."""
    stalk_user = await STALKBROKER.db.add_user(member, member.guild)
    await user_update_guild_roles(member.guild, stalk_user, member)

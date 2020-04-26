import discord.ext.commands
import asyncio
from typing import List, Coroutine, Union

from stalkbroker import messages, constants, models

from ._bot import STALKBROKER


async def confirm_execution(
    ctx: discord.ext.commands.Context, additional: List[str]
) -> None:
    """
    Confirms execution of a command with a thumbs up emoji.

    :param ctx: message context passed in by discord.py to the calling command.
    :param additional: a list of additional emojis to react with.

    The thumbs up emoji will always be added first, but reaction order is not
    guaranteed for emoji's passed to ``additional``.
    """
    message: discord.Message = ctx.message

    # We need to wait until the thumbs up is confirmed to be added to ensure it shows
    # up as the first reaction (discord shows reactions in the order they were added)
    await message.add_reaction(messages.REACTIONS.CONFIRM_PRIMARY)

    if not additional:
        return

    # We will add any additional reactions asynchronously. This means the order that
    # appears on discord may differ from the order passed into this function.
    react_coros: List[Coroutine] = list()
    for reaction in additional:
        react_coros.append(message.add_reaction(reaction))

    await asyncio.gather(*react_coros)


def get_guild_role(guild: discord.Guild, role_name: str) -> discord.Role:
    return discord.utils.get(guild.roles, name=role_name)


async def user_update_guild_roles(
    guild: discord.Guild,
    stalk_user: models.User,
    discord_user: Union[discord.User, discord.Member],
) -> None:
    """
    Update the guild roles of a user based on their settings.
    """
    # If we are getting a generic user, we need to fetch the user's member model for the
    # guild we are updating.
    if not isinstance(discord_user, discord.Member):
        discord_user = discord.utils.get(guild, id=discord_user.id)
        # Type assertion for mypy
        assert isinstance(discord_user, discord.Member)

    # Get the bulletin role for the guild.
    bulletins_role: discord.Role = get_guild_role(guild, constants.BULLETIN_ROLE)

    # Add or remove the guild member from the guild role.
    if stalk_user.notify_on_bulletin is True:
        await discord_user.add_roles(bulletins_role, reason="stalkbroker request")
    else:
        await discord_user.remove_roles(bulletins_role, reason="stalkbroker request")


async def user_change_bulletin_subscription(
    discord_user: discord.User, subscribe: bool
) -> None:
    # we want to sign them up to get notified on ALL servers, so let's fetch their
    # record and see what servers they are a part of.
    stalk_user = await STALKBROKER.db.update_user_notify_on_bulletin(
        discord_user, None, notify=subscribe,
    )

    # Lets add all the roles asynchronously instead of waiting for each operation.
    add_roles_coros: List[Coroutine] = list()

    for guild_id in stalk_user.servers:
        guild: discord.Guild = STALKBROKER.get_guild(guild_id)
        change_role_coro = user_update_guild_roles(guild, stalk_user, discord_user)
        add_roles_coros.append(change_role_coro)

    await asyncio.gather(*add_roles_coros)

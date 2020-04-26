import discord.ext.commands
import asyncio
from typing import List, Union, Coroutine

from stalkbroker import messages


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

import discord.ext.commands
import traceback

from ._bot import STALKBROKER
from stalkbroker import messages, errors


_IMPORT_HELPER = None


@STALKBROKER.event
async def on_command_error(
    ctx: discord.ext.commands.Context, error: BaseException
) -> None:
    """Used to handle errors that occur during the execution of commands."""
    user: discord.User = ctx.author

    # If this is a CommandInvokeError, then it was caused by an error raised by OUR
    # code. We'll want to fetch the original error.
    if isinstance(error, discord.ext.commands.CommandInvokeError):
        error = error.original

    if isinstance(error, errors.ResponseError):
        # There are several places that an UnknownUserTimezoneError can occur, so we are
        # going to handle them all centrally here. This error is raised when a user is
        # trying to update their ticker but has not set their timezone. We need to ask
        # them to do so.
        await ctx.send(error.response())
    else:
        # If it's an error we aren't expecting then we are going to send a short message
        # to the original channel, and DM the user an error traceback which can be
        # sent to us for debugging.
        await ctx.send(messages.error_general(user.display_name))

        traceback_str = "\n".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )

        await user.send(messages.error_general_details(traceback_str))

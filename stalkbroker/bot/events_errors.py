import discord.ext.commands
import traceback

from .bot import STALKBROKER
from stalkbroker import errors


_IMPORT_HELPER = None


@STALKBROKER.event
async def on_command_error(
    ctx: discord.ext.commands.Context, error: BaseException
) -> None:
    """Used to handle errors that occur during the execution of commands."""
    user: discord.User = ctx.author
    user_name = user.display_name

    # If this is a CommandInvokeError, then it was caused by an error raised by OUR
    # code. We'll want to fetch the original error.
    if isinstance(error, discord.ext.commands.CommandInvokeError):
        error = error.original

    if isinstance(error, errors.UnknownUserTimezoneError):
        # There are several places that an UnknownUserTimezoneError can occur, so we are
        # going to handle them all centrally here. This error is raised when a user is
        # trying to update their ticker but has not set their timezone. We need to ask
        # them to do so.
        await ctx.send(
            f"Uh-oh, {user_name}! I need some info to file your paperwork with the"
            f" Inter-island Revenue Service. "
            "Please let us know your timezone by typing: `$timezone <your timezone>`."
        )
    else:
        # If it's an error we aren't expecting then we are going to send a short message
        # to the original channel, and DM the user an error traceback which can be
        # sent to us for debugging.
        await ctx.send(
            f"Well, nuts. I had some trouble processing you're request, {user_name}."
            f" I'll DM you the details."
        )

        traceback_str = "\n".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )

        await user.send(
            f"Here is some more info on the error I encountered:\n```{traceback_str}```"
        )

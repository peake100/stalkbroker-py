import traceback
import discord.ext.commands
import logging
import asyncio
from typing import List, Coroutine

from stalkbroker import errors, messages


async def _handle_bulk_error(
    ctx: discord.ext.commands.Context, error: errors.BulkResponseError
) -> None:
    """
    Handles multiple errors asynchronously by unpacking the list of errors contained
    in a :error:`BulkResponseError`.
    """
    # Build a list of coroutines to run asynchronously.
    all_handle_coros: List[Coroutine] = list()

    for this_error in error.errors:
        handle_coro = handle_command_error(ctx, this_error)
        all_handle_coros.append(handle_coro)

    # We don't want communicating one error to stop others from being communicated, so
    # we'll tell them to return errors instead of halting on the first error.
    results = await asyncio.gather(*all_handle_coros, return_exceptions=False)

    # We'll raise the first error we come across.
    for result in results:
        if isinstance(result, BaseException) or issubclass(result, BaseException):
            raise result


async def _handle_response_error(
    ctx: discord.ext.commands.Context, error: errors.AbstractResponseError,
) -> None:
    """
    Handles errors defined by this package, which contain information on how to respond
    to users trying to execute commands.
    """
    if error.send_as_dm():
        # If this error should be sent as a DM, make it so
        await ctx.author.send(error.response())
    else:
        await ctx.send(error.response())


async def _handle_generic_error(
    ctx: discord.ext.commands.Context, error: BaseException,
) -> None:
    """
    Handles errors that do not inherent from our packages main error types
    :error:`ResponseError` and :error:`BulkResponseError`.

    We are going to send a generic "oops!" response to the channel that the command was
    invoked in, then DM them a traceback that can be sent to the devs for debugging.
    """

    traceback_str = "\n".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )
    logging.error(traceback_str)

    # Set up the coroutines for sending these two messages then execute them
    channel_coro = ctx.send(messages.error_general(ctx.author))
    dm_coro = ctx.author.send(messages.error_general_details(traceback_str))

    await asyncio.gather(channel_coro, dm_coro)


async def handle_command_error(
    ctx: discord.ext.commands.Context, error: BaseException
) -> None:
    """
    Used to handle errors that occur during the execution of commands.

    :param ctx: command context this error occurred during.
    :param error: The error to handle.

    This method is registered as a global command error handler, so it does not have to
    be invoked whenever you encounter an error that should halt the execution of a
    command. Such errors can be raised and will be automatically caught and handled.

    Manual invocation is only needed when you wish to report an error to the user, then
    continue on with the execution of the command.
    """

    # If this is a CommandInvokeError, then it was caused by an error raised by OUR
    # code. We'll want to fetch the original error and inspect it instead.
    if isinstance(error, discord.ext.commands.CommandInvokeError):
        error = error.original

    if isinstance(error, errors.BulkResponseError):
        await _handle_bulk_error(ctx, error)
    elif isinstance(error, errors.AbstractResponseError):
        await _handle_response_error(ctx, error)
    else:
        await _handle_generic_error(ctx, error)

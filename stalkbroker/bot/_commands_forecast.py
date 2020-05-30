import discord.ext.commands
import asyncio

from stalkbroker import messages
from ._bot import STALKBROKER
from ._common import (
    fetch_message_ticker_info,
    get_forecast_from_backend,
    current_period_for_backend,
    get_forecast_chart_from_backend,
)

_IMPORT_HELPER = None


@STALKBROKER.command(
    name="forecast",
    help=(
        "get forecast chart fo turnip prices. If user mention in message, forecast for "
        "that user's island will be fetched"
    ),
)
async def forecast(ctx: discord.ext.commands.Context) -> None:
    """
    Handles responses to the ``'$ticker'`` command.

    :param ctx: message context passed in by discord.py.

    Sends back forecast chart.
    """
    # We can send this asynchronously while we get the forecast and chart
    task = asyncio.create_task(
        ctx.message.add_reaction(messages.REACTIONS.CONFIRM_FORECAST),
    )

    # Get the user's latest ticker info from the db
    info = await fetch_message_ticker_info(ctx, date_arg=None)
    ticker_backend, forecast_backend = await get_forecast_from_backend(ctx, info)

    image_file = await get_forecast_chart_from_backend(
        ctx, info, ticker_backend, forecast_backend
    )

    # Create the text report we are going to send with it.
    current_period = current_period_for_backend(info.user_time)
    message = messages.report_forecast(
        info.discord_user, info.ticker, forecast_backend, current_period=current_period
    )

    await ctx.send(message, file=image_file)
    task.result()

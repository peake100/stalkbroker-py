import discord.ext.commands
import io
import asyncio
import grpclib.exceptions

from protogen.stalk_proto import models_pb2 as backend

from stalkbroker import messages, errors, date_utils
from ._bot import STALKBROKER
from ._common import (
    fetch_message_ticker_info,
    get_forecast_from_backend,
    current_period_for_backend,
)
from ._consts import CHART_BG_COLOR, CHART_PADDING

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
    backend_ticker, island_forecast = await get_forecast_from_backend(ctx, info)

    if info.user_time.weekday() == date_utils.SUNDAY:
        backend_ticker.current_period = -1

    # Once we have the forecast, get the reporting service to generate a chart for
    # it
    req_chart = backend.ReqForecastChart(
        ticker=backend_ticker,
        forecast=island_forecast,
        format=backend.ImageFormat.PNG,
        color_background=CHART_BG_COLOR,
        padding=CHART_PADDING,
    )

    # Catch backend errors and raise them wrapped in a response error.
    try:
        forecast_chart: backend.RespChart = (
            await STALKBROKER.client_reporter.ForecastChart(req_chart)
        )
    except grpclib.exceptions.GRPCError as error:
        raise errors.BackendError(ctx, error)

    # Embed the resulting image in the return message, and include a high-level chart
    image_buffer = io.BytesIO(forecast_chart.chart)
    image_file = discord.File(image_buffer, filename="forecast.png")

    # Create the text report we are going to send with it.
    current_period = current_period_for_backend(info.user_time)
    message = messages.report_forecast(
        info.discord_user, info.ticker, island_forecast, current_period=current_period
    )

    await ctx.send(message, file=image_file)
    task.result()

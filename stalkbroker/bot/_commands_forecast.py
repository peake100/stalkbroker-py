import discord.ext.commands
import io
import asyncio
import grpclib.exceptions
from ._bot import STALKBROKER
from ._commands_ticker import fetch_message_ticker_info
from stalkbroker import messages, errors
from protogen.stalk_proto import models_pb2 as backend
from typing import List


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

    # Now we need to submit that to the forecasting service
    nook_prices: List[int] = list()
    for period in range(12):
        nook_prices.append(info.ticker.phases.get(period, 0))

    current_period = info.ticker.phase_from_datetime(info.user_time)
    if current_period is None:
        current_period = -1

    backend_ticker = backend.Ticker(
        purchase_price=info.ticker.purchase_price,
        previous_pattern=backend.PricePatterns.UNKNOWN,
        prices=nook_prices,
        current_period=current_period,
    )

    # Catch backend errors and raise them wrapped in a response error.
    try:
        island_forecast = await STALKBROKER.client_forecaster.ForecastPrices(
            backend_ticker,
        )

        # Once we have the forecast, get the reporting service to generate a chart for
        # it
        req_chart = backend.ReqForecastChart(
            ticker=backend_ticker,
            forecast=island_forecast,
            format=backend.ImageFormat.PNG,
        )
        forecast_chart: backend.RespChart = (
            await STALKBROKER.client_reporter.ForecastChart(req_chart)
        )

    except grpclib.exceptions.GRPCError as error:
        raise errors.BackendError(ctx, error)

    image_buffer = io.BytesIO(forecast_chart.chart)

    # Embed the resulting image in the return message, and include a high-level chart
    image_file = discord.File(image_buffer, filename="forecast.png")
    message = messages.report_forecast(
        info.discord_user, info.ticker, island_forecast, current_period
    )

    await ctx.send(message, file=image_file)
    task.result()

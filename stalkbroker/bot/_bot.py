import discord.ext.commands
import os
import grpclib.client
import asyncio
from stalkbroker import db
from protogen.stalk_proto import forecaster_grpc as forecaster
from protogen.stalk_proto import reporter_grpc as reporter


class _StalkBrokerBot(discord.ext.commands.Bot):
    """Subclass of ``discord.ext.commands.Bot`` which we can attach custom fields to."""

    def __init__(self) -> None:
        super().__init__(command_prefix="$")
        # We need to change a some behavior when testing
        self.testing = False
        """
        Set by our tests to True when we are in testing mode. There are a few small
        behaviors we have to tweak during tests.
        """
        self.db = db.DBConnection()
        """The database connection to be used by our bot."""

        # set up grpc channels

        self.client_forecaster: forecaster.StalkForecasterStub = None  # type: ignore
        self.client_reporter: reporter.StalkReporterStub = None  # type: ignore

        self.started: asyncio.Event = asyncio.Event()

    async def start_resources(self) -> None:
        # Connect to db
        await STALKBROKER.db.connect()

        # set up grpc channels
        backend_host = os.environ["BACKEND_HOST"]
        backend_port = int(os.environ["BACKEND_PORT"])
        backend_channel = grpclib.client.Channel(host=backend_host, port=backend_port,)

        self.client_forecaster = forecaster.StalkForecasterStub(backend_channel)
        self.client_reporter = reporter.StalkReporterStub(backend_channel)


# Set up the bot and db connection
STALKBROKER: _StalkBrokerBot = _StalkBrokerBot()
"""Global variable containing the bot instance."""


def _add_events_and_commands() -> None:
    """
    We're storing our event and command handlers in other files for better organization,
    but we need to make sure they actually get invoked so that the method decorators are
    called and the events are added to the bot. We only need to import a single item
    from each file for it to be evaluated, so we are going to import a designated null
    object from each file to jump-start that process. We're putting it in a function so
    the auto-formatter doesn't try to put these imports at the top of the file,
    otherwise STALKBROKER will not be initialized when the imports happen.
    """
    from ._events import _IMPORT_HELPER as _helper1
    from ._commands_settings import _IMPORT_HELPER as _helper3
    from ._commands_ticker import _IMPORT_HELPER as _helper2
    from ._commands_forecast import _IMPORT_HELPER as _helper4

    (_helper1, _helper2, _helper3, _helper4)


_add_events_and_commands()


# The main logic to run our bot.
def run_stalkbroker() -> None:
    """Main run function for the bot."""
    STALKBROKER.run(os.environ["DISCORD_TOKEN"])

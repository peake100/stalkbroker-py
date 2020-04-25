import discord.ext.commands
import os
from stalkbroker import db


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


# Set up the bot and db connection
STALKBROKER: _StalkBrokerBot = _StalkBrokerBot()
"""Global variable containing the bot instance."""


def _add_events_and_commands() -> None:
    """
    We're storing our event and command handlers in other files for better organization,
    but we need to make sure they actually get invoked so that the method decorators are
    called and the events are added to the bot. We only need to import a single item
    from each file for it to be evaluated, so we are going to import a designated null
    object from each file to jumpstart that process. We're putting it in a function so
    the autoformatter doesn't try to put these at the top of the file.
    """
    from ._events import _IMPORT_HELPER as _helper1
    from ._commands_settings import _IMPORT_HELPER as _helper3
    from ._commands_ticker import _IMPORT_HELPER as _helper2

    (_helper1, _helper2, _helper3)


_add_events_and_commands()


# The main logic to run our bot.
def run_stalkbroker() -> None:
    """Main run function for the bot."""
    STALKBROKER.run(os.environ["DISCORD_TOKEN"])

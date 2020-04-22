import discord.ext.commands
import os
from stalkbroker import db


class _StalkBrokerBot(discord.ext.commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="$")
        # We need to change a some behavior when testing
        self.testing = False


# Set up the bot and db connection
STALKBROKER: _StalkBrokerBot = _StalkBrokerBot()
DB_CONNECTION: db.DBConnection = db.DBConnection()

# We're storing our event and command handlers in other files for better organization,
# but we need to make sure they actually get invoked so that the method decorators are
# called and the events are added to the bot. We only need to import a single item
# from each file for it to be evaluated, so we are going to import a designated null
# object from each file to jumpstart that process. We're putting it in a function so the
# autoformatter doesn't try to put these at the top of the file.


def _add_events_and_commands() -> None:
    from ._events import _IMPORT_HELPER as _helper1
    from ._events_errors import _IMPORT_HELPER as _helper4
    from ._commands_user_updates import _IMPORT_HELPER as _helper3
    from ._commands_ticker import _IMPORT_HELPER as _helper2

    (_helper1, _helper2, _helper3, _helper4)


_add_events_and_commands()


# The main logic to run our bot.
def run_stalkbroker() -> None:
    token = os.environ["DISCORD_TOKEN"]
    STALKBROKER.run(token)

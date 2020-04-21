import discord.ext.commands
from stalkbroker import db


# Set up the bot and db connection
STALKBROKER: discord.ext.commands.Bot = discord.ext.commands.Bot(command_prefix="$")
DB_CONNECTION = db.DBConnection()

# We're storing our event and command handlers in other files for better organization,
# but we need to make sure they actually get invoked so that the method decorators are
# called and the events are added to the bot. We only need to import a single item
# from each file for it to be evaluated, so we are going to import a designated null
# object from each file to jumpstart that process. We're putting it in a function so the
# autoformatter doesn't try to put these at the top of the file.


def add_events_and_commands() -> None:
    from .commands_user_updates import _IMPORT_HELPER as _helper3
    from .commands_ticker import _IMPORT_HELPER as _helper2
    from .events_initialization import _IMPORT_HELPER as _helper1
    from .events_errors import _IMPORT_HELPER as _helper4

    (_helper1, _helper2, _helper3, _helper4)


add_events_and_commands()

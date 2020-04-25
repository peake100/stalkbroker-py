import discord
from typing import Any


TIMEZONE_REFERENCE_URL = "https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"


def error_unknown_timezone(user: discord.User) -> str:
    """
    Error message returned when we need to know a user's timezone to execute the
    command.

    :param user: The user who's timezone info is not known.

    :returns: the formatted message.
    """
    return (
        f"Uh-oh, {user.mention}! I need to file some paperwork with the Inter-island"
        f" Revenue Service. Please let me know your timezone by typing: `$timezone"
        f" <your timezone>`."
    )


def error_no_bulletin_channel(user: discord.User, guild: discord.Guild) -> str:
    """
    Error message returned when a guild cannot be sent a bulletin because it's bulletin
    channel is not set.

    :param user: The user who's update resulted in this bulletin.
    :param guild: The guild missing their bulletin message.

    :returns: the formatted message.
    """
    return (
        f"{user.mention}, it looks like your guild: '{guild.name}' does not yet have "
        "a bulletin channel set up, so I can't alert them to your market's movements."
        " Tell an admin they need to type the `$bulletins_here` command in the channel"
        " you all want to use. Or if you're an admin, do it yourself!"
    )


def error_bad_value(user: discord.User, value_type: str, value: Any) -> str:
    """
    Generic error message returned when a bad argument value is supplied by the user.

    :param user: The user who's update resulted in this bulletin.
    :param value_type: The type of value, i.e. 'date', 'price', etc.
    :param value: The actual value we could not parse.

    :returns: the formatted message.
    """
    return (
        f"Hmmmm. {user.mention}, I'm having a hard time understanding the {value_type}"
        f" '{value}'."
    )


def error_bad_timezone(user: discord.User, bad_tz: str) -> str:
    """
    Error message returned when a user tries to set a bad timezone value for themselves.

    :param user: The user who's update resulted in this error.
    :param bad_tz: The bad tz arg supplied by the user.

    :returns: the formatted message.
    """
    return (
        f"{error_bad_value(user, 'timezone', bad_tz)} Try a timezone from: "
        + TIMEZONE_REFERENCE_URL
    )


def error_general(user: discord.User) -> str:
    """
    Error message returned when a general python error occurs during the execution of
    a command.

    :param user: The user who's command resulted in this error.

    :returns: the formatted message.
    """
    return (
        f"Well, nuts. I had some trouble processing you're request, {user.mention}."
        f" I'll DM you the details."
    )


def error_general_details(traceback_str: str) -> str:
    """
    Error message DM'ed to the user after a general error with the traceback associated
    with it.

    :param traceback_str: The formatted traceback.

    :returns: the formatted message.
    """
    return f"Here is some more info on the error I encountered:\n```{traceback_str}```"


def error_imaginary_date(user: discord.User, date_arg: str) -> str:
    """
    Error message returned when the user specifies a date that does not exist, i.e.
    '4/32'

    :param user: The user who's command resulted in this error.
    :param date_arg: The date argument the user supplied.

    :returns: the formatted message.
    """
    return (
        f"{user.mention}, you might need to check you're calendar!"
        f" '{date_arg}' doesn't exist!"
    )


def error_future_date(user: discord.User, date_arg: str) -> str:
    """
    Error message returned when the user specifies a date that has yet to happen.

    :param user: The user who's command resulted in this error.
    :param date_arg: The date argument the user supplied.

    :returns: the formatted message.
    """
    return (
        f"{user.mention}, are you some sort of time traveler!?"
        f" '{date_arg}' hasn't happened yet!"
    )


def error_time_of_day_required(user: discord.User) -> str:
    """
    Error message returned when the user specifies a date but not a time of day, and
    the time of day cannot be inferred.

    :param user: The user who's command resulted in this error.

    :returns: the formatted message.
    """
    return (
        f"{user.mention}, I need to know what time of day this price was being offered."
        " please include either 'AM' or 'PM' in your memo like so:"
        " `$ticker 123 4/14 AM`."
    )

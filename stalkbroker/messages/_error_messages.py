import discord
from typing import Any


TIMEZONE_REFERENCE_URL = "https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"


def error_unknown_timezone(user: discord.User) -> str:
    message = (
        f"Uh-oh, {user.mention}! I need to file some paperwork with the Inter-island"
        f" Revenue Service. Please let me know your timezone by typing: `$timezone"
        f" <your timezone>`."
    )
    return message


def error_bad_value(user: discord.User, value_type: str, value: Any) -> str:
    return (
        f"Hmmmm. {user.mention}, I'm having a hard time understanding the {value_type}"
        f" '{value}'."
    )


def error_bad_timezone(user: discord.User, value: str) -> str:
    return (
        f"{error_bad_value(user, 'timezone', value)} Try a timezone from: "
        + TIMEZONE_REFERENCE_URL
    )


def error_general(user: discord.User) -> str:
    message = (
        f"Well, nuts. I had some trouble processing you're request, {user.mention}."
        f" I'll DM you the details."
    )
    return message


def error_general_details(traceback_str: str) -> str:
    return f"Here is some more info on the error I encountered:\n```{traceback_str}```"

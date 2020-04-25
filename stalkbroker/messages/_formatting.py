import datetime
from typing import Mapping, Any, List

from ._memos import random_memo


MESSAGE_DATE_FORMAT: str = "%A %b %d, %Y"


def format_report(header: str, info: Mapping[str, Any]) -> str:
    """
    Formats a report message for the broker to return. Adds random memo to end.

    :param header: the title header for the report.
    :param info: key, value data to be formatted as 'key: value' in report (with
        formatting).

    :returns: the formatted report.
    """

    # We don't want to mutate the data that was passed in, so lets make a quick copy of
    # the info so we can add our memo.
    info = dict(info.items())
    info["Memo"] = random_memo()

    lines: List[str] = [
        f"***{header.title()}***",
    ]
    for key, value in info.items():
        if isinstance(value, datetime.date):
            value = value.strftime(MESSAGE_DATE_FORMAT)

        line = f"**{key.title()}**: {value}"
        lines.append(line)

    lines[1] = ">>> " + lines[1]

    return "\n".join(lines)


def bulletin(header: str, info: Mapping[str, Any]) -> str:
    """
    Formats a bulletin message for the broker to return. Adds random memo to end.

    :param header: the title header for the report.
    :param info: key, value data to be formatted as 'key: value' in report (with
        formatting).

    :returns: the formatted report.
    """
    header = header + "!!!"
    return format_report(header, info)

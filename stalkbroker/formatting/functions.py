import datetime
from typing import Mapping, Any, List


MESSAGE_DATE_FORMAT: str = "%A %b %d, %Y"


def form_response(header: str, info: Mapping[str, Any]) -> str:
    """Formats a message for the broker to return."""

    lines: List[str] = [
        f"***{header}***",
    ]
    for key, value in info.items():
        if isinstance(value, datetime.date):
            value = value.strftime(MESSAGE_DATE_FORMAT)

        line = f"**{key}**: {value}"
        lines.append(line)

    lines[1] = ">>> " + lines[1]

    return "\n".join(lines)

class DatetimeParseError(Exception):
    """Raised when a user-supplied date could not be parsed."""

    def __init__(self, bad_value: str):
        self.bad_value: str = bad_value
        super().__init__()


class UnknownUserTimezoneError(Exception):
    """Raised when a user's timezone is unknown, but required for the operation."""

    pass

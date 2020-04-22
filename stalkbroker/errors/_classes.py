import discord.ext.commands
from typing import Any


from stalkbroker import messages


class ResponseError(Exception):
    """
    Raising an error inside the processing of a command, who's type inherits this
    class will send a message back a message to the user.
    """

    def __init__(
        self, ctx: discord.ext.commands.Context, *args: Any, **kwargs: Any
    ) -> None:
        self.ctx: discord.ext.commands.Context = ctx
        super().__init__(*args)

    def response(self) -> str:
        raise NotImplementedError


class BadValueError(ResponseError):
    """
    Raised when we are having a hard time parsing command arguments. This error should
    not be invoked directly, but subclassed for individual value types.
    """

    def __init__(self, ctx: discord.ext.commands.Context, bad_value: Any):
        self.bad_value: Any = bad_value
        super().__init__(ctx)

    @staticmethod
    def value_type() -> str:
        raise NotImplementedError

    def response(self) -> str:
        return messages.error_bad_value(
            self.ctx.author, self.value_type(), self.bad_value
        )


class BadTimezoneError(BadValueError):
    """Raised when a user-supplied timezone is not recognized."""

    @staticmethod
    def value_type() -> str:
        return "timezone"

    def response(self) -> str:
        return messages.error_bad_timezone(self.ctx.author, self.bad_value)


class ParseDateError(BadValueError):
    """Raised when a user-supplied date could not be parsed."""

    @staticmethod
    def value_type() -> str:
        return "date"


class UnknownUserTimezoneError(ResponseError):
    """Raised when a user's timezone is unknown, but required for the operation."""

    def response(self) -> str:
        return messages.error_unknown_timezone(user=self.ctx.author)

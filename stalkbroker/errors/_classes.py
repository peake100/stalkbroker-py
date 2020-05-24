import discord.ext.commands
import grpclib.exceptions
from typing import Any, Iterable


from stalkbroker import messages


class AbstractResponseError(Exception):
    """
    Implementing this class (through subclassing) results in an error type that can
    be raised during the processing of a command to communicate the error to the user
    who invoked the command.
    """

    def __init__(
        self, ctx: discord.ext.commands.Context, *args: Any, **kwargs: Any
    ) -> None:
        """
        :param ctx: message context passed in by discord.py to the calling command.
        :param args: additional arguments for subclasses.
        :param kwargs: additional keyword arguments for subclasses.
        """

        self.ctx: discord.ext.commands.Context = ctx
        """The command context this error occurred during."""

        super().__init__(*args)

    def send_as_dm(self) -> bool:
        """
        Whether this error should be reported through a direct message to the user who's
        command invoked it. If ``False``, the error will be reported in the channel
        where the command was invoked.
        """
        raise NotImplementedError

    def response(self) -> str:
        """
        The response string to send back to the user.
        """
        raise NotImplementedError


class BulkResponseError(Exception):
    """
    When raised, multiple errors will be communicated to the user during error handling.
    """

    def __init__(self, errors: Iterable[BaseException]):
        """
        :param errors: list

        Raise this error inside of a command to have all errors handled
            by the bot's error-handler.
        """

        self.errors: Iterable[BaseException] = errors
        """List of errors to report."""

        super().__init__()


class AbstractBadValueError(AbstractResponseError):
    """
    Implement for communicating errors resulting from bad user-supplied values.
    Includes default response message implementation.
    """

    def __init__(self, ctx: discord.ext.commands.Context, bad_value: Any):

        self.bad_value: Any = bad_value
        """The bad argument value sent by the user"""

        super().__init__(ctx)

    @staticmethod
    def value_type() -> str:
        raise NotImplementedError

    def send_as_dm(self) -> bool:
        raise NotImplementedError

    def response(self) -> str:
        return messages.error_bad_value(
            self.ctx.author, self.value_type(), self.bad_value
        )


class BadTimezoneError(AbstractBadValueError):
    """Raised when a user-supplied timezone is not recognized."""

    @staticmethod
    def value_type() -> str:
        return "timezone"

    def send_as_dm(self) -> bool:
        return False

    def response(self) -> str:
        return messages.error_bad_timezone(self.ctx.author, self.bad_value)


class ImaginaryDateError(AbstractBadValueError):
    """Raised when a user-supplied date is not a valid caslendar date."""

    @staticmethod
    def value_type() -> str:
        return "date"

    def send_as_dm(self) -> bool:
        return False

    def response(self) -> str:
        return messages.error_imaginary_date(self.ctx.author, self.bad_value)


class FutureDateError(AbstractBadValueError):
    @staticmethod
    def value_type() -> str:
        return "date"

    def send_as_dm(self) -> bool:
        return False

    def response(self) -> str:
        return messages.error_future_date(self.ctx.author, self.bad_value)


class NoBulletinChannelError(AbstractResponseError):
    """
    Raised when we are trying to send a bulletin, but no channel has been configured
    yet.
    """

    def __init__(
        self,
        ctx: discord.ext.commands.Context,
        guild: discord.Guild,
        *args: Any,
        **kwargs: Any,
    ):
        """
        :param ctx: message context passed in by discord.py to the calling command.
        :param guild: thee guild which lacked a bulletin channel. NOTE: because
            bulletins are sent to ALL guilds this user is a part of, it may be different
            from the context's guild.
        :param args: additional arguments for subclasses.
        :param kwargs: additional keyword arguments for subclasses.
        """
        self.guild: discord.Guild = guild
        super().__init__(ctx, *args, **kwargs)

    def send_as_dm(self) -> bool:
        """
        We don't want some other guild's name to pop up in a different guild's
        channel, so we are going to DM this error.
        """
        return True

    def response(self) -> str:
        return messages.error_no_bulletin_channel(self.ctx.author, self.guild)


class UnknownUserTimezoneError(AbstractResponseError):
    """Raised when a user's timezone is unknown, but required for the operation."""

    def __init__(
        self,
        ctx: discord.ext.commands.Context,
        user: discord.User,
        *args: Any,
        **kwargs: Any,
    ):
        """
        :param ctx: message context passed in by discord.py to the calling command.
        :param user: the user the timezone is unknown for. NOTE: Because user's can
            fetch each other's ticker information through mentions, this user may
            be different from the context's user.
        :param args: additional arguments for subclasses.
        :param kwargs: additional keyword arguments for subclasses.
        """
        self.user: discord.User = user
        super().__init__(ctx, *args, **kwargs)

    def send_as_dm(self) -> bool:
        return False

    def response(self) -> str:
        return messages.error_unknown_timezone(user=self.user)


class TimeOfDayRequiredError(AbstractResponseError):
    """
    Raised when stalkbroker needs to know the time of day of a price in order to
    remember it.
    """

    def send_as_dm(self) -> bool:
        return False

    def response(self) -> str:
        return messages.error_time_of_day_required(self.ctx.author)


_IMPOSSIBLE_PATTERN_MESSAGE = (
    "could not generate possibilities because ticker prices are impossible"
)


class BackendError(Exception):
    """
    This class can be used to wrap grpc errors returned from our backend client stubs.
    The error will be converted during handling to one of our known errors if it is
    known. This allows us to wrap and raise the error in command handlers without having
    tp worry about parsing it there.
    """

    def __init__(
        self, ctx: discord.ext.commands.Context, error: grpclib.exceptions.GRPCError
    ) -> None:
        """
        :param ctx: message context passed in by discord.py to the calling command.
        :param user: the user the timezone is unknown for. NOTE: Because user's can
            fetch each other's ticker information through mentions, this user may
            be different from the context's user.
        :param args: additional arguments for subclasses.
        :param kwargs: additional keyword arguments for subclasses.
        """
        self.ctx: discord.ext.commands.Context = ctx
        self.error: grpclib.exceptions.GRPCError = error
        super().__init__()

    def convert_to_bot_error(self) -> Exception:
        if self.error.message == _IMPOSSIBLE_PATTERN_MESSAGE:
            return ImpossibleTickerError(self.ctx)
        else:
            return self.error


class ImpossibleTickerError(AbstractResponseError):
    def send_as_dm(self) -> bool:
        return False

    def response(self) -> str:
        return messages.error_impossible_ticker(self.ctx.author)

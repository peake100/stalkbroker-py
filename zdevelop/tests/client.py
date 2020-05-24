import asyncio
import discord.client
import uuid
import logging
import datetime
import pytz
from asynctest import patch
from typing import (
    Optional,
    List,
    Callable,
    Awaitable,
    Tuple,
    ContextManager,
    Type,
    Coroutine,
    Union,
)
from types import TracebackType


from stalkbroker import messages


TEST_SERVER_ID = 702021272405803050


def generate_on_ready(
    test_client: "DiscordTestClient", init_from: Optional["DiscordTestClient"]
) -> Callable[[], Awaitable[None]]:
    """
    When the test client is ready, we want it to:

        1. Set up channels to test with and remember them
        2. Set an async event to communicate to tests that the client is ready and tests
           can begin

    We need to generate this method in a closure so it has access to the test_client
    and can get/set properties on it.s
    """

    async def on_ready():
        test_client.user = test_client.client.user
        test_client.guild = test_client.client.get_guild(TEST_SERVER_ID)

        # If we are not initializing from a previously created test client, then
        # this is the primary client, and we need to set up our test channels for the
        # suite.
        is_primary = init_from is None

        if is_primary:
            test_client.channel_send = await test_client.guild.create_text_channel(
                name=f"send-{uuid.uuid4()}", reason="running test suite"
            )
            print(f"send channel created: {test_client.channel_send.name}")

            test_client.channel_bulletin = await test_client.guild.create_text_channel(
                name=f"bulletin-{uuid.uuid4()}", reason="running test suite"
            )
            print(f"bulletin channel created: {test_client.channel_bulletin.name}")
        else:
            test_client.channel_send = test_client.guild.get_channel(
                init_from.channel_send.id
            )
            test_client.channel_bulletin = test_client.guild.get_channel(
                init_from.channel_bulletin.id
            )

        test_client.event_ready.set()

    return on_ready


def generate_on_message(
    test_client: "DiscordTestClient", broker_id: int
) -> Callable[[discord.Message], Awaitable[None]]:
    """
    Whenever a message comes in, we want our test client to:

        1. Filter the message so we are only getting the ones we want.
        2. Store received messages so we can inspect them during tests.
        3. Wait to receive a certain number of messages, then set an event communicating
           that the expected number of messages has been received and we can continue.
    """

    async def on_message(message: discord.Message) -> None:
        # Toss out any messages not on our expected channels, otherwise we may receive
        # messages from other devs running tests concurrently
        if message.channel.id not in test_client.channel_id_whitelist:
            return

        # Print the message for our test logs. We're only going to use the primary
        # client to print so we don't double-print each message.
        if test_client.is_primary:
            print(
                f"message received"
                f"\nfrom: {test_client.user.display_name}"
                f"\nby: {message.author.display_name}"
                f"\nchannel: {message.channel.name}"
                f"\n{message.content}\n\n"
            )

        if message.author.id != broker_id:
            return

        test_client.messages_received.append(message)
        if test_client.test_expected_count_received == 0:
            raise IOError("Received an unexpected message")

        if (
            len(test_client.messages_received)
            >= test_client.test_expected_count_received
            and not test_client.event_messages_received.is_set()
        ):
            test_client.event_messages_received.set()

    return on_message


class _FreezeTimeContext:
    """
    Context manager to be invoked when we need to set the current time in a test.
    Makes it a little less unwieldy than calling multiple contexts in each test.
    """

    def __init__(
        self, datetime_local: datetime.datetime, timezone: pytz.BaseTzInfo
    ) -> None:
        """
        :param datetime_local: The local time of the message we want to freeze time for.
        """
        self.datetime_local: datetime.datetime = datetime_local
        # Cache the timezone as well
        self.tz_local: pytz.BaseTzInfo = timezone

        # This is where we will store the context managers we are, well, managing.

        self.patch_message_time: Optional[ContextManager] = None

    def __enter__(self) -> None:
        """Entering this manager freezes time at the desired value."""
        message_time_local = self.tz_local.localize(self.datetime_local, is_dst=None)
        message_time_utc = message_time_local.astimezone(pytz.utc)

        print("message time local:", self.datetime_local)
        print("message time utc:", message_time_utc)

        # However, discord messages will be getting their timestamps from the real-life
        # discord server, so we are going to monkey-patch the created_at attribute with
        # our desired time.
        self.patch_message_time = patch.object(
            discord.Message, "created_at", message_time_utc
        )

        # Enter our context managers.
        self.patch_message_time.__enter__()

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:
        # Exit our context managers.
        self.patch_message_time.__exit__(exc_type, exc_val, exc_tb)

        # We aren't going to suppress errors, let them propagate after we unfreeze time
        # and un-patch our method
        return exc_type is None


class DiscordTestClient:
    """
    DiscordTestClient will manage the setup, lifetime, and teardown of the discord.py
    clients we are going to use send and receive test messages to and from the bot.
    """

    def __init__(
        self,
        broker_id: int,
        timezone: pytz.BaseTzInfo,
        init_from: Optional["DiscordTestClient"] = None,
    ):
        # Resources
        self.client: discord.Client = discord.Client()
        self.timezone: pytz.BaseTzInfo = timezone

        # The rest of these will be created and set by the  'on_ready' client event.
        self.user: Optional[discord.User] = None
        self.guild: Optional[discord.Guild] = None
        self.channel_send: Optional[discord.TextChannel] = None
        self.channel_bulletin: Optional[discord.TextChannel] = None

        # Info
        # The user id of the stalkbroker bot.
        self._broker_id: int = broker_id

        # Whether this is the primary test client.
        self.is_primary = init_from is None

        # Events
        self.event_ready: asyncio.Event = asyncio.Event()
        self.event_messages_received: asyncio.Event = asyncio.Event()
        self.event_reactions_received: asyncio.Event = asyncio.Event()

        self.messages_received: List[discord.Message] = list()
        self.messages_sent: List[discord.Message] = list()

        # Test configuration
        self.test_expected_count_received: int = 0
        self.test_expected_count_reactions: int = 0

        # Create client events
        self.client.event(generate_on_ready(self, init_from))
        self.client.event(generate_on_message(self, broker_id))

    @property
    def channel_id_whitelist(self) -> Tuple[int, int]:
        """
        The channel id's we should store messages from. It's possible multiple instances
        of these tests could be running concurrently, so we want to filter out any
        messages on channels not created by this test suite.
        """
        return self.channel_send.id, self.channel_bulletin.id

    async def start(self, token: str):
        """
        Schedules the client to start on the asyncio event loop and waits for the
        ready event to be set.

        :param token: the token to use when starting this client
        """
        # The start routine on a discord client blocks until the client disconnects,
        # so if we await it directly, then this function will never return. We need to
        # add it to the loop without awaiting it
        asyncio.create_task(self.client.start(token))
        await self.event_ready.wait()

    async def shutdown(self) -> None:
        """Shuts down the client and cleans up the created channels."""

        # We only need to delete our test channels once, so we'll let the primary test
        # client take care of it.
        if self.is_primary and self.channel_send is not None:
            await self.channel_send.delete(reason="Tests complete")
            await self.channel_bulletin.delete(reason="Tests complete")

        await self.client.logout()

        logging.info("client shut down")

        return

    def reset_test(self, expected_messages: int, expected_reactions: int = 0) -> None:
        """
        Resets the message list and count when we are moving on to a new set of messages
        we need to listen for.
        """
        self.test_expected_count_received = expected_messages
        self.test_expected_count_reactions = expected_reactions

        self.messages_received = list()
        self.messages_sent = list()

        self.event_messages_received.clear()
        self.event_reactions_received.clear()

        if expected_reactions > 0:
            asyncio.create_task(self._wait_for_reaction())
        else:
            self.event_reactions_received.set()

        if expected_messages == 0:
            self.event_messages_received.set()

    async def send(self, content: str) -> None:
        message: discord.Message = await self.channel_send.send(content)
        self.messages_sent.append(message)

    async def send_bulletin(self, content: str) -> None:
        message: discord.Message = await self.channel_bulletin.send(content)
        self.messages_sent.append(message)

    async def _wait_for_reaction(self) -> None:

        while True:

            count = 0

            for i, message in enumerate(self.messages_sent):
                message = discord.utils.get(self.client.cached_messages, id=message.id)
                if message is None:
                    continue

                self.messages_sent[i] = message

                count += len(message.reactions)

                if count >= self.test_expected_count_reactions:
                    self.event_reactions_received.set()
                    print("reactions found")
                    return

            await asyncio.sleep(0.1)

    async def wait(self):
        """
        Blocks until all expected messages and reactions are received
        """
        coros: List[Coroutine] = list()

        if self.test_expected_count_received > 0:
            coros.append(self.event_messages_received.wait())

        if self.test_expected_count_reactions > 0:
            coros.append(self.event_reactions_received.wait())

        if coros:
            await asyncio.gather(*coros)
        print("communication complete")

    def freeze_time(self, datetime_local: datetime.datetime) -> _FreezeTimeContext:
        return _FreezeTimeContext(datetime_local, self.timezone)

    @staticmethod
    def _check_message(
        expected_content: str,
        expected_channel: discord.TextChannel,
        received: discord.Message,
        partial: bool,
    ) -> bool:
        """Filter used to pass or reject a received message."""
        if received.channel.id != expected_channel.id:
            return False
        elif partial:
            return expected_content in received.content
        else:
            return expected_content == received.content

    def assert_received_message(
        self,
        expected_message: str,
        expected_channel: discord.TextChannel,
        partial: bool = False,
    ) -> bool:
        """
        Asserts that we have received a message we are expecting to have received
        since .reset_test() was called.

        :param expected_message: the string content of the message we should have
            received
        :param expected_channel: the channel we expect to have received it on
        :param partial: If true, then `expected_message` is a substring of the full
            message we should have received. Useful for checking messages which
            have random pieces (like memos on reports).
        """

        received = any(
            self._check_message(expected_message, expected_channel, m, partial)
            for m in self.messages_received
        )

        if not received:
            for message in self.messages_received:
                print("received message:", message.content)

            raise ValueError(f"message not found: {expected_message}")

        # We're going to return true so we can assert this call in tests
        return True

    def assert_received_confirmation(
        self, additional_reactions: List[str], primary: bool = True
    ) -> bool:

        all_received: List[str] = list()
        for message in self.messages_sent:
            x: discord.Reaction
            all_received.extend(x.emoji for x in message.reactions)

        print("ALL REACTIONS:", all_received)
        if primary:
            assert messages.REACTIONS.CONFIRM_PRIMARY in all_received

        for reaction in additional_reactions:
            assert reaction in all_received

        # We're going to return true so we can assert this call in tests
        return True

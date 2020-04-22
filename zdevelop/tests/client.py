import asyncio
import discord.client
import uuid
import logging
import os
from typing import Optional, List, Callable, Awaitable


TEST_SERVER_ID = 702021272405803050


def generate_on_ready(
    test_client: "DiscordTestClient",
) -> Callable[[], Awaitable[None]]:
    async def on_ready():
        test_client.user = test_client.client.user
        test_client.guild = next(
            g for g in test_client.client.guilds if g.id == TEST_SERVER_ID
        )
        test_client.test_channel = await test_client.guild.create_text_channel(
            name=str(uuid.uuid4()), reason="running test suite"
        )
        logging.info(f"test channel created: {test_client.test_channel.name}")
        test_client.event_ready.set()

    return on_ready


def generate_on_message(
    test_client: "DiscordTestClient",
) -> Callable[[discord.Message], Awaitable[None]]:
    async def on_message(message: discord.Message) -> None:
        logging.info(f"message received:\n{message.content}")

        if message.author.id == test_client.client.user.id:
            return

        test_client.messages_received.append(message)
        if (
            len(test_client.messages_received)
            >= test_client.test_expected_message_count
            and not test_client.event_messages_received.is_set()
        ):
            test_client.event_messages_received.set()

    return on_message


class DiscordTestClient:
    """
    We are going to handle interacting with our test client through this class.
    It is going to run the client in it's own thread, and will handle sending
    messages for us.
    """

    def __init__(self):
        self.user: Optional[discord.User] = None
        self.client: discord.Client = discord.Client()
        self.guild: Optional[discord.Guild] = None
        self.test_channel: Optional[discord.TextChannel] = None

        # Events
        self.event_ready: asyncio.Event = asyncio.Event()
        self.event_messages_received: asyncio.Event = asyncio.Event()
        self.messages_received: List[discord.Message] = list()

        # Add client hooks
        self.client.event(generate_on_ready(self))
        self.client.event(generate_on_message(self))

        # Test configuration
        self.test_expected_message_count: int = 0

    def start(self):
        asyncio.create_task(self.client.start(os.environ["TEST_CLIENT_DISCORD_TOKEN"]))

    async def shutdown(self) -> None:
        if self.test_channel is not None:
            await self.test_channel.delete(reason="Tests complete")

        await self.client.logout()

        logging.info("client shut down")

        return

    def new_test(self, expected_message_count: int) -> None:
        self.test_expected_message_count = expected_message_count
        self.messages_received = list()
        self.event_messages_received.clear()

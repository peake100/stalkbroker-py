import pytz
import pytest
import pymongo
import motor.core
from dataclasses import dataclass, field
from typing import Tuple, List, Optional, Mapping

from stalkbroker import bot, db, messages

from zdevelop.tests.client import DiscordTestClient


@dataclass
class ExpectedIndex:
    name: str
    key_expected: List[Tuple[str, int]]

    index_found: Optional[Mapping] = field(init=False)

    def __post_init__(self) -> None:
        self.index_found = None

    def verify_index(self):
        key_found = list(dict(self.index_found["key"]).items())
        assert self.key_expected == key_found


async def verify_collection_indexes(
    expected: List[ExpectedIndex], collection: motor.core.Collection
) -> None:
    async for index in collection.list_indexes():
        for expected_index in expected:
            if expected_index.name == index["name"]:
                expected_index.index_found = index

    for expected_index in expected:
        expected_index.verify_index()


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_login(self, test_client: DiscordTestClient) -> None:

        # Test that both discord clients are ready
        assert test_client.event_ready.is_set()
        assert bot.STALKBROKER.is_ready()

        # Test that we are connected to the right guild
        assert any(g for g in bot.STALKBROKER.guilds if g.id == test_client.guild.id)

    @pytest.mark.asyncio
    async def test_user_indexes_created(self, stalkdb: db.DBConnection) -> None:
        """Tests that the correct indexes were created on the user collection"""
        index: pymongo.IndexModel

        expected = [
            ExpectedIndex(name="user_id", key_expected=[("id", pymongo.ASCENDING),]),
            ExpectedIndex(
                name="discord_id", key_expected=[("discord_id", pymongo.ASCENDING),]
            ),
        ]

        await verify_collection_indexes(expected, stalkdb.collections.users)

    @pytest.mark.asyncio
    async def test_ticker_indexes_created(self, stalkdb: db.DBConnection) -> None:
        """Tests that the correct indexes were made on the ticker collection"""
        index: pymongo.IndexModel

        expected = [
            ExpectedIndex(
                name="user_id", key_expected=[("user_id", pymongo.ASCENDING),]
            ),
            ExpectedIndex(
                name="week_of", key_expected=[("week_of", pymongo.ASCENDING),]
            ),
            ExpectedIndex(
                name="user_week_of",
                key_expected=[
                    ("user_id", pymongo.ASCENDING),
                    ("week_of", pymongo.ASCENDING),
                ],
            ),
        ]

        await verify_collection_indexes(expected, stalkdb.collections.tickers)

    @pytest.mark.asyncio
    async def test_users_added(
        self, stalkdb: db.DBConnection, test_client: DiscordTestClient
    ):
        """Tests if a user record was added for our test client."""

        # Search for our client's user id
        user_data = await stalkdb.collections.users.find_one(
            {"discord_id": test_client.user.id}
        )

        # Check that the discord id is correct
        assert user_data["discord_id"] == test_client.user.id
        # Check that this server has been added to the list of servers for that user
        assert any(s for s in user_data["servers"] if s == test_client.guild.id)

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio
    async def test_error_on_no_timezone(self, test_client: DiscordTestClient):
        """
        Tests that we thrown an error if we try to update the ticker without setting
        a timezone.
        """
        test_client.new_test(expected_message_count=1)

        await test_client.test_channel.send("$ticker 34")
        await test_client.event_messages_received.wait()

        assert len(test_client.messages_received) == 1

        assert test_client.messages_received[0].content == (
            messages.error_unknown_timezone(test_client.client.user)
        )

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio
    async def test_error_bad_tz(self, test_client: DiscordTestClient):
        """
        Tests that we thrown an error if we try to update the ticker without setting
        a timezone.
        """
        test_client.new_test(expected_message_count=1)

        await test_client.test_channel.send("$timezone blahblah")
        await test_client.event_messages_received.wait()

        assert len(test_client.messages_received) == 1

        assert test_client.messages_received[0].content == (
            messages.error_bad_timezone(test_client.client.user, "blahblah")
        )

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio
    async def test_set_timezone_response(self, test_client: DiscordTestClient):
        """
        Tests that we can set the timezone for ourselves
        """
        test_client.new_test(expected_message_count=1)

        await test_client.test_channel.send("$timezone pst")
        await test_client.event_messages_received.wait()

        assert len(test_client.messages_received) == 1

        assert test_client.messages_received[0].content == (
            messages.confirmation_timezone(
                test_client.user, pytz.timezone("US/Pacific")
            )
        )

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio
    async def test_set_timezone_db(
        self, stalkdb: db.DBConnection, test_client: DiscordTestClient
    ):
        """
        Tests that the timezone got updated correctly in the last test.
        """
        user = await stalkdb.fetch_user(test_client.user.id, test_client.guild.id)
        assert user.timezone == pytz.timezone("US/Pacific")

    @pytest.mark.timeout(5)
    @pytest.mark.asyncio
    async def test_set_buy_on_sunday(self, test_client: DiscordTestClient):
        pass

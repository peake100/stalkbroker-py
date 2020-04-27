import pytz
import pytest
import pymongo
import motor.core
import uuid
import datetime
import discord
from asynctest import patch
from dataclasses import dataclass, field
from typing import Tuple, List, Optional, Mapping, Callable

from stalkbroker import bot, db, messages, models, constants

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


def ticker_report_remove_memo(
    report: str, guild: discord.Guild, bulletin: bool = False
) -> str:
    # We need to remove the memo, since it's random, and check that
    # the rest of the message is there
    report_lines = report.split("\n")

    memo_line = -1

    memo = report_lines[-1]
    report = "\n".join(report_lines[:memo_line])

    assert memo.startswith("**Memo**:")

    return report


def mark_test(test: Callable) -> Callable:
    """
    We have a bunch of decorators we want to apply to all of our async tests, so we
    will use this decorator to apply them all
    """
    # Mark the test as an asyncio test (why pytest can't deduce this itself is beyond
    # me).
    test = pytest.mark.asyncio(test)

    # The test suite is set to fail on the first failure, and we don't want our tests
    # to hang indefinitely if one of our clients in another thread hangs or discord has
    # a communication error, so we are going to give each test a 10-second limit to
    # complete before failing.
    #
    # Also, keep in mind that there is a rate limit on bots of 5 messages / second /
    # server so sadly, these integration tests are going to take longer than we would
    # like.
    test = pytest.mark.timeout(20)(test)

    # Make it so our bot does not appear to be a bot on inspection, otherwise discord.py
    # will ignore any commands sent by it.
    test = patch.object(discord.User, "bot", False)(test)
    test = patch.object(discord.Member, "bot", False)(test)
    return test


class TestLifecycle:
    @mark_test
    async def test_login(self, test_client: DiscordTestClient) -> None:

        # Test that both discord clients are ready
        assert test_client.event_ready.is_set()
        assert bot.STALKBROKER.is_ready()

        # Test that we are connected to the right guild
        assert any(g for g in bot.STALKBROKER.guilds if g.id == test_client.guild.id)

    @mark_test
    async def test_server_indexes_created(self, stalkdb: db.DBConnection) -> None:
        """Tests that the correct indexes were created on the user collection"""
        index: pymongo.IndexModel

        expected = [
            ExpectedIndex(name="server_id", key_expected=[("id", pymongo.ASCENDING),]),
            ExpectedIndex(
                name="discord_id", key_expected=[("discord_id", pymongo.ASCENDING),]
            ),
        ]

        await verify_collection_indexes(expected, stalkdb.collections.servers)

    @mark_test
    async def test_user_indexes_created(self, stalkdb: db.DBConnection) -> None:
        """Tests that the correct indexes were created on the user collection"""
        index: pymongo.IndexModel

        expected = [
            ExpectedIndex(name="user_id", key_expected=[("id", pymongo.ASCENDING)]),
            ExpectedIndex(
                name="discord_id", key_expected=[("discord_id", pymongo.ASCENDING)]
            ),
        ]

        await verify_collection_indexes(expected, stalkdb.collections.users)

    @mark_test
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

    @mark_test
    async def test_server_added(
        self, stalkdb: db.DBConnection, test_client: DiscordTestClient
    ):
        """Tests if a user record was added for our test client."""

        # Search for our client's user id
        server_data = await stalkdb.collections.servers.find_one(
            {"discord_id": test_client.guild.id}
        )

        # Check that the discord id is correct
        assert isinstance(server_data["id"], uuid.UUID)
        assert server_data["discord_id"] == test_client.guild.id

    @mark_test
    async def test_users_added(
        self, stalkdb: db.DBConnection, test_client: DiscordTestClient
    ):
        """Tests if a user record was added for our test client."""

        # Search for our client's user id
        user_data = await stalkdb.collections.users.find_one(
            {"discord_id": test_client.user.id}
        )

        # Check that the discord id is correct
        assert isinstance(user_data["id"], uuid.UUID)
        assert user_data["discord_id"] == test_client.user.id
        # Check that this server has been added to the list of servers for that user
        assert any(s for s in user_data["servers"] if s == test_client.guild.id)

    @mark_test
    async def test_investor_role_created(self, test_client: DiscordTestClient) -> None:
        role: discord.Role = discord.utils.get(
            test_client.guild.roles, name=constants.BULLETIN_ROLE
        )
        assert role is not None
        assert role.name == constants.BULLETIN_ROLE

    # COMMAND TESTS #####

    @mark_test
    async def test_error_on_no_timezone(self, test_client: DiscordTestClient):
        """
        Tests that we throw  an error if we try to update the ticker without setting
        a timezone.
        """
        test_client.reset_test(expected_messages=1, expected_reactions=0)

        await test_client.send("$ticker 34")
        await test_client.event_messages_received.wait()

        assert len(test_client.messages_received) == 1

        test_client.assert_received_message(
            messages.error_unknown_timezone(test_client.client.user),
            expected_channel=test_client.channel_send,
        )

    @mark_test
    async def test_error_bad_tz(self, test_client: DiscordTestClient):
        """
        Tests that we thrown an error if we try to update the ticker without setting
        a timezone.
        """
        test_client.reset_test(expected_messages=1, expected_reactions=0)

        await test_client.send("$timezone blahblah")
        await test_client.wait()

        assert len(test_client.messages_received) == 1

        test_client.assert_received_message(
            messages.error_bad_timezone(test_client.client.user, "blahblah"),
            expected_channel=test_client.channel_send,
        )

    @mark_test
    async def test_set_timezone_response(
        self, test_client: DiscordTestClient, local_tz: pytz.BaseTzInfo
    ):
        """
        Tests that we can set the timezone for ourselves
        """
        test_client.reset_test(expected_messages=0, expected_reactions=2)

        await test_client.send(f"$timezone {test_client.timezone.zone}")
        await test_client.wait()

        test_client.assert_received_confirmation([messages.REACTIONS.CONFIRM_TIMEZONE])

    @mark_test
    async def test_set_timezone_response_user2(
        self, test_client2: DiscordTestClient, local_tz2: pytz.BaseTzInfo
    ):
        """
        Tests that we can set the timezone for ourselves
        """
        test_client2.reset_test(expected_messages=0, expected_reactions=2)

        await test_client2.send(f"$timezone {test_client2.timezone.zone}")
        await test_client2.wait()

        test_client2.assert_received_confirmation([messages.REACTIONS.CONFIRM_TIMEZONE])

    @mark_test
    async def test_set_timezone_db(
        self,
        stalkdb: db.DBConnection,
        test_client: DiscordTestClient,
        local_tz: pytz.BaseTzInfo,
    ):
        """
        Tests that the timezone got updated correctly in the last test.
        """
        user = await stalkdb.fetch_user(test_client.user, test_client.guild)
        assert user.timezone == local_tz

    @mark_test
    async def test_set_timezone_db_user2(
        self,
        stalkdb: db.DBConnection,
        test_client2: DiscordTestClient,
        local_tz2: pytz.BaseTzInfo,
    ):
        """
        Tests that the timezone got updated correctly in the last test.
        """
        user = await stalkdb.fetch_user(test_client2.user, test_client2.guild)
        assert user.timezone == local_tz2

    @staticmethod
    async def _test_bulletins_subscribe(
        test_client_primary: DiscordTestClient,
        test_client_secondary: DiscordTestClient,
        stalkdb: db.DBConnection,
    ):
        test_client_primary.reset_test(expected_messages=0, expected_reactions=2)
        await test_client_primary.send("$bulletins subscribe")
        await test_client_primary.wait()

        assert test_client_primary.assert_received_confirmation(
            [messages.REACTIONS.CONFIRM_BULLETINS_SUBSCRIBED]
        )

        # Check that the db was updated
        user = await stalkdb.fetch_user(
            test_client_primary.user, test_client_primary.guild
        )
        assert user.notify_on_bulletin is True

        # Check that the role was added on discord
        member: discord.Member = test_client_primary.guild.get_member(user.discord_id)
        assert any(r.name == constants.BULLETIN_ROLE for r in member.roles)

        # Check that the second user was not affected
        user2 = await stalkdb.fetch_user(
            test_client_secondary.user, test_client_secondary.guild
        )
        assert user2.notify_on_bulletin is False

        # Check that the role was NOT added on discord for the second user
        member: discord.Member = test_client_secondary.guild.get_member(
            user2.discord_id
        )
        assert not any(r.name == constants.BULLETIN_ROLE for r in member.roles)

    @staticmethod
    async def _test_bulletins_unsubscribe(
        test_client_primary: DiscordTestClient, stalkdb: db.DBConnection,
    ):
        test_client_primary.reset_test(expected_messages=0, expected_reactions=2)
        await test_client_primary.send("$bulletins unsubscribe")
        await test_client_primary.wait()

        assert test_client_primary.assert_received_confirmation(
            [messages.REACTIONS.CONFIRM_BULLETINS_UNSUBSCRIBED]
        )

        # Check that the db was updated
        user = await stalkdb.fetch_user(
            test_client_primary.user, test_client_primary.guild
        )
        assert user.notify_on_bulletin is False

        # Check that the role was added on discord
        member: discord.Member = test_client_primary.guild.get_member(user.discord_id)
        assert not any(r.name == constants.BULLETIN_ROLE for r in member.roles)

    @mark_test
    async def test_bulletins_subscribe_user1(
        self,
        test_client: DiscordTestClient,
        test_client2: DiscordTestClient,
        stalkdb: db.DBConnection,
    ):
        await self._test_bulletins_subscribe(
            test_client_primary=test_client,
            test_client_secondary=test_client2,
            stalkdb=stalkdb,
        )

    @mark_test
    async def test_bulletins_unsubscribe_user1(
        self, test_client: DiscordTestClient, stalkdb: db.DBConnection,
    ):
        await self._test_bulletins_unsubscribe(test_client, stalkdb)

    @mark_test
    async def test_bulletins_subscribe_user2(
        self,
        test_client: DiscordTestClient,
        test_client2: DiscordTestClient,
        stalkdb: db.DBConnection,
    ):
        await self._test_bulletins_subscribe(
            test_client_primary=test_client2,
            test_client_secondary=test_client,
            stalkdb=stalkdb,
        )

    @mark_test
    async def test_bulletins_unsubscribe_user2(
        self, test_client2: DiscordTestClient, stalkdb: db.DBConnection,
    ):
        await self._test_bulletins_unsubscribe(test_client2, stalkdb)

    @mark_test
    async def test_set_bulletin_channel(
        self, stalkdb: db.DBConnection, test_client: DiscordTestClient
    ):
        """
        Tests sending the command to set the bulletin channel.
        """
        test_client.reset_test(expected_messages=0, expected_reactions=2)

        await test_client.send_bulletin("$bulletins here")
        await test_client.wait()

        test_client.assert_received_confirmation(
            [messages.REACTIONS.CONFIRM_BULLETIN_CHANNEL]
        )

    @mark_test
    async def test_set_bulletin_channel_db(
        self, stalkdb: db.DBConnection, test_client: DiscordTestClient
    ):
        """
        Tests that the bulletin channel got correctly updated.
        """

        server = await stalkdb.fetch_server(test_client.guild)
        assert server.bulletin_channel == test_client.channel_bulletin.id

    @mark_test
    async def test_set_bulletin_minimum(
        self, stalkdb: db.DBConnection, test_client: DiscordTestClient
    ):
        """
        Tests sending the command to set the bulletin channel.
        """
        test_client.reset_test(expected_messages=0, expected_reactions=2)

        await test_client.send_bulletin("$bulletins minimum 450")
        await test_client.wait()

        test_client.assert_received_confirmation(
            [messages.REACTIONS.CONFIRM_BULLETIN_MINIMUM]
        )

    # NOTE: This test takes a long time to run because of discord's rate limiting, but
    # faithfully tests our core functionality.
    @pytest.mark.parametrize("user", [1, 2])
    @pytest.mark.parametrize("phase_index", range(13))
    @mark_test
    async def test_set_bell_prices(
        self,
        test_client: DiscordTestClient,
        test_client2: DiscordTestClient,
        phase_dates: List[datetime.datetime],
        expected_ticker: models.Ticker,
        expected_ticker_user2: models.Ticker,
        phase_index: int,
        user: int,
    ):
        # We're going to set a full ticker for two separate clients to make sure that
        # they get handled correctly.
        if user == 1:
            client_primary = test_client
            client_secondary = test_client2
        else:
            client_primary = test_client2
            client_secondary = test_client
            # Use a ticker with different values for the second user so we are more
            # certain it is being tracked correctly.
            expected_ticker = expected_ticker_user2

        message_time_local = phase_dates[phase_index]

        ticker_index = phase_index - 1
        if phase_index == 0:
            price = expected_ticker.purchase_price
        else:
            price = expected_ticker[ticker_index].price

        # Freeze time at the date we want so we are sending the message "now".
        with client_primary.freeze_time(message_time_local):
            if message_time_local.hour < 12:
                time_of_day = models.TimeOfDay.AM
            else:
                time_of_day = models.TimeOfDay.PM

            expected_reactions = messages.REACTIONS.price_update_reactions(
                price_date=message_time_local.date(),
                price_time_of_day=time_of_day,
                message_datetime_local=message_time_local,
            )

            if price >= 450 and message_time_local.date().weekday() != 6:
                expected_messages = 1
            else:
                expected_messages = 0

            # Now lets test setting the price
            client_primary.reset_test(
                expected_messages=expected_messages,
                expected_reactions=len(expected_reactions) + 1,
            )
            client_secondary.reset_test(
                expected_messages=expected_messages, expected_reactions=0,
            )

            await client_primary.send(f"$ticker {price}")
            await client_primary.wait()
            await client_secondary.wait()

            if expected_messages == 1:
                # And also check that the bulletin went out to the correct channel
                expected_bulletin = messages.bulletin_price_update(
                    discord_user=client_primary.user,
                    price=price,
                    date_local=message_time_local.date(),
                    time_of_day=time_of_day,
                )
                expected_bulletin = ticker_report_remove_memo(
                    expected_bulletin, guild=client_primary.guild, bulletin=True
                )

                client_primary.assert_received_message(
                    expected_bulletin, client_primary.channel_bulletin, partial=True,
                )

                message = client_primary.messages_received[0]
                # Test that the user was mentioned as the market
                assert (
                    discord.utils.get(message.mentions, id=client_primary.user.id)
                    is not None
                )

                # Test that the investor role gets mentioned
                investor_role = discord.utils.get(
                    client_primary.guild.roles, name=constants.BULLETIN_ROLE
                )
                assert (
                    discord.utils.get(message.role_mentions, id=investor_role.id)
                    is not None
                )

            # Once we validate that, let's test fetching the ticker via message
            client_primary.reset_test(1, expected_reactions=0)
            client_secondary.reset_test(1, expected_reactions=0)

            await client_primary.send("$ticker")

            await client_primary.wait()
            await client_secondary.wait()

            expected_report = messages.report_ticker(
                display_name=client_primary.user.display_name,
                ticker=expected_ticker,
                message_time_local=message_time_local,
            )
            expected_report = ticker_report_remove_memo(
                expected_report, guild=client_primary.guild
            )

            client_primary.assert_received_message(
                expected_report,
                expected_channel=test_client.channel_send,
                partial=True,
            )

            # Once we validate that, let's test fetching the ticker via mentioning
            # the user's name
            client_primary.reset_test(1, expected_reactions=0)
            client_secondary.reset_test(1, expected_reactions=0)

            await client_secondary.send(f"$ticker {client_primary.user.mention}")
            await client_primary.wait()
            await client_secondary.wait()

            client_secondary.assert_received_message(
                expected_report,
                expected_channel=client_secondary.channel_send,
                partial=True,
            )

    @mark_test
    async def test_ticker_db_values(
        self,
        expected_ticker: models.Ticker,
        stalkdb: db.DBConnection,
        test_client: DiscordTestClient,
    ):
        """
        Test that the ticker values set in the last test were correctly stored by the
        database.
        """

        stalk_user = await stalkdb.fetch_user(test_client.user, test_client.guild)
        stored_ticker = await stalkdb.fetch_ticker(stalk_user, expected_ticker.week_of)

        expected_ticker.user_id = stalk_user.id

        assert expected_ticker == stored_ticker

    @mark_test
    async def test_ticker_db_values_user2(
        self,
        expected_ticker_user2: models.Ticker,
        stalkdb: db.DBConnection,
        test_client2: DiscordTestClient,
    ):
        """
        Test that the ticker values set in the last test were correctly stored by the
        database.
        """

        stalk_user = await stalkdb.fetch_user(test_client2.user, test_client2.guild)
        stored_ticker = await stalkdb.fetch_ticker(
            stalk_user, expected_ticker_user2.week_of
        )

        expected_ticker_user2.user_id = stalk_user.id

        assert expected_ticker_user2 == stored_ticker

    @pytest.mark.parametrize("request_offset", [0, 1, 6])
    @mark_test
    async def test_fetch_past_ticker(
        self,
        expected_ticker: models.Ticker,
        stalkdb: db.DBConnection,
        test_client: DiscordTestClient,
        test_client2: DiscordTestClient,
        base_sunday: datetime.date,
        request_offset: int,
    ):
        """
        Test that the we can fetch the ticker as historical data when we specify the
        date. We are no longer freezing time, so the ticker we filled our earlier is now
        from a past week
        """
        test_client.reset_test(1, expected_reactions=0)
        test_client2.reset_test(1, expected_reactions=0)

        message_time_local = datetime.datetime(year=2020, month=5, day=30)

        with test_client.freeze_time(message_time_local):
            # We are going to test fetching for that sunday, as well as the date for
            # that monday and friday, to see that if we put any date in that week
            # we get the correct one back
            request_date = base_sunday + datetime.timedelta(request_offset)

            command = f"$ticker {request_date.strftime('%m/%d')}"
            await test_client.channel_send.send(command)

            await test_client.event_messages_received.wait()
            await test_client2.event_messages_received.wait()

            expected_report = messages.report_ticker(
                display_name=test_client.user.display_name,
                ticker=expected_ticker,
                message_time_local=datetime.datetime.now(),
            )
            expected_report = ticker_report_remove_memo(
                expected_report, guild=test_client.guild
            )

            test_client.assert_received_message(
                expected_report,
                expected_channel=test_client.channel_send,
                partial=True,
            )

            # Now lets try fetching with a mention
            test_client.reset_test(1, expected_reactions=0)
            test_client2.reset_test(1, expected_reactions=0)

            command = (
                f"$ticker {request_date.strftime('%m/%d')}"
                f" {test_client.user.mention}"
            )
            await test_client2.channel_send.send(command)

            await test_client.event_messages_received.wait()
            await test_client2.event_messages_received.wait()

            test_client2.assert_received_message(
                expected_report,
                expected_channel=test_client2.channel_send,
                partial=True,
            )

            # Lastly lets try putting the mention first
            test_client.reset_test(1, expected_reactions=0)
            test_client2.reset_test(1, expected_reactions=0)

            command = (
                f"$ticker {test_client.user.mention}"
                f" {request_date.strftime('%m/%d')}"
            )
            await test_client2.channel_send.send(command)

            await test_client.event_messages_received.wait()
            await test_client2.event_messages_received.wait()

            test_client2.assert_received_message(
                expected_report,
                expected_channel=test_client2.channel_send,
                partial=True,
            )

    @mark_test
    async def test_set_missed_am_ticker(
        self,
        expected_ticker_week2: models.Ticker,
        stalkdb: db.DBConnection,
        test_client: DiscordTestClient,
        phase_dates_week2: List[datetime.datetime],
    ) -> None:
        """
        In this test we are going to set a morning price in the afternoon of the same
        day using the "AM" argument.
        """

        wednesday_pm_message_time = datetime.datetime.combine(
            date=expected_ticker_week2.week_of + datetime.timedelta(days=3),
            time=datetime.time(hour=14),
        )

        expected_phase = expected_ticker_week2[4]
        # Lets test that updating hostorical data does not trigger a bulletin
        expected_phase.price = 800

        expected_reactions = messages.REACTIONS.price_update_reactions(
            price_date=expected_phase.date,
            price_time_of_day=models.TimeOfDay.AM,
            message_datetime_local=wednesday_pm_message_time,
        )

        test_client.reset_test(
            expected_messages=0, expected_reactions=len(expected_reactions) + 1
        )

        with test_client.freeze_time(wednesday_pm_message_time):
            command = f"$ticker AM {expected_phase.price}"

            await test_client.send(command)
            await test_client.wait()

            test_client.assert_received_confirmation(expected_reactions)

        stalk_user = await stalkdb.fetch_user(test_client.user, test_client.guild)
        ticker_set = await stalkdb.fetch_ticker(
            stalk_user, expected_ticker_week2.week_of
        )

        phase_set = ticker_set[4]
        assert phase_set == expected_phase

    @pytest.mark.parametrize(
        # Lets test every permutation of the order this command can go in
        "command,price",
        [
            ("$ticker {} PM 4/14", 201),
            ("$ticker {} 4/14 PM", 202),
            ("$ticker PM {} 4/14", 203),
            ("$ticker PM 4/14 {}", 204),
            ("$ticker 4/14 PM {}", 205),
            ("$ticker 4/14 {} PM", 206),
            # And once including a "bells" unit
            ("$ticker {} bells PM 4/14", 207),
            ("$ticker {} bells 4/14 PM", 208),
            ("$ticker PM {} bells 4/14", 209),
            ("$ticker PM 4/14 {} bells", 210),
            ("$ticker 4/14 PM {} bells", 211),
            ("$ticker 4/14 {} bells PM", 212),
            # Make sure we can parse dates with years
            ("$ticker 4/14/2020 {} bells PM", 213),
        ],
    )
    @mark_test
    async def test_set_missed_previous_ticker(
        self,
        expected_ticker_week2: models.Ticker,
        stalkdb: db.DBConnection,
        test_client: DiscordTestClient,
        phase_dates_week2: List[datetime.datetime],
        command: str,
        price: int,
    ) -> None:
        """
        In this test we are setting the price for Tuesday PM during Saturday AM.
        """
        friday_pm_message_time = datetime.datetime.combine(
            date=expected_ticker_week2.week_of + datetime.timedelta(days=6),
            time=datetime.time(hour=9),
        )

        expected_phase = expected_ticker_week2[3]
        expected_reactions = messages.REACTIONS.price_update_reactions(
            price_date=expected_phase.date,
            price_time_of_day=models.TimeOfDay.PM,
            message_datetime_local=friday_pm_message_time,
        )

        test_client.reset_test(0, expected_reactions=len(expected_reactions) + 1)

        # Set our unique price for this test
        expected_phase.price = price

        with test_client.freeze_time(friday_pm_message_time):

            # Lets move the commands around to check that we can do that
            command = command.format(price)

            await test_client.send(command)
            await test_client.wait()

            test_client.assert_received_confirmation(expected_reactions)

        stalk_user = await stalkdb.fetch_user(test_client.user, test_client.guild)
        ticker_set = await stalkdb.fetch_ticker(
            stalk_user, expected_ticker_week2.week_of
        )

        phase_set = ticker_set[3]
        assert phase_set == expected_phase

    @mark_test
    async def test_previous_year(
        self,
        expected_ticker: models.Ticker,
        stalkdb: db.DBConnection,
        test_client: DiscordTestClient,
        base_sunday: datetime.date,
    ):
        """
        If we ask for a date from the April and it's january, we should fetch from
        april of *the previous year* rather than try and fetch data that hasn't
        happened yet.
        """
        test_client.reset_test(1)

        message_time_local = datetime.datetime(year=2021, month=1, day=10)

        with test_client.freeze_time(message_time_local):
            request_date = base_sunday

            command = f"$ticker {request_date.strftime('%m/%d')}"
            await test_client.send(command)

            await test_client.event_messages_received.wait()

            expected_report = messages.report_ticker(
                display_name=test_client.user.display_name,
                ticker=expected_ticker,
                message_time_local=datetime.datetime.now(),
            )
            expected_report = ticker_report_remove_memo(
                expected_report, guild=test_client.guild
            )

            test_client.assert_received_message(
                expected_report,
                expected_channel=test_client.channel_send,
                partial=True,
            )

    @mark_test
    async def test_time_traveller_error(
        self,
        expected_ticker: models.Ticker,
        stalkdb: db.DBConnection,
        test_client: DiscordTestClient,
        base_sunday: datetime.date,
    ):
        """
        Check that we return an error when a user specifies a date that has not occurred
        yet.
        """
        test_client.reset_test(1, 0)

        message_time_local = datetime.datetime(year=2020, month=5, day=10)

        with test_client.freeze_time(message_time_local):

            command = f"$ticker 4/5/2021"
            await test_client.send(command)

            await test_client.event_messages_received.wait()

            expected_error = messages.error_future_date(test_client.user, "4/5/2021")

            test_client.assert_received_message(
                expected_error, expected_channel=test_client.channel_send,
            )

    @mark_test
    async def test_time_of_day_required_error(
        self,
        expected_ticker: models.Ticker,
        stalkdb: db.DBConnection,
        test_client: DiscordTestClient,
        base_sunday: datetime.date,
    ):
        """
        Check that we return an error when a user tries to update a bell price for a
        past date without specifying a time of day.
        """
        test_client.reset_test(1, 0)

        monday_arg_date = base_sunday + datetime.timedelta(days=1)

        tuesday_message_date = base_sunday + datetime.timedelta(days=2)
        tuesday_message_time = datetime.datetime.combine(
            tuesday_message_date, datetime.time(hour=12)
        )

        with test_client.freeze_time(tuesday_message_time):

            command = f"$ticker 180 {monday_arg_date.strftime('%m/%d')}"
            await test_client.send(command)

            await test_client.event_messages_received.wait()

            expected_error = messages.error_time_of_day_required(test_client.user)

            test_client.assert_received_message(
                expected_error, expected_channel=test_client.channel_send,
            )

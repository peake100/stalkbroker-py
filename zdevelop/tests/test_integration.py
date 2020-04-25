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

from stalkbroker import bot, db, messages, models

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


def ticker_report_remove_memo(report: str) -> str:
    # We need to remove the memo, since it's random, and check that
    # the rest of the message is there
    report_lines = report.split("\n")
    memo = report_lines[-1]
    report = "\n".join(report_lines[:-1])

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
    async def test_error_on_no_timezone(self, test_client: DiscordTestClient):
        """
        Tests that we throw  an error if we try to update the ticker without setting
        a timezone.
        """
        test_client.reset_test(expected_message_count=1)

        await test_client.channel_send.send("$ticker 34")
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
        test_client.reset_test(expected_message_count=1)

        await test_client.channel_send.send("$timezone blahblah")
        await test_client.event_messages_received.wait()

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
        test_client.reset_test(expected_message_count=1)

        await test_client.channel_send.send(f"$timezone {local_tz.zone}")
        await test_client.event_messages_received.wait()

        assert len(test_client.messages_received) == 1
        test_client.assert_received_message(
            messages.confirmation_timezone(test_client.user, local_tz),
            expected_channel=test_client.channel_send,
        )

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
        user = await stalkdb.fetch_user(test_client.user.id, test_client.guild.id)
        assert user.timezone == local_tz

    @mark_test
    async def test_set_bulletin_channel(
        self, stalkdb: db.DBConnection, test_client: DiscordTestClient
    ):
        """
        Tests sending the command to set the bulletin channel.
        """
        test_client.reset_test(1)

        await test_client.channel_bulletin.send("$bulletins_here")
        await test_client.event_messages_received.wait()

        test_client.assert_received_message(
            messages.confirmation_bulletins_channel(test_client.user),
            expected_channel=test_client.channel_bulletin,
        )

    @mark_test
    async def test_set_bulletin_channel_db(
        self, stalkdb: db.DBConnection, test_client: DiscordTestClient
    ):
        """
        Tests that the bulletin channel got correctly updated.
        """

        server = await stalkdb.fetch_server(test_client.guild.id)
        assert server.bulletin_channel == test_client.channel_bulletin.id

    @pytest.mark.parametrize("phase_index", range(13))
    @mark_test
    async def test_set_bell_prices(
        self,
        test_client: DiscordTestClient,
        test_client2: DiscordTestClient,
        phase_dates: List[datetime.datetime],
        expected_ticker: models.Ticker,
        local_tz: datetime.tzinfo,
        phase_index: int,
    ):
        message_time_local = phase_dates[phase_index]

        ticker_index = phase_index - 1
        if phase_index == 0:
            price = expected_ticker.purchase_price
        else:
            price = expected_ticker[ticker_index].price

        # Freeze time at the date we want so we are sending the message "now".
        with test_client.freeze_time(message_time_local):

            # Now lets test setting the price
            test_client.reset_test(2)

            await test_client.channel_send.send(f"$ticker {price}")

            if message_time_local.hour < 12:
                time_of_day = models.TimeOfDay.AM
            else:
                time_of_day = models.TimeOfDay.PM

            confirmation_expected = messages.confirmation_ticker_update(
                user=test_client.user,
                price=price,
                price_date=message_time_local.date(),
                price_time_of_day=time_of_day,
                message_datetime_local=message_time_local,
            )

            await test_client.event_messages_received.wait()

            # Check that we have received the confirmation
            test_client.assert_received_message(
                confirmation_expected, expected_channel=test_client.channel_send,
            )

            # And also check that the bulletin went out to the correct channel
            expected_bulletin = messages.bulletin_price_update(
                display_name=test_client.user.display_name,
                price=price,
                date_local=message_time_local.date(),
                time_of_day=time_of_day,
            )
            expected_bulletin = ticker_report_remove_memo(expected_bulletin)

            test_client.assert_received_message(
                expected_bulletin, test_client.channel_bulletin, partial=True,
            )

            # Once we validate that, let's test fetching the ticker via message
            test_client.reset_test(1)
            test_client2.reset_test(1)

            await test_client.channel_send.send("$ticker")

            await test_client.event_messages_received.wait()
            await test_client2.event_messages_received.wait()

            expected_report = messages.report_ticker(
                display_name=test_client.user.display_name,
                ticker=expected_ticker,
                message_time_local=message_time_local,
            )
            expected_report = ticker_report_remove_memo(expected_report)

            test_client.assert_received_message(
                expected_report,
                expected_channel=test_client.channel_send,
                partial=True,
            )

            # Once we validate that, let's test fetching the ticker via mentioning
            # the user's name
            test_client.reset_test(1)
            test_client2.reset_test(1)

            await test_client2.channel_send.send(f"$ticker {test_client.user.mention}")
            await test_client.event_messages_received.wait()
            await test_client2.event_messages_received.wait()

            test_client2.assert_received_message(
                expected_report,
                expected_channel=test_client2.channel_send,
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

        stalk_user = await stalkdb.fetch_user(test_client.user.id, test_client.guild.id)
        stored_ticker = await stalkdb.fetch_ticker(stalk_user, expected_ticker.week_of)

        expected_ticker.user_id = stalk_user.id

        assert expected_ticker == stored_ticker

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
        local_tz: datetime.tzinfo,
    ):
        """
        Test that the we can fetch the ticker as historical data when we specify the
        date. We are no longer freezing time, so the ticker we filled our earlier is now
        from a past week
        """
        test_client.reset_test(1)
        test_client2.reset_test(1)

        message_time_local = datetime.datetime(
            year=2020, month=5, day=30, tzinfo=local_tz
        )

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
            expected_report = ticker_report_remove_memo(expected_report)

            test_client.assert_received_message(
                expected_report,
                expected_channel=test_client.channel_send,
                partial=True,
            )

            # Now lets try fetching with a mention
            test_client.reset_test(1)
            test_client2.reset_test(1)

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
            test_client.reset_test(1)
            test_client2.reset_test(1)

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
        local_tz: datetime.tzinfo,
    ) -> None:
        """
        In this test we are going to set a morning price in the afternoon of the same
        day using the "AM" argument.
        """
        test_client.reset_test(1)

        wednesday_pm_message_time = datetime.datetime.combine(
            date=expected_ticker_week2.week_of + datetime.timedelta(days=3),
            time=datetime.time(hour=14, tzinfo=local_tz),
        )

        expected_phase = expected_ticker_week2[4]

        with test_client.freeze_time(wednesday_pm_message_time):
            command = f"$ticker AM {expected_phase.price}"

            await test_client.channel_send.send(command)
            await test_client.event_messages_received.wait()

            expected_confirmation = messages.confirmation_ticker_update(
                test_client.user,
                expected_phase.price,
                expected_phase.date,
                price_time_of_day=models.TimeOfDay.AM,
                message_datetime_local=wednesday_pm_message_time,
            )
            test_client.assert_received_message(
                expected_confirmation, expected_channel=test_client.channel_send,
            )

        stalk_user = await stalkdb.fetch_user(test_client.user.id, test_client.guild.id)
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
            ("$ticker 4/14/2020 {} bells PM", 212),
        ],
    )
    @mark_test
    async def test_set_missed_previous_ticker(
        self,
        expected_ticker_week2: models.Ticker,
        stalkdb: db.DBConnection,
        test_client: DiscordTestClient,
        phase_dates_week2: List[datetime.datetime],
        local_tz: datetime.tzinfo,
        command: str,
        price: int,
    ) -> None:
        """
        In this test we are setting the price for Tuesday PM during Saturday AM.
        """
        test_client.reset_test(1)

        friday_pm_message_time = datetime.datetime.combine(
            date=expected_ticker_week2.week_of + datetime.timedelta(days=6),
            time=datetime.time(hour=9, tzinfo=local_tz),
        )

        expected_phase = expected_ticker_week2[3]
        # Set our unique price for this test
        expected_phase.price = price

        with test_client.freeze_time(friday_pm_message_time):

            # Lets move the commands around to check that we can do that
            command = command.format(price)

            await test_client.channel_send.send(command)
            await test_client.event_messages_received.wait()

            expected_confirmation = messages.confirmation_ticker_update(
                test_client.user,
                expected_phase.price,
                expected_phase.date,
                price_time_of_day=models.TimeOfDay.PM,
                message_datetime_local=friday_pm_message_time,
            )
            test_client.assert_received_message(
                expected_confirmation, expected_channel=test_client.channel_send,
            )

        stalk_user = await stalkdb.fetch_user(test_client.user.id, test_client.guild.id)
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
        local_tz: datetime.tzinfo,
    ):
        """
        If we ask for a date from the April and it's january, we should fetch from
        april of *the previous year* rather than try and fetch data that hasn't
        happened yet.
        """
        test_client.reset_test(1)

        message_time_local = datetime.datetime(
            year=2021, month=1, day=10, tzinfo=local_tz
        )

        with test_client.freeze_time(message_time_local):
            request_date = base_sunday

            command = f"$ticker {request_date.strftime('%m/%d')}"
            await test_client.channel_send.send(command)

            await test_client.event_messages_received.wait()

            expected_report = messages.report_ticker(
                display_name=test_client.user.display_name,
                ticker=expected_ticker,
                message_time_local=datetime.datetime.now(),
            )
            expected_report = ticker_report_remove_memo(expected_report)

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
        local_tz: datetime.tzinfo,
    ):
        """
        Check that we return an error when a user specifies a date that has not occurred
        yet.
        """
        test_client.reset_test(1)

        message_time_local = datetime.datetime(
            year=2020, month=5, day=10, tzinfo=local_tz
        )

        with test_client.freeze_time(message_time_local):

            command = f"$ticker 4/5/2021"
            await test_client.channel_send.send(command)

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
        local_tz: datetime.tzinfo,
    ):
        """
        Check that we return an error when a user tries to update a bell price for a
        past date without specifying a time of day.
        """
        test_client.reset_test(1)

        monday_arg_date = base_sunday + datetime.timedelta(days=1)

        tuesday_message_date = base_sunday + datetime.timedelta(days=2)
        tuesday_message_time = datetime.datetime.combine(
            tuesday_message_date, datetime.time(hour=12), tzinfo=local_tz
        )

        with test_client.freeze_time(tuesday_message_time):

            command = f"$ticker 180 {monday_arg_date.strftime('%m/%d')}"
            await test_client.channel_send.send(command)

            await test_client.event_messages_received.wait()

            expected_error = messages.error_time_of_day_required(test_client.user)

            test_client.assert_received_message(
                expected_error, expected_channel=test_client.channel_send,
            )

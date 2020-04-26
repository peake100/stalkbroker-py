import pytest
import os
import asyncio
import discord.ext.commands
import dotenv
import time
import datetime
import pytz
import uuid
from typing import List

from stalkbroker import bot, db, models, constants

from zdevelop.tests.client import DiscordTestClient

dotenv.load_dotenv()

os.environ["MONGO_URI"] = "mongodb://localhost:57017"


def run_stalkbroker_in_thread(loop: asyncio.AbstractEventLoop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(bot.STALKBROKER.start(os.environ["DISCORD_TOKEN"]))


@pytest.fixture(scope="class")
def event_loop():
    """The event loop to use for the test"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="class")
async def stalkbroker(
    event_loop: asyncio.AbstractEventLoop,
) -> discord.ext.commands.Bot:
    """Sets up and runs the stalkbroker bot."""

    # Now when this role gets created or used we can be certain it was this test
    # We're going to run-specific user roles on the discord server, so we can be more
    # certain that our roles were set up by this test run.
    constants.BULLETIN_ROLE = f"stalk investor {uuid.uuid4()}"

    bot.STALKBROKER.testing = True

    asyncio.create_task(bot.STALKBROKER.start(os.environ["DISCORD_TOKEN_TEST"]))

    started = time.time()
    while not bot.STALKBROKER.is_ready():
        if time.time() - started > 10:
            raise TimeoutError("Stalkbroker failed to start within 10 seconds")
        await asyncio.sleep(0.1)

    yield bot.STALKBROKER

    # Remove our test roles
    guild: discord.Guild
    for guild in bot.STALKBROKER.guilds:
        bulletin_role: discord.Role = discord.utils.get(
            guild.roles, name=constants.BULLETIN_ROLE
        )
        await bulletin_role.delete(reason="Test run complete")

    await bot.STALKBROKER.logout()


@pytest.fixture(scope="class")
async def test_client(
    event_loop: asyncio.AbstractEventLoop, stalkbroker: discord.ext.commands.Bot,
) -> DiscordTestClient:
    """Manages our first test user client."""

    # Setup client
    client1 = DiscordTestClient(broker_id=stalkbroker.user.id)
    await client1.start(os.environ["TEST_CLIENT_DISCORD_TOKEN"])

    # Return to tests
    yield client1

    # Teardown
    await client1.shutdown()


@pytest.fixture(scope="class")
async def test_client2(
    event_loop: asyncio.AbstractEventLoop,
    stalkbroker: discord.ext.commands.Bot,
    test_client: DiscordTestClient,
) -> DiscordTestClient:
    """
    Manages our second test user client. We will primarily use this to test fetching
    other user's price information through mentions.
    """

    # Setup client
    client2 = DiscordTestClient(broker_id=stalkbroker.user.id, init_from=test_client)
    await client2.start(os.environ["TEST_CLIENT_DISCORD_TOKEN2"])

    # Return to tests
    yield client2

    # Teardown
    await client2.shutdown()


@pytest.fixture(scope="class")
async def stalkdb(event_loop: asyncio.AbstractEventLoop,) -> db.DBConnection:
    """
    Manages a database connector we can use to inspect the db after a transaction and
    confirm it was executed correctly.
    """
    connection = db.DBConnection()
    await connection.connect()

    yield connection


@pytest.fixture()
def local_tz() -> datetime.tzinfo:
    """
    Returns the local tz of the machine running these tests. Because user timezone is so
    integral to knowing the price phase of the user, we'll need to use it to make some
    adjustment to our datetimes.
    """
    return pytz.timezone("America/New_York")


@pytest.fixture()
def base_sunday():
    """The sunday of the first test week we are going to create data on"""
    # We are going to set it to 4 weeks prior
    sunday = datetime.date(year=2020, month=4, day=5)
    return sunday


def relative_message_time(
    sunday: datetime.date,
    weekday: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    shift_weeks: int = 0,
) -> datetime.datetime:
    """Creates a test message time for a day of the week relative to the base sunday"""
    if weekday == 6:
        weekday = -1

    date = sunday + datetime.timedelta(days=weekday + 1 + 7 * shift_weeks)

    clock_time = datetime.time(hour=hour, minute=minute, second=second,)

    return datetime.datetime.combine(date, clock_time)


@pytest.fixture()
def phase_dates(
    local_tz: datetime.tzinfo, base_sunday: datetime.date
) -> List[datetime.datetime]:
    """
    Test dates and times for the entire week of base_sunday. These are the times we
    will use as our message times for updating bell prices.
    """
    sunday = relative_message_time(sunday=base_sunday, weekday=6)

    monday_am = relative_message_time(sunday=base_sunday, weekday=0, hour=10)
    monday_pm = relative_message_time(sunday=base_sunday, weekday=0, hour=14)

    tuesday_am = relative_message_time(
        sunday=base_sunday, weekday=1, hour=11, minute=59, second=59
    )
    tuesday_pm = relative_message_time(
        sunday=base_sunday, weekday=1, hour=23, minute=59, second=59
    )

    wednesday_am = relative_message_time(sunday=base_sunday, weekday=2, hour=9)
    wednesday_pm = relative_message_time(sunday=base_sunday, weekday=2, hour=16)

    thursday_am = relative_message_time(sunday=base_sunday, weekday=3, hour=11)
    thursday_pm = relative_message_time(sunday=base_sunday, weekday=3, hour=16)

    friday_am = relative_message_time(sunday=base_sunday, weekday=4, hour=11)
    friday_pm = relative_message_time(sunday=base_sunday, weekday=4, hour=16)

    saturday_am = relative_message_time(sunday=base_sunday, weekday=5, hour=11)
    saturday_pm = relative_message_time(sunday=base_sunday, weekday=5, hour=16)

    return [
        sunday,
        monday_am,
        monday_pm,
        tuesday_am,
        tuesday_pm,
        wednesday_am,
        wednesday_pm,
        thursday_am,
        thursday_pm,
        friday_am,
        friday_pm,
        saturday_am,
        saturday_pm,
    ]


def create_expected_ticker(dates: List[datetime.datetime]):
    """Creates an expected ticker model based on a list of message times."""
    ticker = models.Ticker(
        user_id=uuid.uuid4(), week_of=dates[0].date(), purchase_price=100,
    )
    ticker[0] = 101
    ticker[1] = 102
    ticker[2] = 103
    ticker[3] = 104
    ticker[4] = 105
    ticker[5] = 449
    ticker[6] = 450
    ticker[7] = 108
    ticker[8] = 560
    ticker[9] = 110
    ticker[10] = 111
    ticker[11] = 112

    return ticker


@pytest.fixture
def expected_ticker(phase_dates: List[datetime.datetime]) -> models.Ticker:
    """The resulting ticker we expect to be created for messages sent on phase_dates."""
    return create_expected_ticker(phase_dates)


@pytest.fixture
def phase_dates_week2(phase_dates: List[datetime.date]) -> List[datetime.date]:
    """A second set of message times for the week after phase_dates."""
    one_week = datetime.timedelta(days=7)
    return [d + one_week for d in phase_dates]


@pytest.fixture
def expected_ticker_week2(phase_dates_week2: List[datetime.datetime]) -> models.Ticker:
    """
    The resulting ticker we expect to be created for messages sent on phase_dates_week2.
    """
    return create_expected_ticker(phase_dates_week2)

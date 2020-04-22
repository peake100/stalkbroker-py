import pytest
import os
import asyncio
import discord.ext.commands
import dotenv
import time
from concurrent.futures.thread import ThreadPoolExecutor

from stalkbroker.bot import STALKBROKER
from stalkbroker.db import DBConnection

from zdevelop.tests.client import DiscordTestClient

dotenv.load_dotenv()

os.environ["MONGO_URI"] = "mongodb://localhost:57017"


def run_stalkbroker_in_thread(loop: asyncio.AbstractEventLoop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(STALKBROKER.start(os.environ["DISCORD_TOKEN"]))


@pytest.fixture(scope="class")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="class")
def client_executor():
    """This executor is going to run our discord clients."""
    executor = ThreadPoolExecutor()
    yield executor
    executor.shutdown()


@pytest.fixture(scope="class")
async def stalkbroker(
    event_loop: asyncio.AbstractEventLoop, client_executor: ThreadPoolExecutor,
) -> discord.ext.commands.Bot:

    STALKBROKER.testing = True

    asyncio.create_task(STALKBROKER.start(os.environ["DISCORD_TOKEN_TEST"]))

    started = time.time()
    while not STALKBROKER.is_ready():
        if time.time() - started > 10:
            raise TimeoutError("Stalkbroker failed to start within 10 seconds")
        await asyncio.sleep(0.1)

    yield STALKBROKER

    await STALKBROKER.logout()


@pytest.fixture(scope="class")
async def test_client(
    event_loop: asyncio.AbstractEventLoop, stalkbroker: discord.ext.commands.Bot,
) -> DiscordTestClient:

    # Setup client
    test_client = DiscordTestClient()
    test_client.start()

    # Do not return until the client is running
    await test_client.event_ready.wait()

    # Return to tests
    yield test_client

    # Teardown
    await test_client.shutdown()


@pytest.fixture(scope="class")
async def stalkdb(event_loop: asyncio.AbstractEventLoop,) -> DBConnection:
    connection = DBConnection()
    await connection.connect()

    yield connection

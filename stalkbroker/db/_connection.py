import os
import uuid
import marshmallow
import pytz.tzinfo
import motor.motor_asyncio
import motor.core
import pymongo.errors
import datetime
import discord
from typing import Optional, Dict, Any, DefaultDict, Mapping
from collections import defaultdict

from stalkbroker import models, schemas, date_utils


# The schema used to serialize and deserialize the Server model.
SCHEMA_SERVER_FULL = schemas.Server(use_defaults=True, unknown=marshmallow.EXCLUDE)

# The schema used to serialize and deserialize the User model.
SCHEMA_USER_FULL = schemas.User(use_defaults=True, unknown=marshmallow.EXCLUDE)

# The schema used to serialize and deserialize the Ticker model.
SCHEMA_TICKER_FULL = schemas.Ticker(
    # If only the sunday price has been set, there maybe know 'phases' field
    partial=("phases",),
    use_defaults=True,
    unknown=marshmallow.EXCLUDE,
)


# Types Aliases for mypy
_QueryType = Dict[str, Any]
_UpdateType = DefaultDict[str, DefaultDict[str, Any]]


def _default_factory() -> DefaultDict[str, DefaultDict[str, Any]]:
    """Creates an infinitely deep nested default dict for building updates / queries."""
    return defaultdict(_default_factory)


def _new_update() -> _UpdateType:
    """Primes a new default dict to start building an update document with."""
    return defaultdict(_default_factory)


def _query_discord_id(discord_id: int) -> _QueryType:
    """Return a base quesry for a specific discord id."""
    return {"discord_id": discord_id}


class _Collections:
    """
    Houses the motor collection objects for asynchronously accessing data in mongodb.
    """

    def __init__(self, db: motor.core.AgnosticDatabase) -> None:
        """
        :param db: the motor database object.
        """
        self.servers: motor.core.AgnosticCollection = db["servers"]
        self.users: motor.core.AgnosticCollection = db["users"]
        self.tickers: motor.core.AgnosticCollection = db["tickers"]

    async def make_indexes(self) -> None:
        """Generate indexes for the mongo db collections."""
        # SERVER INDEXES
        await self.servers.create_index("id", unique=True, name="server_id")
        await self.servers.create_index("discord_id", unique=True, name="discord_id")

        # USER INDEXES
        await self.users.create_index("id", unique=True, name="user_id")
        await self.users.create_index("discord_id", unique=True, name="discord_id")

        # TICKER INDEXES
        await self.tickers.create_index("user_id", name="user_id")
        await self.tickers.create_index("week_of", name="week_of")
        # The most common search case is going to be searching for a specific user's
        # weekly ticker, so let's make a compound index for it. We also want to mark
        # it as unique so we don't result in a duplicate record by accident from an
        # odd race condition
        await self.tickers.create_index(
            [("user_id", pymongo.ASCENDING), ("week_of", pymongo.ASCENDING)],
            unique=True,
            name="user_week_of",
        )


class DBConnection:
    """Adapter used to fetch and store data with our mongodb database."""

    def __init__(self) -> None:
        self.client: Optional[motor.core.AgnosticClient] = None
        """Client object"""
        self.db: Optional[motor.core.AgnosticDatabase] = None
        """Database object"""
        self.collections: Optional[_Collections] = None
        """Collections object"""

    async def connect(self) -> None:
        """Connect to the database. Generates indexes if this is the first time."""
        # Get our mongo URI from the environment
        connection_uri: str = os.environ["MONGO_URI"]

        self.client = motor.motor_asyncio.AsyncIOMotorClient(connection_uri)
        self.db = self.client["stalkbroker"]
        self.collections = _Collections(self.db)

        # Make indexes on the db. This has no effect if the indexes are already set up.
        await self.collections.make_indexes()

    async def _upsert_server(
        self, query: _QueryType, update: Optional[_UpdateType]
    ) -> models.Server:
        """
        Add a server to the database if it does not exist or update it if it does.
         """
        assert self.collections is not None

        if update is None:
            update = _new_update()

        update["$setOnInsert"]["id"] = uuid.uuid4()
        update["$setOnInsert"]["discord_id"] = query["discord_id"]

        server_data = await self.collections.servers.find_one_and_update(
            query, update, upsert=True, return_document=pymongo.ReturnDocument.AFTER,
        )

        server = SCHEMA_SERVER_FULL.load(server_data)
        assert isinstance(server, models.Server)

        return server

    async def add_server(self, server: discord.Guild) -> models.Server:
        """
        Add a server record if it does not already exist.

        :param server: the server to add a record for.

        :returns: the updated / created server data.
        """
        query = _query_discord_id(server.id)
        return await self._upsert_server(query, None)

    async def fetch_server(self, server: discord.Guild) -> models.Server:
        """
        Fetch a server record.

        :param server: the server to fetch info about.

        If a record does not already exist for the server, it will be created.

        :returns: the server data.
        """
        query = _query_discord_id(server.id)
        return await self._upsert_server(query, None)

    async def server_set_bulletin_channel(
        self, server: discord.Guild, channel: discord.TextChannel,
    ) -> models.Server:
        """
        Set the bulletin channel id for a server.

        :param server: the server to set the channel for.
        :param channel: the channel to send bulletins to.

        :returns: the updated server data.
        """
        query = _query_discord_id(server.id)
        update = _new_update()
        update["$set"]["bulletin_channel"] = channel.id
        return await self._upsert_server(query, update)

    @staticmethod
    def _add_server_to_user_update(
        update: _UpdateType, server: Optional[discord.Guild]
    ) -> None:
        """handles adding a new server id to a user's record."""

        # The $addToSet operator adds a value to an array only if it does not already
        # exist. If we are interacting with the user over DM, the guild value will
        # be ``None``, so there is nothing to add. We are going ot handle that here
        # rather than in every operation where we might want to add a server for the
        # user.
        if server is not None:
            update["$addToSet"]["servers"] = server.id

    async def _upsert_user(
        self, query: _QueryType, update: _UpdateType
    ) -> Mapping[str, Any]:
        """
        Add a user if they don't exist or update the user record if they do. Returns
        raw document info.
        """
        assert self.collections is not None

        # If this user is not yet known, add a stalkbroker ID for them as well as
        # their discord id. These fields only get added if a record does not already
        # exist
        update["$setOnInsert"]["id"] = uuid.uuid4()
        update["$setOnInsert"]["discord_id"] = query["discord_id"]

        return await self.collections.users.find_one_and_update(
            query, update, upsert=True, return_document=pymongo.ReturnDocument.AFTER,
        )

    async def add_user(
        self, discord_user: discord.User, server: Optional[discord.Guild]
    ) -> models.User:
        """
        Add a user to the database.

        :param discord_user: the discord user we want to add.
        :param server: the server this user was found on. ``None`` if found via DM.

        Calling this method for a user that already exists is safe. In such a case, the
        server id will be appended to the existing record if it is new. It is expected
        that this method will be called on each user every time the bot boots up.

        :returns: User data.
        """
        query = _query_discord_id(discord_user.id)

        update = _new_update()
        self._add_server_to_user_update(update, server)

        user_document = await self._upsert_user(query, update)
        user = SCHEMA_USER_FULL.load(user_document)

        assert isinstance(user, models.User)

        return user

    async def fetch_user(
        self, discord_user: discord.User, server: Optional[discord.Guild]
    ) -> models.User:
        """
        Fetches user model from database.

        :param discord_user: the discord user we want to fetch info about.
        :param server: the server this user was found on. ``None`` if found via DM.

        If the user is not known to stalkbroker, a record will be created for them and
        returned.

        :returns: User data.
        """
        assert self.collections is not None

        query = _query_discord_id(discord_user.id)

        update = _new_update()
        self._add_server_to_user_update(update, server)
        user_data = await self._upsert_user(query, update)

        return SCHEMA_USER_FULL.load(user_data)

    async def update_timezone(
        self,
        discord_user: discord.User,
        server: Optional[discord.Guild],
        tz: pytz.tzinfo,
    ) -> None:
        """
        Update the timezone of a user.

        :param discord_user: the discord user to update.
        :param server: the server the user is on. ``None`` if interacting via DM.
        :param tz: the local timezone of the user to save.
        """
        assert self.collections is not None

        query = _query_discord_id(discord_user.id)
        update = _new_update()
        self._add_server_to_user_update(update, server)
        update["$set"]["timezone"] = tz.tzname(None)

        updated = await self.collections.users.find_one_and_update(query, update)
        if updated is None:
            await self._upsert_user(query, update)

    async def update_ticker(
        self,
        user: models.User,
        week_of: datetime.date,
        price_date: datetime.date,
        price_time_of_day: Optional[models.TimeOfDay],
        price: int,
    ) -> None:
        """
        Update a turnip price ticker for a user.

        :param user: the stalkbroker user the ticker belongs to.
        :param week_of: the sunday date this ticker starts.
        :param price_date: the date this bell price occurred.
        :param price_time_of_day: the time of day (AM/PM) this price occured.
        :param price: the price to save.
        """
        assert self.collections is not None

        mongo_date = date_utils.serialize_date(week_of)

        query = {"week_of": mongo_date}
        update: Dict[str, Any] = {
            "$setOnInsert": {"user_id": user.id, "week_of": mongo_date},
        }

        set_price: Dict[str, Any] = dict()
        if price_date.weekday() != date_utils.SUNDAY:
            date_utils.validate_price_period(
                date=price_date, time_of_day=price_time_of_day
            )
            phase_index = models.Ticker.phase_from_date(price_date, price_time_of_day)
            set_price[f"phases.{phase_index}"] = price

        else:
            set_price["purchase_price"] = price

        update["$set"] = set_price

        await self.collections.tickers.find_one_and_update(query, update, upsert=True)

    async def fetch_ticker(
        self, user: models.User, week_of: datetime.date
    ) -> models.Ticker:
        """
        Fetches a turnip price ticker for a given user and week.

        :param user: the stalkbroker user the ticker belongs to.
        :param week_of: the sunday date this ticker starts.

        :returns: turnip stalk price ticker.
        """
        assert self.collections is not None

        mongo_data = date_utils.serialize_date(week_of)

        query = {"user_id": user.id, "week_of": mongo_data}
        ticker_data = await self.collections.tickers.find_one(query)

        if ticker_data is None:
            ticker = models.Ticker(user_id=user.id, week_of=week_of)
        else:
            ticker = SCHEMA_TICKER_FULL.load(ticker_data)

        return ticker

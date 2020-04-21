import os
import uuid
import marshmallow
import pytz.tzinfo
import motor.motor_asyncio
import motor.core
import pymongo.errors
import datetime
from typing import Optional, Dict, Any, DefaultDict, Mapping
from collections import defaultdict

from stalkbroker import models, schemas


SCHEMA_USER_FULL = schemas.UserSchema(use_defaults=True, unknown=marshmallow.EXCLUDE)
SCHEMA_TICKER_FULL = schemas.TickerSchema(
    use_defaults=True, unknown=marshmallow.EXCLUDE,
)

DATE_SERIALIZER = schemas.DateField()


_QueryType = Dict[str, Any]
_UpdateType = DefaultDict[str, DefaultDict[str, Any]]
_NULL_PHASES = list(None for _ in range(12))


def _default_factory() -> DefaultDict[str, DefaultDict[str, Any]]:
    """Creates an infinitely deep nested default dict."""
    return defaultdict(_default_factory)


def new_update() -> _UpdateType:
    return defaultdict(_default_factory)


def query_discord_id(discord_id: str) -> _QueryType:
    return {"discord_id": discord_id}


class Collections:
    def __init__(self, db: motor.core.AgnosticDatabase) -> None:
        self.users: motor.core.AgnosticCollection = db["users"]
        self.purchases: motor.core.AgnosticCollection = db["purchases"]
        self.tickers: motor.core.AgnosticCollection = db["tickers"]
        self.sales: motor.core.AgnosticCollection = db["sales"]


class DBConnection:
    def __init__(self) -> None:
        self.client: Optional[motor.core.AgnosticClient] = None
        self.db: Optional[motor.core.AgnosticDatabase] = None
        self.collections: Optional[Collections] = None

    async def connect(self) -> None:
        user = os.getenv("MONGO_USER")
        pw = os.getenv("MONGO_PASSWORD")

        connection_uri: str = (
            f"mongodb+srv://{user}:{pw}@cluster0-spyaj.mongodb.net"
            "/test?retryWrites=true&w=majority"
        )

        self.client = motor.motor_asyncio.AsyncIOMotorClient(connection_uri)
        self.db = self.client["stalkbroker"]
        self.collections = Collections(self.db)

    @staticmethod
    def _add_server_to_user_update(update: _UpdateType, server_id: str) -> None:
        update["$addToSet"]["servers"] = server_id

    async def _upsert_user(
        self, query: _QueryType, update: _UpdateType
    ) -> Mapping[str, Any]:
        """
        Add a user if they don't exist or update the user record if they do.
        """
        assert self.collections is not None

        if update is None:
            update = new_update()

        # If this user is not yet known, add a stalkbroker ID for them as well as
        # their discord id. These fields only get added if a record does not already
        # exist
        update["$setOnInsert"]["id"] = uuid.uuid4()
        update["$setOnInsert"]["discord_id"] = query["discord_id"]

        return await self.collections.users.find_one_and_update(
            query, update, upsert=True, return_document=pymongo.ReturnDocument.AFTER,
        )

    async def add_user(self, discord_id: str, server_id: str) -> None:
        query = query_discord_id(discord_id)

        update = new_update()
        self._add_server_to_user_update(update, server_id)

        await self._upsert_user(query, update)

    async def fetch_user(self, discord_id: str, server_id: str) -> models.User:
        """Fetches user model from database."""
        assert self.collections is not None

        query = query_discord_id(discord_id)
        user_data = await self.collections.users.find_one(query)
        if user_data is None:
            update = new_update()
            self._add_server_to_user_update(update, server_id)
            user_data = await self._upsert_user(query, update)

        return SCHEMA_USER_FULL.load(user_data)

    async def update_timezone(
        self, discord_id: str, server_id: str, tz: pytz.tzinfo
    ) -> None:
        """Update the timezone of a user."""
        assert self.collections is not None

        query = query_discord_id(discord_id)
        update = new_update()
        self._add_server_to_user_update(update, server_id)
        update["$set"]["timezone"] = tz.tzname(None)

        updated = await self.collections.users.find_one_and_update(query, update)
        if updated is None:
            await self._upsert_user(query, update)

    async def update_ticker(
        self,
        user: models.User,
        week_of: datetime.date,
        date_local: datetime.date,
        time_of_day: models.TimeOfDay,
        price: int,
    ) -> None:
        assert self.collections is not None

        mongo_date = DATE_SERIALIZER._serialize(week_of, "", dict())

        query = {"week_of": mongo_date}

        update: Dict[str, Any] = {
            "$setOnInsert": {"user_id": user.id, "week_of": mongo_date},
        }

        set_price: Dict[str, Any] = dict()
        if date_local.weekday() != 6:
            phase_index = models.Ticker.phase_from_date(date_local, time_of_day)
            set_price[f"phases.{phase_index}"] = price
        else:
            set_price["purchase_price"] = price

        update["$set"] = set_price

        await self.collections.tickers.find_one_and_update(query, update, upsert=True)

    async def fetch_ticker(
        self, user: models.User, week_of: datetime.date
    ) -> models.Ticker:
        assert self.collections is not None

        mongo_data = DATE_SERIALIZER._serialize(week_of, "", dict())

        query = {"user_id": user.id, "week_of": mongo_data}
        ticker_data = await self.collections.tickers.find_one(query)

        if ticker_data is None:
            ticker = models.Ticker(user_id=user.id, week_of=week_of)
        else:
            ticker = SCHEMA_TICKER_FULL.load(ticker_data)

        return ticker

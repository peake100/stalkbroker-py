import grahamcracker
import marshmallow
import datetime
import pytz
from typing import Any, Optional, Mapping, Dict, Type, Union

from stalkbroker import models

_HandlerType = Union[marshmallow.fields.Field, marshmallow.Schema]
_TYPE_HANDLERS: Dict[Type[Any], Type[_HandlerType]] = dict()


class TzField(marshmallow.fields.Field):
    """Used to serialize and deserialize datetime.tzinfo.s"""

    def _serialize(
        self, value: datetime.tzinfo, attr: str, obj: Any, **kwargs: Any,
    ) -> str:
        name = value.tzname(None)
        if name is None:
            raise ValueError("could not get name for timezone")

        return name

    def _deserialize(
        self,
        value: str,
        attr: Optional[str],
        data: Optional[Mapping[str, Any]],
        **kwargs: Any,
    ) -> datetime.tzinfo:
        return pytz.timezone(value)


class DateField(marshmallow.fields.Field):
    """
    Used to serialize and deserialize datetime.date. We need to use a custom version
    for mongo because we need to serialize to a datetime.datetime (which mongodb can
    handle) instead of a string
    """

    def _serialize(
        self, value: datetime.date, attr: str, obj: Any, **kwargs: Any,
    ) -> datetime.date:
        return datetime.datetime.combine(value, datetime.time())

    def _deserialize(
        self,
        value: datetime.datetime,
        attr: Optional[str],
        data: Optional[Mapping[str, Any]],
        **kwargs: Any,
    ) -> datetime.date:
        return value.date()


class PatternsField(marshmallow.fields.Field):
    def _serialize(
        self, value: models.Patterns, attr: str, obj: Any, **kwargs: Any,
    ) -> str:
        return value.value

    def _deserialize(
        self,
        value: str,
        attr: Optional[str],
        data: Optional[Mapping[str, Any]],
        **kwargs: Any,
    ) -> Optional[models.Patterns]:
        if value is None:
            return value

        return models.Patterns(value)


_TYPE_HANDLERS[datetime.tzinfo] = TzField
_TYPE_HANDLERS[datetime.date] = DateField
_TYPE_HANDLERS[models.Patterns] = PatternsField


@grahamcracker.schema_for(models.User, type_handlers=_TYPE_HANDLERS)
class UserSchema(grahamcracker.DataSchema[models.User]):
    """Schema for serializing and deserializing user data"""

    pass


@grahamcracker.schema_for(models.Ticker, type_handlers=_TYPE_HANDLERS)
class TickerSchema(grahamcracker.DataSchema[models.Ticker]):
    """Schema for serializing and deserializing user data"""

    pass

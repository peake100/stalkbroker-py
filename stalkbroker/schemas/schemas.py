import grahamcracker
import marshmallow
import datetime
from typing import Any, Dict, Type, Union

from stalkbroker import models

from .fields import TzField, DateField, PatternsField

_HandlerType = Union[marshmallow.fields.Field, marshmallow.Schema]
_TYPE_HANDLERS: Dict[Type[Any], Type[_HandlerType]] = dict()


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

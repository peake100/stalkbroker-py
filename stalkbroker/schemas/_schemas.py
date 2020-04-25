import grahamcracker
import marshmallow
import datetime
from typing import Any, Dict, Type, Union

from stalkbroker import models

from ._fields import TzField, DateField, PatternsField


# These schemas are created using grahamcracker, which can automatically generate
# marshmallow schemas from dataclasses.

_HandlerType = Union[marshmallow.fields.Field, marshmallow.Schema]
_TYPE_HANDLERS: Dict[Type[Any], Type[_HandlerType]] = dict()


_TYPE_HANDLERS[datetime.tzinfo] = TzField
_TYPE_HANDLERS[datetime.date] = DateField
_TYPE_HANDLERS[models.Patterns] = PatternsField


@grahamcracker.schema_for(models.Server, type_handlers=_TYPE_HANDLERS)
class Server(grahamcracker.DataSchema[models.User]):
    """Schema for serializing and deserializing user data"""

    pass


@grahamcracker.schema_for(models.User, type_handlers=_TYPE_HANDLERS)
class User(grahamcracker.DataSchema[models.User]):
    """Schema for serializing and deserializing user data"""

    pass


@grahamcracker.schema_for(models.Ticker, type_handlers=_TYPE_HANDLERS)
class Ticker(grahamcracker.DataSchema[models.Ticker]):
    """Schema for serializing and deserializing user data"""

    pass

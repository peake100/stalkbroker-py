import marshmallow
import datetime
import pytz
from typing import Optional, Mapping, Any


from stalkbroker import models


class TzField(marshmallow.fields.Field):
    """Used to serialize and deserialize datetime.tzinfo.s"""

    def _serialize(
        self, value: pytz.BaseTzInfo, attr: str, obj: Any, **kwargs: Any,
    ) -> str:
        if value.zone is None:
            raise ValueError("could not get name for timezone")

        return value.zone

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
    """Used to serialize and deserialize the Pattern enum."""

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

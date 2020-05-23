import datetime
from typing import Optional, List

from stalkbroker import date_utils, models


class _Reactions:
    # Our primary confirmation will be a thumbs up
    CONFIRM_PRIMARY = "👍"

    # Now lets add som additional emotes to add for specific confirmations
    CONFIRM_PRICE_NOOK = "🦝"
    CONFIRM_PRICE_DAISEY = "🐷"

    CONFIRM_PRICE_MORNING = "☀️"
    CONFIRM_PRICE_NIGHT = "🌒"

    CONFIRM_PRICE_HISTORIC = "📅"

    CONFIRM_TIMEZONE = "🕓"
    CONFIRM_BULLETINS_SUBSCRIBED = "📰"
    CONFIRM_BULLETINS_UNSUBSCRIBED = "🔕"

    CONFIRM_BULLETIN_CHANNEL = "📈"
    CONFIRM_BULLETIN_MINIMUM = "💰"

    CONFIRM_FORECAST = "🌧️"

    @classmethod
    def price_update_reactions(
        cls,
        price_date: datetime.date,
        price_time_of_day: Optional[models.TimeOfDay],
        message_datetime_local: datetime.datetime,
    ) -> List[str]:
        reactions: List[str] = list()

        date_utils.validate_price_period(price_date, price_time_of_day)

        if price_date.weekday() == date_utils.SUNDAY:
            reactions.append(cls.CONFIRM_PRICE_DAISEY)
        else:
            reactions.append(cls.CONFIRM_PRICE_NOOK)
            if price_time_of_day is models.TimeOfDay.AM:
                reactions.append(cls.CONFIRM_PRICE_MORNING)
            else:
                reactions.append(cls.CONFIRM_PRICE_NIGHT)

        if not date_utils.is_price_period(
            message_datetime_local, price_date, price_time_of_day,
        ):
            reactions.append(cls.CONFIRM_PRICE_HISTORIC)

        return reactions


REACTIONS = _Reactions

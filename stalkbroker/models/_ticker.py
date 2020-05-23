import datetime
import uuid
from dataclasses import dataclass, field
from typing import Optional, Generator, Dict


from ._enums import TimeOfDay, Patterns


@dataclass
class PhaseInfo:
    price: Optional[int]
    name: str
    date: datetime.date
    time_of_day: Optional[TimeOfDay]


@dataclass
class Ticker:
    """Holds price updates for the week."""

    user_id: uuid.UUID
    """User id for island"""
    week_of: datetime.date
    """Sunday date the week begins with"""

    purchase_price: Optional[int] = None
    """The initial purchase price from Maisey day"""

    phases: Dict[int, int] = field(init=False, default_factory=dict)
    """
    An index of our known phases. We store as a map so that we aren't filling arrays
    with lots of ``None`` values when we don't have info for a phase.
    """

    final_pattern: Optional[Patterns] = None
    """The final pattern for the week 'None' if unknown"""

    def __post_init__(self) -> None:
        # Set up the dict where we store our phases.
        self.phases = dict()

    def __iter__(self) -> Generator[PhaseInfo, None, None]:
        for phase_index in range(12):
            phase_info = self[phase_index]
            yield phase_info

    def __getitem__(self, phase_index: int) -> PhaseInfo:
        try:
            price: Optional[int] = self.phases[phase_index]
        except KeyError:
            if phase_index > 11:
                raise IndexError("phase index must be between 0 and 11")
            price = None

        return self._create_phase_info(phase_index=phase_index, price=price)

    def __setitem__(self, phase_index: int, price: Optional[int]) -> None:
        if not isinstance(price, int) and price is not None:
            raise TypeError("price must be int or None")
        if phase_index > 11:
            raise IndexError("phase index must be between 0 and 13")

        if price is None:
            self.phases.pop(phase_index, None)
        else:
            self.phases[phase_index] = price

    def _create_phase_info(self, phase_index: int, price: Optional[int]) -> PhaseInfo:
        phase_info = PhaseInfo(
            price=price,
            name=self.phase_name(phase_index),
            date=(self.week_of + datetime.timedelta(days=phase_index // 2 + 1)),
            time_of_day=TimeOfDay.from_phase_index(phase_index),
        )
        return phase_info

    @staticmethod
    def phase_from_date(
        date: datetime.date, time_of_day: Optional[TimeOfDay]
    ) -> Optional[int]:
        """
        Get the phase index value for a given date and time of day (AM/PM).

        :param date: the date of the price phase.
        :param time_of_day: the time of day for the price phase.

        :returns: either the phase index or ``None`` if this is a sunday.
        """
        if date.weekday() == 6:
            return None
        elif time_of_day is None:
            raise ValueError("all days but sunday require time of day")

        return date.weekday() * 2 + time_of_day.value

    @staticmethod
    def phase_from_datetime(dt: datetime.datetime) -> Optional[int]:
        """
        Get the phase index value for a given datetime.

        :param dt: the date of the price phase.

        :returns: either the phase index or ``None`` if this is a sunday.
        """
        if dt.hour < 12:
            time_of_day: TimeOfDay = TimeOfDay.AM
        else:
            time_of_day = TimeOfDay.PM

        return Ticker.phase_from_date(date=dt.date(), time_of_day=time_of_day)

    @staticmethod
    def phase_name(phase: int) -> str:
        """
        Return the name to use in reports for a given price phase.

        :param phase: the index of the price phase. Use ``-1`` for sunday.

        :returns: phase name.
        """
        if phase == -1:
            return "Daisey's Deal"

        day = phase // 2
        day_str = {
            0: "Monday",
            1: "Tuesday",
            2: "Wednesday",
            3: "Thursday",
            4: "Friday",
            5: "Saturday",
        }[day]
        period_str = TimeOfDay.from_phase_index(phase).name
        return day_str + " " + period_str

    def for_date(
        self, date: datetime.date, time_of_day: Optional[TimeOfDay]
    ) -> PhaseInfo:
        """
        Return the phase info for a given date described by this ticker.

        :param date: the date of the desired phase info.
        :param time_of_day: the time of day (AM/PM of the desired phase info).
            Can be ``None`` if this is a sunday.
        """
        phase = self.phase_from_date(date, time_of_day)
        if phase is None:
            return PhaseInfo(
                price=self.purchase_price,
                name=self.phase_name(-1),
                date=date,
                time_of_day=None,
            )
        return self[phase]

    def set_price(
        self, price: int, date: datetime.date, time_of_day: Optional[TimeOfDay]
    ) -> None:
        """
        Set the price for a phase in the week described by the date and time of day.

        :param price: Turnip price to set.
        :param date: The date this price occurred on.
        :param time_of_day: The time of day this price occurred on. Can be ``None`` if
            this is a sunday
        """
        phase = self.phase_from_date(date, time_of_day)
        if phase is None:
            self.purchase_price = price
        else:
            self.phases[phase] = price

import datetime
import enum
import uuid
from dataclasses import dataclass, field
from typing import Optional, List, Generator, Dict


class TimeOfDay(enum.Enum):
    """Enum value of AM/PM"""

    AM = 0
    PM = 1

    @property
    def phase_adjustment(self) -> int:
        """
        The amount we need to adjust the phase index by when calculating the phase
        number from a date.
        """
        if self is TimeOfDay.AM:
            return 0
        return 1

    @classmethod
    def from_str(cls, value: str) -> "TimeOfDay":
        if value.upper() == "AM":
            return cls.AM
        else:
            return cls.PM

    @classmethod
    def from_phase_index(cls, phase_index: int) -> "TimeOfDay":
        if phase_index % 2 == 0:
            return cls.AM
        else:
            return cls.PM


class Patterns(enum.Enum):
    """Possible pattern names."""

    RANDOM = "random"
    DECREASING = "decreasing"
    SMALL_SPIKE = "small spike"
    BIG_SPIKE = "big spike"


@dataclass
class User:
    """Holds information about the user."""

    id: uuid.UUID
    """Unique id for the user"""
    discord_id: int
    """Discord id of the user"""
    timezone: Optional[datetime.tzinfo] = None
    """Timezone the user is in"""
    servers: List[int] = field(default_factory=list)
    """A list of servers this user is a part of"""


@dataclass
class Purchase:
    """Information about turnips purchased"""

    user_id: uuid.UUID
    """Id of user that made the sale."""
    market: uuid.UUID
    """User id for the island the sale was made."""
    unit_price: int
    """Price of an individual turnip."""
    units: int
    """Number of turnips purchased in this transaction."""
    investment_total: int
    """Total number of bells invested in this transaction."""


@dataclass
class Sale:
    user_id: uuid.UUID
    """User who made the sale."""
    sale_date: datetime.date
    """Date of sale."""
    sale_time_of_day: TimeOfDay
    """Sale period of sale."""
    sale_price: int
    """The price per turnip of the sale."""
    units: int
    """The number of turnips sold."""
    revenue: int
    """Bells received for this sale."""
    sale_market: Optional[uuid.UUID] = None
    """The user ID of the island the sale was made on."""


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

    phases: Dict[int, int] = field(init=False)
    """
    An index of our known phases. We store as a map so that we aren't filling arrays
    with lots of ``None`` values when we don't have info for a phase.
    """

    final_pattern: Optional[Patterns] = None
    """The final pattern for the week 'None' if unknown"""

    def __iter__(self) -> Generator[PhaseInfo, None, None]:
        for phase_index in range(12):
            phase_info = self[phase_index]
            yield phase_info

    def __getitem__(self, phase_index: int) -> PhaseInfo:
        try:
            price: Optional[int] = self.phases[phase_index]
        except KeyError:
            if phase_index > 11:
                raise IndexError("phase index must be between 0 and 13")
            price = None

        return self._create_phase_info(phase_index, price)

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
        if date.weekday() == 6:
            return None
        elif time_of_day is None:
            raise ValueError("all days but sunday require time of day")

        return date.weekday() * 2 + time_of_day.value

    @staticmethod
    def phase_name(phase: int) -> str:
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

    def date_info(
        self, date: datetime.date, time_of_day: Optional[TimeOfDay]
    ) -> PhaseInfo:
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
        phase = self.phase_from_date(date, time_of_day)
        if phase is None:
            self.purchase_price = price
        else:
            self.phases[phase] = price

import enum


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

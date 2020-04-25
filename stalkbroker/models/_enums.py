import enum


class TimeOfDay(enum.Enum):
    """Enum value of AM/PM"""

    AM = 0
    PM = 1

    @classmethod
    def from_str(cls, value: str) -> "TimeOfDay":
        """Return an AM/PM value from a string."""
        if value.upper() == "AM":
            return cls.AM
        else:
            return cls.PM

    @classmethod
    def from_phase_index(cls, phase_index: int) -> "TimeOfDay":
        """Return whether a phase index happens in the morning or afternoon."""
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

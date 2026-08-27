from dataclasses import dataclass
from enum import StrEnum

from ..const import MAX_TEMPERATURE, MAX_TIMER, MIN_TEMPERATURE, MIN_TIMER


class RemkoPower(StrEnum):
    OFF = "off"
    ON = "on"


class RemkoMode(StrEnum):
    COOL = "cool"
    DRY = "dry"
    FAN_ONLY = "fan_only"


class RemkoFanMode(StrEnum):
    AUTO = "auto"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RemkoSwingMode(StrEnum):
    OFF = "off"
    ON = "on"


@dataclass(frozen=True, slots=True)
class RemkoState:
    """A validated state that can be represented by a Remko IR frame."""

    power: RemkoPower = RemkoPower.OFF
    mode: RemkoMode = RemkoMode.COOL
    fan: RemkoFanMode = RemkoFanMode.AUTO
    swing: RemkoSwingMode = RemkoSwingMode.OFF
    temperature: int = 24
    timer: int = MIN_TIMER

    def __post_init__(self) -> None:
        """Validate values before they reach the protocol encoder."""
        enum_fields = (
            ("power", self.power, RemkoPower),
            ("mode", self.mode, RemkoMode),
            ("fan", self.fan, RemkoFanMode),
            ("swing", self.swing, RemkoSwingMode),
        )
        for name, value, enum_type in enum_fields:
            if not isinstance(value, enum_type):
                raise ValueError(f"Invalid {name}: {value!r}")

        if isinstance(self.temperature, bool) or not isinstance(self.temperature, int):
            raise ValueError(f"Temperature must be an integer: {self.temperature!r}")
        if not MIN_TEMPERATURE <= self.temperature <= MAX_TEMPERATURE:
            raise ValueError(
                f"Temperature {self.temperature} out of range "
                f"({MIN_TEMPERATURE}-{MAX_TEMPERATURE})"
            )

        if isinstance(self.timer, bool) or not isinstance(self.timer, int):
            raise ValueError(f"Timer must be an integer: {self.timer!r}")
        if not MIN_TIMER <= self.timer <= MAX_TIMER:
            raise ValueError(
                f"Timer {self.timer} out of range ({MIN_TIMER}-{MAX_TIMER})"
            )

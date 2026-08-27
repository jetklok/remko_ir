"""The Remko IR integration."""

from typing import TypedDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_REMOTE_TOPIC
from .protocol import (
    RemkoFanMode,
    RemkoIREncoder,
    RemkoMode,
    RemkoPower,
    RemkoProtocol,
    RemkoState,
    RemkoSwingMode,
    ZosungCodec,
)

__all__ = [
    "RemkoFanMode",
    "RemkoMode",
    "RemkoPower",
    "RemkoSwingMode",
    "RemkoIREncoder",
    "RemkoProtocol",
    "RemkoState",
    "ZosungCodec",
    "async_setup_entry",
    "async_unload_entry",
]

_PLATFORMS: list[Platform] = [Platform.CLIMATE]


class RemkoConfigEntryData(TypedDict):
    """Configuration stored for a Remko integration entry."""

    remote_topic: str


type RemkoIrConfigEntry = ConfigEntry[RemkoConfigEntryData]


async def async_setup_entry(hass: HomeAssistant, entry: RemkoIrConfigEntry) -> bool:
    """Set up Remko IR from a config entry."""
    entry.runtime_data = entry.data[CONF_REMOTE_TOPIC]

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RemkoIrConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)

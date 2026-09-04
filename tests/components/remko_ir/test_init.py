from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.remko_ir import async_setup_entry, async_unload_entry
from custom_components.remko_ir.const import CONF_REMOTE_TOPIC, DOMAIN


async def test_setup_and_unload_entry(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_REMOTE_TOPIC: "zigbee2mqtt/living_room_ir/set"},
    )
    entry.add_to_hass(hass)

    with (
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new_callable=AsyncMock,
        ) as forward,
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            new_callable=AsyncMock,
            return_value=True,
        ) as unload,
    ):
        assert await async_setup_entry(hass, entry)
        assert await async_unload_entry(hass, entry)

    assert entry.runtime_data == "zigbee2mqtt/living_room_ir/set"
    forward.assert_awaited_once()
    unload.assert_awaited_once()

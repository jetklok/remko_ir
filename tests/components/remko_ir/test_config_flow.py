"""Test the Remko IR config flow."""

from unittest.mock import AsyncMock

import pytest
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.remko_ir.config_flow import STEP_USER_DATA_SCHEMA
from custom_components.remko_ir.const import CONF_REMOTE_TOPIC, DOMAIN


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test entering a remote topic creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_REMOTE_TOPIC: "zigbee2mqtt/living_room"}
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Remko RKL 495 via zigbee2mqtt/living_room"
    assert result.get("data") == {CONF_REMOTE_TOPIC: "zigbee2mqtt/living_room"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_duplicate(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the same remote topic cannot be configured twice."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_REMOTE_TOPIC: "zigbee2mqtt/living_room"},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_REMOTE_TOPIC: "zigbee2mqtt/living_room"}
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.parametrize("topic", ["", "   ", "zigbee2mqtt/+/set", "zigbee2mqtt/#"])
async def test_form_rejects_invalid_publish_topic(
    hass: HomeAssistant, topic: str
) -> None:
    with pytest.raises(vol.Invalid):
        STEP_USER_DATA_SCHEMA({CONF_REMOTE_TOPIC: topic})

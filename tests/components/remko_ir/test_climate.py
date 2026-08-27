import json
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.climate.const import (
    FAN_HIGH,
    SWING_ON,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.core import HomeAssistant, State
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.remko_ir.climate import RemkoClimateEntity
from custom_components.remko_ir.const import CONF_REMOTE_TOPIC, DOMAIN
from custom_components.remko_ir.protocol import (
    RemkoFanMode,
    RemkoIREncoder,
    RemkoMode,
    RemkoPower,
    RemkoState,
    RemkoSwingMode,
)

TOPIC = "zigbee2mqtt/living_room_ir/set"


def test_climate_exposes_temperature_fan_and_swing_controls(
    hass: HomeAssistant,
) -> None:
    entity = create_entity(hass)

    assert entity.supported_features == (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
    )


def create_entity(hass: HomeAssistant) -> RemkoClimateEntity:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_REMOTE_TOPIC: TOPIC},
    )
    entity = RemkoClimateEntity(entry)
    entity.hass = hass
    return entity


async def test_set_hvac_mode_publishes_encoded_command(
    hass: HomeAssistant,
) -> None:
    entity = create_entity(hass)
    expected_state = RemkoState(power=RemkoPower.ON, mode=RemkoMode.COOL)

    with (
        patch(
            "custom_components.remko_ir.climate.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as publish,
        patch.object(entity, "async_write_ha_state"),
    ):
        await entity.async_set_hvac_mode(HVACMode.COOL)

    publish.assert_awaited_once_with(
        hass,
        TOPIC,
        json.dumps({"ir_code_to_send": RemkoIREncoder.encode(expected_state)}),
    )
    assert entity.hvac_mode == HVACMode.COOL


async def test_set_controls_publish_the_combined_state(
    hass: HomeAssistant,
) -> None:
    entity = create_entity(hass)

    with (
        patch(
            "custom_components.remko_ir.climate.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as publish,
        patch.object(entity, "async_write_ha_state"),
    ):
        await entity.async_set_hvac_mode(HVACMode.COOL)
        await entity.async_set_temperature(temperature=22)
        await entity.async_set_fan_mode(FAN_HIGH)
        await entity.async_set_swing_mode(SWING_ON)

    assert publish.await_count == 4
    expected_state = RemkoState(
        power=RemkoPower.ON,
        mode=RemkoMode.COOL,
        fan=RemkoFanMode.HIGH,
        swing=RemkoSwingMode.ON,
        temperature=22,
    )
    assert publish.await_args is not None
    assert json.loads(publish.await_args.args[2]) == {
        "ir_code_to_send": RemkoIREncoder.encode(expected_state)
    }


async def test_set_temperature_rejects_protocol_limit(
    hass: HomeAssistant,
) -> None:
    entity = create_entity(hass)

    with (
        patch(
            "custom_components.remko_ir.climate.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as publish,
        pytest.raises(ValueError, match="Temperature"),
    ):
        await entity.async_set_temperature(temperature=31)

    publish.assert_not_awaited()


async def test_fractional_temperature_is_rejected(hass: HomeAssistant) -> None:
    entity = create_entity(hass)

    with pytest.raises(ValueError, match="whole number"):
        await entity.async_set_temperature(temperature=22.5)


async def test_publish_failure_does_not_commit_state(hass: HomeAssistant) -> None:
    entity = create_entity(hass)

    with (
        patch(
            "custom_components.remko_ir.climate.mqtt.async_publish",
            new_callable=AsyncMock,
            side_effect=RuntimeError("MQTT unavailable"),
        ),
        pytest.raises(RuntimeError, match="MQTT unavailable"),
    ):
        await entity.async_set_hvac_mode(HVACMode.COOL)

    assert entity.hvac_mode == HVACMode.OFF


async def test_unsupported_hvac_mode_is_rejected(hass: HomeAssistant) -> None:
    entity = create_entity(hass)

    with pytest.raises(ValueError, match="Unsupported HVAC mode"):
        await entity.async_set_hvac_mode(HVACMode.HEAT)


async def test_non_cooling_mode_only_exposes_auto_fan(hass: HomeAssistant) -> None:
    entity = create_entity(hass)

    with (
        patch(
            "custom_components.remko_ir.climate.mqtt.async_publish",
            new_callable=AsyncMock,
        ),
        patch.object(entity, "async_write_ha_state"),
    ):
        await entity.async_set_hvac_mode(HVACMode.DRY)

    assert entity.fan_modes == ["auto"]
    with pytest.raises(ValueError, match="Unsupported fan mode"):
        await entity.async_set_fan_mode(FAN_HIGH)


async def test_swing_mode_is_restored(hass: HomeAssistant) -> None:
    entity = create_entity(hass)
    restored_state = State(
        "climate.remko_rkl_495",
        "cool",
        {"fan_mode": FAN_HIGH, "swing_mode": SWING_ON, "temperature": 22},
    )

    with patch.object(
        entity, "async_get_last_state", new_callable=AsyncMock
    ) as get_state:
        get_state.return_value = restored_state
        await entity.async_added_to_hass()

    assert entity.swing_mode == SWING_ON

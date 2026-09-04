import json
from unittest.mock import AsyncMock, Mock, patch

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
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )


def create_entity(hass: HomeAssistant) -> RemkoClimateEntity:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_REMOTE_TOPIC: TOPIC},
    )
    entity = RemkoClimateEntity(entry)
    entity.hass = hass
    return entity


async def test_setup_entry_adds_climate_entity(hass: HomeAssistant) -> None:
    from custom_components.remko_ir.climate import async_setup_entry

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_REMOTE_TOPIC: TOPIC})
    add_entities = Mock()

    await async_setup_entry(hass, entry, add_entities)

    add_entities.assert_called_once()


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


async def test_turn_on_turn_off_and_toggle(hass: HomeAssistant) -> None:
    entity = create_entity(hass)
    entity._last_hvac_mode = HVACMode.DRY

    with (
        patch(
            "custom_components.remko_ir.climate.mqtt.async_publish",
            new_callable=AsyncMock,
        ),
        patch.object(entity, "async_write_ha_state"),
    ):
        await entity.async_turn_off()
        assert entity.hvac_mode == HVACMode.OFF

        await entity.async_turn_off()
        assert entity.hvac_mode == HVACMode.OFF

        await entity.async_turn_on()
        assert entity.hvac_mode == HVACMode.DRY

        await entity.async_toggle()
        assert entity.hvac_mode == HVACMode.OFF

        await entity.async_toggle()
        assert entity.hvac_mode == HVACMode.DRY

    entity._attr_hvac_mode = HVACMode.OFF
    entity._last_hvac_mode = HVACMode.HEAT
    with (
        patch(
            "custom_components.remko_ir.climate.mqtt.async_publish",
            new_callable=AsyncMock,
        ),
        patch.object(entity, "async_write_ha_state"),
    ):
        await entity.async_turn_on()

    assert entity.hvac_mode == HVACMode.COOL


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


async def test_restore_without_state_keeps_defaults(hass: HomeAssistant) -> None:
    entity = create_entity(hass)

    with patch.object(
        entity, "async_get_last_state", AsyncMock(return_value=None)
    ):
        await entity.async_added_to_hass()

    assert entity.hvac_mode == HVACMode.OFF


async def test_rejects_invalid_hvac_fan_and_swing_values(
    hass: HomeAssistant,
) -> None:
    entity = create_entity(hass)

    with pytest.raises(ValueError, match="Unsupported HVAC mode"):
        await entity._async_send_command(hvac_mode=HVACMode.HEAT)

    with pytest.raises(ValueError, match="Unsupported fan mode"):
        await entity._async_send_command(fan_mode=FAN_HIGH)

    with pytest.raises(ValueError, match="Unsupported swing mode"):
        await entity._async_send_command(swing_mode="sideways")


async def test_set_swing_mode_rejects_invalid_value(hass: HomeAssistant) -> None:
    entity = create_entity(hass)

    with pytest.raises(ValueError, match="Unsupported swing mode"):
        await entity.async_set_swing_mode("sideways")


async def test_restore_non_cooling_mode_resets_fan(hass: HomeAssistant) -> None:
    entity = create_entity(hass)
    restored_state = State("climate.remko_rkl_495", "dry", {"fan_mode": FAN_HIGH})

    with patch.object(
        entity, "async_get_last_state", new_callable=AsyncMock
    ) as get_state:
        get_state.return_value = restored_state
        await entity.async_added_to_hass()

    assert entity.fan_mode == "auto"

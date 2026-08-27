"""Climate platform for the Remko IR integration."""

import json
from typing import Any, override

from homeassistant.components import mqtt
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_OFF,
    SWING_ON,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_REMOTE_TOPIC, MAX_TEMPERATURE, MIN_TEMPERATURE
from .protocol import (
    RemkoFanMode,
    RemkoIREncoder,
    RemkoMode,
    RemkoPower,
    RemkoState,
    RemkoSwingMode,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[str],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Remko climate entity."""
    async_add_entities([RemkoClimateEntity(entry)])


class RemkoClimateEntity(ClimateEntity, RestoreEntity):
    """Represent a Remko RKL 495 controlled through an IR remote."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "rkl_495"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = float(MIN_TEMPERATURE)
    _attr_max_temp = float(MAX_TEMPERATURE)
    _attr_target_temperature_step = 1.0
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
    )
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.DRY, HVACMode.FAN_ONLY]
    _attr_fan_modes = [FAN_AUTO, FAN_HIGH, FAN_MEDIUM, FAN_LOW]
    _attr_swing_modes = [SWING_OFF, SWING_ON]
    _attr_assumed_state = True

    def __init__(self, entry: ConfigEntry[str]) -> None:
        """Initialize the Remko climate entity."""
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = {
            "identifiers": {(entry.domain, entry.entry_id)},
            "manufacturer": "Remko",
            "model": "RKL 495",
        }
        self._remote_topic = entry.data[CONF_REMOTE_TOPIC]
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_fan_mode = FAN_AUTO
        self._attr_swing_mode = SWING_OFF
        self._attr_target_temperature = 24.0

    async def _async_send_command(
        self,
        hvac_mode: HVACMode | None = None,
        fan_mode: str | None = None,
        swing_mode: str | None = None,
        target_temperature: float | None = None,
    ) -> None:
        """Build and send the current AC state to Zigbee2MQTT."""
        hvac_mode = hvac_mode or self.hvac_mode or HVACMode.OFF
        fan_mode = fan_mode or self.fan_mode or FAN_AUTO
        swing_mode = swing_mode or self.swing_mode or SWING_OFF
        target_temperature = target_temperature or self.target_temperature or 24.0
        if hvac_mode not in self.hvac_modes:
            raise ValueError(f"Unsupported HVAC mode: {hvac_mode}")
        if fan_mode not in self._fan_modes_for_hvac_mode(hvac_mode):
            raise ValueError(f"Unsupported fan mode: {fan_mode}")
        if swing_mode not in (self.swing_modes or []):
            raise ValueError(f"Unsupported swing mode: {swing_mode}")
        state = RemkoState(
            power=(RemkoPower.OFF if hvac_mode == HVACMode.OFF else RemkoPower.ON),
            mode=(
                RemkoMode.COOL
                if hvac_mode == HVACMode.OFF
                else {
                    HVACMode.COOL: RemkoMode.COOL,
                    HVACMode.DRY: RemkoMode.DRY,
                    HVACMode.FAN_ONLY: RemkoMode.FAN_ONLY,
                }[hvac_mode]
            ),
            fan={
                FAN_AUTO: RemkoFanMode.AUTO,
                FAN_HIGH: RemkoFanMode.HIGH,
                FAN_MEDIUM: RemkoFanMode.MEDIUM,
                FAN_LOW: RemkoFanMode.LOW,
            }[fan_mode],
            swing=(RemkoSwingMode.ON if swing_mode == SWING_ON else RemkoSwingMode.OFF),
            temperature=int(target_temperature),
        )
        await mqtt.async_publish(
            self.hass,
            self._remote_topic,
            json.dumps({"ir_code_to_send": RemkoIREncoder.encode(state)}),
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last assumed state."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is None:
            return
        if last_state.state in self.hvac_modes:
            self._attr_hvac_mode = HVACMode(last_state.state)
        if fan_mode := last_state.attributes.get("fan_mode"):
            self._attr_fan_mode = fan_mode
        if swing_mode := last_state.attributes.get("swing_mode"):
            self._attr_swing_mode = swing_mode
        if temperature := last_state.attributes.get(ATTR_TEMPERATURE):
            self._attr_target_temperature = float(temperature)
        if self._attr_hvac_mode != HVACMode.COOL:
            self._attr_fan_mode = FAN_AUTO

    def _fan_modes_for_hvac_mode(self, hvac_mode: HVACMode) -> list[str]:
        """Return fan modes represented by the Remko protocol for a mode."""
        if hvac_mode == HVACMode.COOL:
            return [FAN_AUTO, FAN_HIGH, FAN_MEDIUM, FAN_LOW]
        return [FAN_AUTO]

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        if hvac_mode not in self.hvac_modes:
            raise ValueError(f"Unsupported HVAC mode: {hvac_mode}")
        fan_mode = FAN_AUTO if hvac_mode != HVACMode.COOL else self.fan_mode or FAN_AUTO
        await self._async_send_command(hvac_mode=hvac_mode, fan_mode=fan_mode)
        self._attr_hvac_mode = hvac_mode
        self._attr_fan_mode = fan_mode
        self._attr_fan_modes = self._fan_modes_for_hvac_mode(hvac_mode)
        self.async_write_ha_state()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]
        if (
            isinstance(temperature, bool)
            or not isinstance(temperature, (int, float))
            or temperature != int(temperature)
        ):
            raise ValueError("Temperature must be a whole number")
        if not self.min_temp <= temperature <= self.max_temp:
            raise ValueError(
                f"Temperature must be between {self.min_temp} and {self.max_temp}"
            )
        await self._async_send_command(target_temperature=float(temperature))
        self._attr_target_temperature = float(temperature)
        self.async_write_ha_state()

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        if fan_mode not in self._fan_modes_for_hvac_mode(
            self.hvac_mode or HVACMode.OFF
        ):
            raise ValueError(f"Unsupported fan mode: {fan_mode}")
        await self._async_send_command(fan_mode=fan_mode)
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the swing mode."""
        if swing_mode not in (self.swing_modes or []):
            raise ValueError(f"Unsupported swing mode: {swing_mode}")
        await self._async_send_command(swing_mode=swing_mode)
        self._attr_swing_mode = swing_mode
        self.async_write_ha_state()

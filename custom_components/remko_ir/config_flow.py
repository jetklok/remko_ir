"""Config flow for the Remko IR integration."""

from typing import Any, override

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow as HomeAssistantConfigFlow
from homeassistant.config_entries import ConfigFlowResult

from .const import CONF_REMOTE_TOPIC, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_REMOTE_TOPIC): vol.All(
            str,
            vol.Match(r"^(?=\S+$)[^+#]+$"),
        ),
    }
)


class ConfigFlow(HomeAssistantConfigFlow, domain=DOMAIN):
    """Handle a config flow for Remko IR."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            remote_topic = user_input[CONF_REMOTE_TOPIC]
            self._async_abort_entries_match({CONF_REMOTE_TOPIC: remote_topic})
            return self.async_create_entry(
                title=f"Remko RKL 495 via {remote_topic}", data=user_input
            )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

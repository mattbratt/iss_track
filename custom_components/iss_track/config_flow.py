"""Config flow for ISS Track."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)

from .const import (
    CONF_UNIT_SYSTEM,
    DEFAULT_UNIT_SYSTEM,
    DOMAIN,
    PANEL_TITLE,
    UNIT_SYSTEM_IMPERIAL,
    UNIT_SYSTEM_METRIC,
)

UNIT_SYSTEM_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_UNIT_SYSTEM, default=DEFAULT_UNIT_SYSTEM
        ): vol.In([UNIT_SYSTEM_IMPERIAL, UNIT_SYSTEM_METRIC]),
    }
)


class ISSTrackConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single-instance flow: pick a default unit system and create the entry."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title=PANEL_TITLE, data=user_input)
        return self.async_show_form(step_id="user", data_schema=UNIT_SYSTEM_SCHEMA)

    @staticmethod
    def async_get_options_flow(entry: ConfigEntry) -> ISSTrackOptionsFlow:
        return ISSTrackOptionsFlow()


class ISSTrackOptionsFlow(OptionsFlow):
    """Let the user change the default unit system after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_UNIT_SYSTEM,
            self.config_entry.data.get(CONF_UNIT_SYSTEM, DEFAULT_UNIT_SYSTEM),
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_UNIT_SYSTEM, default=current
                ): vol.In([UNIT_SYSTEM_IMPERIAL, UNIT_SYSTEM_METRIC]),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

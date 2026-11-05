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
from homeassistant.helpers import selector

from .const import (
    CONF_EVENING,
    CONF_FAINTEST_MAGNITUDE,
    CONF_MORNING,
    CONF_PEOPLE,
    CONF_QUALITIES,
    CONF_SKY_LIMIT,
    CONF_UNIT_SYSTEM,
    CONF_UPDATE_INTERVAL,
    CONF_WEATHER_ENTITY,
    DEFAULT_EVENING,
    DEFAULT_FAINTEST_MAGNITUDE,
    DEFAULT_MORNING,
    DEFAULT_QUALITIES,
    DEFAULT_SKY_LIMIT,
    DEFAULT_UNIT_SYSTEM,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAGNITUDE_BRIGHTEST,
    MAGNITUDE_FAINTEST,
    MAGNITUDE_STEP,
    PANEL_TITLE,
    UNIT_SYSTEM_IMPERIAL,
    UNIT_SYSTEM_METRIC,
    UPDATE_INTERVAL_MAX,
    UPDATE_INTERVAL_MIN,
)
from .coordinator import get_option
from .engine import QUALITIES, SKY_LIMITS

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


def _options_schema(entry: ConfigEntry) -> vol.Schema:
    """The same pass settings the panel edits, plus the ones only set here."""

    def current(key: str, default: Any) -> Any:
        return get_option(entry, key, default)

    return vol.Schema(
        {
            vol.Required(
                CONF_UNIT_SYSTEM, default=current(CONF_UNIT_SYSTEM, DEFAULT_UNIT_SYSTEM)
            ): vol.In([UNIT_SYSTEM_IMPERIAL, UNIT_SYSTEM_METRIC]),
            vol.Required(
                CONF_QUALITIES, default=current(CONF_QUALITIES, DEFAULT_QUALITIES)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(reversed(QUALITIES)),
                    multiple=True,
                    translation_key="quality",
                )
            ),
            vol.Required(
                CONF_FAINTEST_MAGNITUDE,
                default=current(CONF_FAINTEST_MAGNITUDE, DEFAULT_FAINTEST_MAGNITUDE),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MAGNITUDE_BRIGHTEST,
                    max=MAGNITUDE_FAINTEST,
                    step=MAGNITUDE_STEP,
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                CONF_EVENING, default=current(CONF_EVENING, DEFAULT_EVENING)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_MORNING, default=current(CONF_MORNING, DEFAULT_MORNING)
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_WEATHER_ENTITY,
                description={"suggested_value": current(CONF_WEATHER_ENTITY, None)},
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="weather")),
            vol.Required(
                CONF_SKY_LIMIT, default=current(CONF_SKY_LIMIT, DEFAULT_SKY_LIMIT)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(SKY_LIMITS), translation_key="sky_limit"
                )
            ),
            vol.Optional(
                CONF_PEOPLE, default=current(CONF_PEOPLE, [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="person", multiple=True)
            ),
            vol.Required(
                CONF_UPDATE_INTERVAL,
                default=current(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=UPDATE_INTERVAL_MIN,
                    max=UPDATE_INTERVAL_MAX,
                    step=5,
                    unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


class ISSTrackOptionsFlow(OptionsFlow):
    """Units, pass settings, sky forecast, tracked people and update pace."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_QUALITIES):
                errors[CONF_QUALITIES] = "no_quality"
            elif not user_input[CONF_EVENING] and not user_input[CONF_MORNING]:
                errors[CONF_MORNING] = "no_period"
            else:
                user_input[CONF_UPDATE_INTERVAL] = int(user_input[CONF_UPDATE_INTERVAL])
                user_input[CONF_FAINTEST_MAGNITUDE] = float(user_input[CONF_FAINTEST_MAGNITUDE])
                return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _options_schema(self.config_entry), user_input or {}
            ),
            errors=errors,
        )

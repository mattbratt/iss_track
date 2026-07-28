"""ISS Track: live ISS map panel served from the integration's own www folder."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import (
    async_register_built_in_panel,
    async_remove_panel,
)
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PANEL_ICON, PANEL_TITLE, PANEL_URL_PATH, STATIC_URL


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Serve the bundled frontend and add the ISS Track sidebar panel."""
    # Static routes cannot be unregistered, so only register once per runtime.
    if not hass.data.setdefault(DOMAIN, {}).get("static_registered"):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    STATIC_URL,
                    str(Path(__file__).parent / "www"),
                    cache_headers=False,
                )
            ]
        )
        hass.data[DOMAIN]["static_registered"] = True

    async_register_built_in_panel(
        hass,
        component_name="iframe",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        frontend_url_path=PANEL_URL_PATH,
        config={"url": f"{STATIC_URL}/my_iss.html"},
        require_admin=False,
        update=True,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove the sidebar panel."""
    async_remove_panel(hass, PANEL_URL_PATH)
    return True

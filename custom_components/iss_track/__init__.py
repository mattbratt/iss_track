"""ISS Track: live ISS map panel, pass predictions, entities and a dashboard card."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components import panel_custom
from homeassistant.components.frontend import add_extra_js_url, async_remove_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.loader import async_get_integration

from .const import (
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    OBSERVER_HOME,
    PANEL_ELEMENT,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL_PATH,
    STATIC_URL,
)
from .coordinator import IssTrackConfigEntry, IssTrackCoordinator, get_option
from .entity import OWNER_ISS
from .websocket import async_register_websocket

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.SENSOR]

_FRONTEND_PANELS = "frontend_panels"


async def async_setup_entry(hass: HomeAssistant, entry: IssTrackConfigEntry) -> bool:
    """Start the hub, then add the entities, the panel and the card."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    integration = await async_get_integration(hass, DOMAIN)
    version = str(integration.version or "0")

    # Static routes, API commands and the card script cannot be unregistered,
    # so each is registered once per run of Home Assistant.
    if not domain_data.get("static_registered"):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    STATIC_URL,
                    str(Path(__file__).parent / "www"),
                    cache_headers=False,
                )
            ]
        )
        domain_data["static_registered"] = True
    if not domain_data.get("frontend_registered"):
        async_register_websocket(hass)
        add_extra_js_url(hass, f"{STATIC_URL}/iss-track-card.js?v={version}")
        domain_data["frontend_registered"] = True

    coordinator = IssTrackCoordinator(hass, entry)
    try:
        await coordinator.async_start()
    except Exception:
        await coordinator.async_shutdown()
        raise
    entry.runtime_data = coordinator

    _async_remove_orphans(hass, entry, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if PANEL_URL_PATH in hass.data.get(_FRONTEND_PANELS, {}):
        async_remove_panel(hass, PANEL_URL_PATH)
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_ELEMENT,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        module_url=f"{STATIC_URL}/iss-track-panel.js?v={version}",
        embed_iframe=False,
        require_admin=False,
        config={"version": version, "static_url": STATIC_URL},
    )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


@callback
def _async_remove_orphans(
    hass: HomeAssistant, entry: IssTrackConfigEntry, coordinator: IssTrackCoordinator
) -> None:
    """Drop the entities and devices of people who are no longer tracked."""
    owners = {OWNER_ISS, *coordinator.books}
    entity_registry = er.async_get(hass)
    for registered in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        parts = registered.unique_id.split("|")
        if len(parts) == 3 and parts[1] not in owners:
            entity_registry.async_remove(registered.entity_id)
    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if not er.async_entries_for_device(entity_registry, device.id, include_disabled_entities=True):
            if (DOMAIN, entry.entry_id) not in device.identifiers:
                device_registry.async_update_device(
                    device.id, remove_config_entry_id=entry.entry_id
                )


async def _async_update_listener(hass: HomeAssistant, entry: IssTrackConfigEntry) -> None:
    """Pass settings apply in place; a change of people or pace needs a reload."""
    coordinator = entry.runtime_data
    people_changed = set(coordinator.people) != set(coordinator.books) - {OBSERVER_HOME}
    pace_changed = (
        int(get_option(entry, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))
        != coordinator.update_seconds
    )
    if people_changed or pace_changed:
        await hass.config_entries.async_reload(entry.entry_id)
    else:
        await coordinator.async_apply_options()


async def async_unload_entry(hass: HomeAssistant, entry: IssTrackConfigEntry) -> bool:
    """Remove the entities, stop the hub and take the panel out of the sidebar."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
        if PANEL_URL_PATH in hass.data.get(_FRONTEND_PANELS, {}):
            async_remove_panel(hass, PANEL_URL_PATH)
    return unloaded

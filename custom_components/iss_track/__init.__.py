"""The ISS Tracker integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

DOMAIN = "iss_track"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ISS Tracker from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    # Serve static files from www directory
    hass.http.register_static_path("/local/iss_track", hass.config.path("custom_components/iss_track/www"), cache_ok=True)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data.pop(DOMAIN, None)
    return True

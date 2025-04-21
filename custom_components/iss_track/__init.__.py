from .panel import setup_panel

DOMAIN = "iss_track"

async def async_setup(hass, config):
    setup_panel(hass)
    return True

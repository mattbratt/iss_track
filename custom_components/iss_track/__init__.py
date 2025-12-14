from .const import DOMAIN
from .panel import setup_panel

async def async_setup(hass, config):
    setup_panel(hass)
    return True

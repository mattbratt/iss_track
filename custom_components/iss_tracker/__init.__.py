from .panel import setup_panel

DOMAIN = "iss_tracker"

def setup(hass, config):
    setup_panel(hass)
    return True

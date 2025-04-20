from .panel import setup_panel

DOMAIN = "iss_track"

def setup(hass, config):
    setup_panel(hass)
    return True

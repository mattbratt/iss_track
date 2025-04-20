from homeassistant.components import frontend
from homeassistant.components.panel_custom import async_register_panel

def setup_panel(hass):
    hass.async_create_task(
        async_register_panel(
            hass,
            frontend_integration=DOMAIN,
            frontend_url_path="iss",
            module_url="/local/iss_tracker/my_iss.html",
            sidebar_title="ISS Tracker",
            sidebar_icon="mdi:satellite-variant",
            require_admin=False,
            config={},
            trust_external=True
        )
    )

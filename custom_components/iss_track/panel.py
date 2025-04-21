from homeassistant.components.panel_custom import async_register_panel

def setup_panel(hass):
    hass.async_create_task(_async_register_panel(hass))

async def _async_register_panel(hass):
    await async_register_panel(
        hass,
        frontend_integration="iss_track",
        frontend_url_path="iss",
        module_url="/local/iss_track/my_iss.html",
        sidebar_title="ISS Tracker",
        sidebar_icon="mdi:satellite-variant",
        require_admin=False,
        config={},
        trust_external=True
    )

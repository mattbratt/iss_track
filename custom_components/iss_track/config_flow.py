"""Config flow for ISS Tracker integration."""
from homeassistant import config_entries
import voluptuous as vol
import os
import yaml

class ISSTrackConfigFlow(config_entries.ConfigFlow, domain="iss_track"):
    """Handle a config flow for ISS Tracker."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            # Create dashboard on setup
            await self._create_dashboard()
            return self.async_create_entry(title="ISS Tracker", data={})

        return self.async_show_form(step_id="user")

    async def _create_dashboard(self):
        """Create the ISS Track dashboard."""
        dashboard_config = {
            "title": "ISS Track",
            "views": [{
                "title": "ISS Tracker",
                "cards": [{
                    "type": "iframe",
                    "url": "/local/iss_track/iss_track.html",
                    "aspect_ratio": "50%"
                }]
            }]
        }
        # Store dashboard config asynchronously
        dashboard_path = os.path.join(self.hass.config.path(), "custom_components/iss_track/dashboard.yaml")
        await self.hass.async_add_executor_job(self._write_dashboard_file, dashboard_path, dashboard_config)

    def _write_dashboard_file(self, path, config):
        """Write the dashboard config to file in a separate thread."""
        with open(path, "w") as f:
            yaml.dump(config, f)

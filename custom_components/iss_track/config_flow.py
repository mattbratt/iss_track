from homeassistant import config_entries

class ISSTrackConfigFlow(config_entries.ConfigFlow, domain="iss_track"):
    """Handle a config flow for ISS Track."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        # Since this integration requires no user input, we create an entry immediately.
        return self.async_create_entry(title="ISS Track", data={})

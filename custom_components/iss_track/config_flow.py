"""Config flow for ISS Tracker integration."""
from homeassistant import config_entries
import voluptuous as vol

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
                    "type": "custom:html-card",
                    "content": await self._get_html_content()
                }]
            }]
        }
        # Store dashboard config
        with open(f"{self.hass.config.path()}/custom_components/iss_track/dashboard.yaml", "w") as f:
            import yaml
            yaml.dump(dashboard_config, f)

    async def _get_html_content(self):
        """Generate HTML content with correct paths."""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8" />
            <title>ISS Tracker</title>
            <script src="/local/iss_track/astronomy.browser.js" defer></script>
            <script src="/local/iss_track/satellite.min.js" defer></script>
            <link href="https://fonts.googleapis.com/css2?family=Roboto+Condensed:wght@400;700&display=swap" rel="stylesheet">
            <!-- Include your CSS here -->
            <style>{css}</style>
        </head>
        <body>
            <div id="tracker-container">
                <canvas id="earthCanvas"></canvas>
                <div id="iss-tooltip" class="tooltip">Click to view live ISS feed</div>
                <div id="info-panel">
                    <div id="primary-data">
                        <div class="data-section"><div class="data-label" data-full="Latitude" data-abbr="Lat">Latitude</div><div id="lat" class="data-value">--</div></div>
                        <div class="data-section"><div class="data-label" data-full="Longitude" data-abbr="Lon">Longitude</div><div id="lon" class="data-value">--</div></div>
                        <div class="data-section"><div class="data-label" data-full="Altitude" data-abbr="Alt">Altitude</div><div id="alt" class="data-value">--</div></div>
                        <div class="data-section"><div class="data-label" data-full="Speed" data-abbr="Spd">Speed</div><div id="speed" class="data-value">--</div></div>
                        <div class="data-section"><div class="data-label" data-full="ISS Time" data-abbr="Time">ISS Time</div><div id="time" class="data-value">--</div></div>
                        <div class="data-section" id="units-section"><div id="units-label" data-full="Metric/Imperial" data-abbr="M/I">Metric/Imperial</div><div id="units-toggle"><div id="units-slider"></div></div></div>
                    </div>
                    <div id="fullscreen-toggle">⛶</div>
                    <div id="tle-info"></div>
                </div>
            </div>
            <div id="waitmsg">Loading TLE data...</div>
            <div id="videoModal" class="modal">
                <div class="modal-content">
                    <span class="close">×</span>
                    <iframe src="https://www.youtube.com/embed/jKHvbJe9c_Y?si=w6Pp60_zwzah_hxf" title="YouTube video player" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>
                </div>
            </div>
            <script>{js}</script>
        </body>
        </html>
        """
        # Replace image paths
        html = html.format(
            css=open("custom_components/iss_track/www/style.css").read(),  # Extract CSS to separate file
            js=open("custom_components/iss_track/www/script.js").read()     # Extract JS to separate file
        ).replace("images/", "/local/iss_track/images/")
        return html

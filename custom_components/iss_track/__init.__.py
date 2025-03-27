import os
import yaml
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace import dashboard

DOMAIN = "iss_track"

async def async_setup(hass, config):
    """Set up the ISS Track component."""
    # Register static paths for the frontend assets
    static_path = os.path.join(os.path.dirname(__file__), "www")
    hass.http.register_static_path(
        f"/local/iss_track", static_path, cache_duration=3600
    )

    # Define the dashboard configuration
    dashboard_config = {
        "title": "ISS Track",
        "views": [
            {
                "theme": "ios-dark-mode-blue-red",
                "title": "ISS Track",
                "icon": "mdi:space-station",
                "type": "panel",
                "subview": True,
                "badges": [],
                "cards": [
                    {
                        "type": "iframe",
                        "url": "/local/iss_track/iss_track.html",
                        "title": "ISS Map Location",
                        "aspect_ratio": "1.1",
                    }
                ],
            }
        ],
    }

    # Check if the "ISS Track" dashboard already exists
    dashboard_id = "ISS Track"
    lovelace_config_path = hass.config.path(f"lovelace/{dashboard_id}.yaml")

    try:
        # Try to load the existing dashboard
        with open(lovelace_config_path, "r") as f:
            existing_config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        # If the dashboard doesn't exist, create a new one
        existing_config = dashboard_config
    else:
        # If the dashboard exists, append the ISS Track view if it doesn't already exist
        existing_views = existing_config.get("views", [])
        if not any(view.get("title") == "ISS Track" for view in existing_views):
            existing_views.append(dashboard_config["views"][0])
            existing_config["views"] = existing_views

    # Save the updated dashboard configuration
    with open(lovelace_config_path, "w") as f:
        yaml.dump(existing_config, f)

    # Register the dashboard with Home Assistant
    hass.data.setdefault("lovelace", {}).setdefault("dashboards", {})
    if dashboard_id not in hass.data["lovelace"]["dashboards"]:
        hass.data["lovelace"]["dashboards"][dashboard_id] = dashboard.LovelaceYAML(
            hass, dashboard_id, lovelace_config_path
        )

    return True
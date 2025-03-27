import os
import yaml
import logging
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace import dashboard

_LOGGER = logging.getLogger(__name__)

DOMAIN = "iss_track"

async def async_setup(hass, config):
    """Set up the ISS Track component."""
    # Register static paths for the frontend assets
    try:
        static_path = os.path.join(os.path.dirname(__file__), "www")
        hass.http.register_static_path(
            f"/local/iss_track", static_path, cache_duration=3600
        )
    except Exception as e:
        _LOGGER.error(f"Failed to register static path for ISS Track: {e}")
        return False

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
    dashboard_id = "iss-track"
    lovelace_config_path = hass.config.path(f"lovelace/{dashboard_id}.yaml")

    try:
        # Try to load the existing dashboard
        with open(lovelace_config_path, "r") as f:
            existing_config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        # If the dashboard doesn't exist, create a new one
        existing_config = dashboard_config
    except Exception as e:
        _LOGGER.error(f"Failed to load existing dashboard configuration: {e}")
        return False
    else:
        # If the dashboard exists, append the ISS Track view if it doesn't already exist
        existing_views = existing_config.get("views", [])
        if not any(view.get("title") == "ISS Track" for view in existing_views):
            existing_views.append(dashboard_config["views"][0])
            existing_config["views"] = existing_views

    # Save the updated dashboard configuration
    try:
        with open(lovelace_config_path, "w") as f:
            yaml.safe_dump(existing_config, f)
    except Exception as e:
        _LOGGER.error(f"Failed to save dashboard configuration: {e}")
        return False

    # Register the dashboard with Home Assistant
    try:
        hass.data.setdefault("lovelace", {}).setdefault("dashboards", {})
        if dashboard_id not in hass.data["lovelace"]["dashboards"]:
            hass.data["lovelace"]["dashboards"][dashboard_id] = dashboard.LovelaceYAML(
                hass, dashboard_id, lovelace_config_path
            )
    except Exception as e:
        _LOGGER.error(f"Failed to register dashboard with Home Assistant: {e}")
        return False

    # Notify the user that the dashboard has been created
    try:
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "ISS Track Installed",
                "message": "A new 'ISS Track' dashboard has been created. Check it out in the sidebar!",
                "notification_id": "iss_track_dashboard_added",
            },
        )
    except Exception as e:
        _LOGGER.warning(f"Failed to create notification for ISS Track dashboard: {e}")

    return True

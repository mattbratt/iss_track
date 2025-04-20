"""Sensor platform for ISS Tracker."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import Entity
import requests
import satellitejs
from datetime import datetime

class ISSTrackSensor(SensorEntity):
    """Representation of an ISS Tracker Sensor."""

    def __init__(self, hass):
        self._hass = hass
        self._state = None
        self._attributes = {}
        self._tle_line1 = None
        self._tle_line2 = None

    @property
    def name(self):
        return "ISS Position"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    async def async_update(self):
        """Fetch new state data for the sensor."""
        # Fetch TLE data (simplified, matching your HTML logic)
        TLE_URL = "https://celestrak.com/NORAD/elements/stations.txt"
        try:
            response = await self._hass.async_add_executor_job(requests.get, TLE_URL)
            if response.status_code == 200:
                lines = response.text.split('\n')
                idx = lines.index("ISS (ZARYA)\n")
                self._tle_line1 = lines[idx + 1].strip()
                self._tle_line2 = lines[idx + 2].strip()
            else:
                # Fallback to dummy data
                self._tle_line1 = "1 49044U 21066A   25056.51033439  .00026620  00000+0  48205-3 0  9999"
                self._tle_line2 = "2 49044  51.6359 140.1589 0006082 313.5519  46.4964 15.49435478203179"
        except Exception:
            self._tle_line1 = "1 49044U 21066A   25056.51033439  .00026620  00000+0  48205-3 0  9999"
            self._tle_line2 = "2 49044  51.6359 140.1589 0006082 313.5519  46.4964 15.49435478203179"

        # Calculate position
        satrec = satellitejs.twoline2satrec(self._tle_line1, self._tle_line2)
        now = datetime.utcnow()
        pv = satellitejs.propagate(satrec, now)
        gmst = satellitejs.gstime(now)
        gd = satellitejs.eci_to_geodetic(pv.position, gmst)
        
        lat = satellitejs.degrees_lat(gd.latitude)
        lon = satellitejs.degrees_long(gd.longitude)
        alt = gd.height

        self._state = f"{lat:.2f}, {lon:.2f}"
        self._attributes = {
            "latitude": lat,
            "longitude": lon,
            "altitude": alt,
            "tle_line1": self._tle_line1,
            "tle_line2": self._tle_line2
        }

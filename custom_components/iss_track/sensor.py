"""Sensor platform for ISS Tracker."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import Entity
import satellitejs

class ISSTrackSensor(SensorEntity):
    """Representation of an ISS Tracker Sensor."""

    def __init__(self, hass):
        self._hass = hass
        self._state = None
        self._attributes = {}

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
        # This would ideally fetch TLE data and compute position
        # For simplicity, we'll simulate it here
        tle_line1 = "1 49044U 21066A   25056.51033439  .00026620  00000+0  48205-3 0  9999"
        tle_line2 = "2 49044  51.6359 140.1589 0006082 313.5519  46.4964 15.49435478203179"
        satrec = satellitejs.twoline2satrec(tle_line1, tle_line2)
        position_and_velocity = satellitejs.propagate(satrec, new Date())
        gmst = satellitejs.gstime(new Date())
        position_gd = satellitejs.eci_to_geodetic(position_and_velocity.position, gmst)
        
        self._state = f"{position_gd.latitude:.2f}, {position_gd.longitude:.2f}"
        self._attributes = {
            "latitude": position_gd.latitude,
            "longitude": position_gd.longitude,
            "altitude": position_gd.height,
        }

"""Sun position: the one place it is computed.

Low-precision solar coordinates from the Astronomical Almanac (as given by
Vallado). Good to about 0.01 degrees, which is far finer than anything here
needs: the day/night line, twilight at the observer, and Earth's shadow.
"""
from __future__ import annotations

import math
from datetime import datetime

from .orbit import EARTH_RADIUS_KM, ObserverFrame, Vector, dot, gmst, julian, rotate_z

AU_KM = 149597870.7


def sun_vector(when: datetime) -> Vector:
    """Unit vector from Earth's centre to the Sun, in the inertial frame."""
    jd, fr = julian(when)
    centuries = ((jd - 2451545.0) + fr) / 36525.0
    mean_longitude = math.radians((280.460 + 36000.771 * centuries) % 360.0)
    mean_anomaly = math.radians((357.5291092 + 35999.05034 * centuries) % 360.0)
    ecliptic_longitude = (
        mean_longitude
        + math.radians(1.914666471) * math.sin(mean_anomaly)
        + math.radians(0.019994643) * math.sin(2 * mean_anomaly)
    )
    obliquity = math.radians(23.439291 - 0.0130042 * centuries)
    return (
        math.cos(ecliptic_longitude),
        math.cos(obliquity) * math.sin(ecliptic_longitude),
        math.sin(obliquity) * math.sin(ecliptic_longitude),
    )


def sun_subpoint(when: datetime) -> tuple[float, float]:
    """Latitude and longitude, in degrees, where the Sun is overhead."""
    jd, fr = julian(when)
    x, y, z = rotate_z(sun_vector(when), gmst(jd, fr))
    longitude = math.degrees(math.atan2(y, x))
    return math.degrees(math.asin(z)), (longitude + 180.0) % 360.0 - 180.0


def sun_elevation(frame: ObserverFrame, sun: Vector, theta: float) -> float:
    """Sun's elevation in degrees for an observer; theta is sidereal time."""
    return math.degrees(math.asin(max(-1.0, min(1.0, dot(rotate_z(sun, theta), frame.up)))))


def is_sunlit(position: Vector, sun: Vector) -> bool:
    """True when an inertial position (km) is outside Earth's shadow cylinder."""
    along = dot(position, sun)
    if along >= 0:
        return True
    across_sq = dot(position, position) - along * along
    return across_sq > EARTH_RADIUS_KM * EARTH_RADIUS_KM

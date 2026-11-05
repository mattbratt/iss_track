"""ISS orbit propagation: the one place a position is ever computed.

Pure Python plus the sgp4 package. Nothing in this package imports Home
Assistant, so it can be tested on its own.

Frames: sgp4 returns TEME (an inertial frame). Rotating by Greenwich mean
sidereal time gives an Earth-fixed frame, which is accurate to well under a
kilometre for this purpose (polar motion is ignored, as satellite.js does).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sgp4.api import Satrec, jday

ISS_CATALOG_NUMBER = "25544"

EARTH_RADIUS_KM = 6378.137
_FLATTENING = 1 / 298.257223563
_E2 = _FLATTENING * (2 - _FLATTENING)
_TWO_PI = 2 * math.pi
_J2000 = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)

Vector = tuple[float, float, float]


class OrbitError(ValueError):
    """The orbital elements are unusable, or propagation failed."""


@dataclass(frozen=True, slots=True)
class Observer:
    """A place on the ground, in degrees and metres."""

    latitude: float
    longitude: float
    elevation_m: float = 0.0


@dataclass(frozen=True, slots=True)
class ObserverFrame:
    """An observer's Earth-fixed position and local east/north/up axes."""

    position: Vector
    east: Vector
    north: Vector
    up: Vector


@dataclass(frozen=True, slots=True)
class State:
    """Where the station is at one instant."""

    when: datetime
    latitude: float
    longitude: float
    altitude_km: float
    speed_kms: float
    ecef: Vector
    teme: Vector


def julian(when: datetime) -> tuple[float, float]:
    """Split a timezone-aware datetime into the Julian date pair sgp4 wants."""
    if when.tzinfo is None:
        raise OrbitError("datetime must be timezone-aware")
    utc = when.astimezone(timezone.utc)
    return jday(
        utc.year,
        utc.month,
        utc.day,
        utc.hour,
        utc.minute,
        utc.second + utc.microsecond / 1e6,
    )


def gmst(jd: float, fr: float) -> float:
    """Greenwich mean sidereal time in radians (Vallado, IAU-82)."""
    tut1 = ((jd - 2451545.0) + fr) / 36525.0
    seconds = (
        -6.2e-6 * tut1**3
        + 0.093104 * tut1**2
        + (876600.0 * 3600 + 8640184.812866) * tut1
        + 67310.54841
    )
    return math.radians(seconds / 240.0) % _TWO_PI


def rotate_z(vector: Vector, angle: float) -> Vector:
    """Rotate a vector about the z axis by -angle (inertial to Earth-fixed)."""
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    x, y, z = vector
    return (x * cos_a + y * sin_a, -x * sin_a + y * cos_a, z)


def ecef_to_geodetic(ecef: Vector) -> tuple[float, float, float]:
    """Earth-fixed km to WGS84 latitude and longitude (degrees) and height (km)."""
    x, y, z = ecef
    radius = math.hypot(x, y)
    longitude = math.atan2(y, x)
    latitude = math.atan2(z, radius)
    curvature = 1.0
    for _ in range(20):
        sin_lat = math.sin(latitude)
        curvature = 1 / math.sqrt(1 - _E2 * sin_lat * sin_lat)
        latitude = math.atan2(z + EARTH_RADIUS_KM * curvature * _E2 * sin_lat, radius)
    height = radius / math.cos(latitude) - EARTH_RADIUS_KM * curvature
    return math.degrees(latitude), math.degrees(longitude), height


def observer_frame(observer: Observer) -> ObserverFrame:
    """Earth-fixed position and local axes for a place on the ground."""
    lat = math.radians(observer.latitude)
    lon = math.radians(observer.longitude)
    sin_lat, cos_lat = math.sin(lat), math.cos(lat)
    sin_lon, cos_lon = math.sin(lon), math.cos(lon)
    height = observer.elevation_m / 1000.0
    curvature = EARTH_RADIUS_KM / math.sqrt(1 - _E2 * sin_lat * sin_lat)
    position = (
        (curvature + height) * cos_lat * cos_lon,
        (curvature + height) * cos_lat * sin_lon,
        (curvature * (1 - _E2) + height) * sin_lat,
    )
    return ObserverFrame(
        position=position,
        east=(-sin_lon, cos_lon, 0.0),
        north=(-sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat),
        up=(cos_lat * cos_lon, cos_lat * sin_lon, sin_lat),
    )


def dot(a: Vector, b: Vector) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def look_angles(frame: ObserverFrame, ecef: Vector) -> tuple[float, float, float]:
    """Azimuth and elevation in degrees, and range in km, of an Earth-fixed point."""
    delta = (
        ecef[0] - frame.position[0],
        ecef[1] - frame.position[1],
        ecef[2] - frame.position[2],
    )
    distance = math.sqrt(dot(delta, delta))
    east = dot(delta, frame.east)
    north = dot(delta, frame.north)
    up = dot(delta, frame.up)
    elevation = math.degrees(math.asin(max(-1.0, min(1.0, up / distance))))
    azimuth = math.degrees(math.atan2(east, north)) % 360.0
    return azimuth, elevation, distance


def ground_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points on the ground."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * 6371.0088 * math.asin(min(1.0, math.sqrt(a)))


_COMPASS = (
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
)


def compass(azimuth: float) -> str:
    """Sixteen-point compass name for an azimuth in degrees."""
    return _COMPASS[int((azimuth % 360.0) / 22.5 + 0.5) % 16]


def _checksum_ok(line: str) -> bool:
    total = 0
    for char in line[:68]:
        if char.isdigit():
            total += int(char)
        elif char == "-":
            total += 1
    return line[68:69].isdigit() and total % 10 == int(line[68])


def parse_tle(text: str) -> tuple[str, str]:
    """Pull the ISS element lines out of a Celestrak reply, or raise OrbitError."""
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    line1 = next((ln for ln in lines if ln.startswith("1 " + ISS_CATALOG_NUMBER)), None)
    line2 = next((ln for ln in lines if ln.startswith("2 " + ISS_CATALOG_NUMBER)), None)
    if line1 is None or line2 is None:
        raise OrbitError("ISS element lines not found")
    if len(line1) < 69 or len(line2) < 69:
        raise OrbitError("element lines are truncated")
    if not _checksum_ok(line1) or not _checksum_ok(line2):
        raise OrbitError("element line checksum mismatch")
    return line1[:69], line2[:69]


class Orbit:
    """The ISS orbit described by one two-line element set."""

    def __init__(self, line1: str, line2: str) -> None:
        self.line1, self.line2 = parse_tle(f"{line1}\n{line2}")
        self._sat = Satrec.twoline2rv(self.line1, self.line2)
        if self._sat.error != 0 or self._sat.no_kozai <= 0:
            raise OrbitError("element set could not be initialised")
        self.epoch = _J2000 + timedelta(
            days=(self._sat.jdsatepoch - 2451545.0) + self._sat.jdsatepochF
        )
        self.period_minutes = _TWO_PI / self._sat.no_kozai

    def teme(self, when: datetime) -> tuple[Vector, Vector, float]:
        """Inertial position (km), velocity (km/s) and sidereal time (rad)."""
        jd, fr = julian(when)
        error, position, velocity = self._sat.sgp4(jd, fr)
        if error != 0:
            raise OrbitError(f"propagation failed with sgp4 error {error}")
        return tuple(position), tuple(velocity), gmst(jd, fr)

    def state(self, when: datetime) -> State:
        """Position, altitude and speed at one instant."""
        position, velocity, theta = self.teme(when)
        ecef = rotate_z(position, theta)
        latitude, longitude, altitude = ecef_to_geodetic(ecef)
        return State(
            when=when,
            latitude=latitude,
            longitude=longitude,
            altitude_km=altitude,
            speed_kms=math.sqrt(dot(velocity, velocity)),
            ecef=ecef,
            teme=position,
        )


def ground_track(
    orbit: Orbit, start: datetime, end: datetime, step_seconds: int
) -> list[list[float]]:
    """Rows of [latitude, longitude, altitude km, speed km/s] from start to end."""
    rows: list[list[float]] = []
    step = timedelta(seconds=step_seconds)
    when = start
    while when <= end:
        state = orbit.state(when)
        rows.append(
            [
                round(state.latitude, 4),
                round(state.longitude, 4),
                round(state.altitude_km, 2),
                round(state.speed_kms, 4),
            ]
        )
        when += step
    return rows

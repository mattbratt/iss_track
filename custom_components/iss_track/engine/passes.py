"""Visible ISS passes: the one place a pass, its quality and its brightness
are computed.

A pass is visible while three things hold together: the station is at least
MIN_ELEVATION above the horizon, it is in sunlight, and the sky at the
observer is dark (Sun at or below SUN_DARK_ELEVATION). Everything reported
about a pass describes that visible stretch, not the whole geometric pass.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from .orbit import (
    Observer,
    ObserverFrame,
    Orbit,
    compass,
    dot,
    gmst,
    julian,
    look_angles,
    observer_frame,
    rotate_z,
)
from .sun import is_sunlit, sun_elevation, sun_vector

MIN_ELEVATION = 10.0
SUN_DARK_ELEVATION = -6.0
MIN_VISIBLE_SECONDS = 60
PATH_STEP_SECONDS = 5

# Brightness at 1000 km range and a 90 degree Sun-station-observer angle, the
# convention published ISS predictions use, with a linear phase term. Both
# figures were checked against published predictions for seven passes on
# 2026-11-04 and agreed to within 0.1 magnitude. It is still an estimate:
# solar-array flares are not modelled.
STANDARD_MAGNITUDE = -1.8
PHASE_COEFFICIENT = 0.012  # magnitudes per degree away from 90

QUALITY_POOR = "poor"
QUALITY_FAIR = "fair"
QUALITY_GOOD = "good"
QUALITY_EXCELLENT = "excellent"
QUALITIES = (QUALITY_POOR, QUALITY_FAIR, QUALITY_GOOD, QUALITY_EXCELLENT)

PERIOD_EVENING = "evening"
PERIOD_MORNING = "morning"

_COARSE = timedelta(seconds=20)
_FINE = timedelta(seconds=1)


def quality_for(peak_elevation: float) -> str:
    """Quality band for the highest point of the visible stretch.

    The peak is rounded to a whole degree first, so the bands read exactly
    as published: 10-20 poor, 21-40 fair, 41-60 good, 61-90 excellent.
    """
    degrees = math.floor(peak_elevation + 0.5)
    if degrees >= 61:
        return QUALITY_EXCELLENT
    if degrees >= 41:
        return QUALITY_GOOD
    if degrees >= 21:
        return QUALITY_FAIR
    return QUALITY_POOR


def estimate_magnitude(range_km: float, phase_degrees: float) -> float:
    """Apparent magnitude from range and the Sun-station-observer angle."""
    return (
        STANDARD_MAGNITUDE
        - 15.0
        + 5.0 * math.log10(range_km)
        + PHASE_COEFFICIENT * (phase_degrees - 90.0)
    )


@dataclass(frozen=True, slots=True)
class Pass:
    """One visible pass. start, peak and end bound the visible stretch."""

    start: datetime
    peak: datetime
    end: datetime
    rise: datetime
    set: datetime
    peak_elevation: float
    peak_azimuth: float
    start_azimuth: float
    start_elevation: float
    end_azimuth: float
    end_elevation: float
    max_elevation: float
    magnitude: float
    quality: str
    period: str
    starts_in_shadow: bool
    ends_in_shadow: bool
    path: tuple[tuple[int, float, float], ...]

    @property
    def duration_seconds(self) -> int:
        return int((self.end - self.start).total_seconds())

    def as_dict(self, *, with_path: bool = True) -> dict:
        """JSON-ready form, every float rounded."""
        data = {
            "start": self.start.isoformat(),
            "peak": self.peak.isoformat(),
            "end": self.end.isoformat(),
            "duration_seconds": self.duration_seconds,
            "peak_elevation": round(self.peak_elevation, 1),
            "peak_direction": compass(self.peak_azimuth),
            "start_azimuth": round(self.start_azimuth, 1),
            "start_direction": compass(self.start_azimuth),
            "start_elevation": round(self.start_elevation, 1),
            "end_azimuth": round(self.end_azimuth, 1),
            "end_direction": compass(self.end_azimuth),
            "end_elevation": round(self.end_elevation, 1),
            "magnitude": round(self.magnitude, 1),
            "quality": self.quality,
            "period": self.period,
            "starts_in_shadow": self.starts_in_shadow,
            "ends_in_shadow": self.ends_in_shadow,
        }
        if with_path:
            data["path"] = [list(point) for point in self.path]
        return data


@dataclass(frozen=True, slots=True)
class Criteria:
    """Which visible passes the user wants to hear about."""

    qualities: frozenset[str] = frozenset({QUALITY_GOOD, QUALITY_EXCELLENT})
    faintest_magnitude: float = -2.0
    evening: bool = True
    morning: bool = False

    def reason(self, candidate: Pass) -> str | None:
        """Why a pass is left out: "quality", "brightness" or "period". None
        when it matches. The one place the decision is made."""
        if candidate.quality not in self.qualities:
            return "quality"
        if candidate.magnitude > self.faintest_magnitude:
            return "brightness"
        wanted = self.evening if candidate.period == PERIOD_EVENING else self.morning
        return None if wanted else "period"

    def matches(self, candidate: Pass) -> bool:
        return self.reason(candidate) is None


def _elevation(orbit: Orbit, frame: ObserverFrame, when: datetime) -> float:
    position, _velocity, theta = orbit.teme(when)
    return look_angles(frame, rotate_z(position, theta))[1]


def _coarse_step(elevation: float) -> timedelta:
    """How far the scan may jump. The station climbs at most a few degrees
    in 20 seconds, so far below the horizon a longer stride is safe."""
    if elevation < -40.0:
        return timedelta(seconds=300)
    if elevation < -20.0:
        return timedelta(seconds=120)
    if elevation < 0.0:
        return timedelta(seconds=40)
    return _COARSE


def _resolve(
    orbit: Orbit, frame: ObserverFrame, window_start: datetime, window_end: datetime
) -> Pass | None:
    """Sample one coarse window every second and describe its visible stretch."""
    sun = sun_vector(window_start + (window_end - window_start) / 2)
    rows = []
    when = window_start
    while when <= window_end:
        position, _velocity, theta = orbit.teme(when)
        azimuth, elevation, distance = look_angles(frame, rotate_z(position, theta))
        above = elevation >= MIN_ELEVATION
        lit = is_sunlit(position, sun)
        dark = sun_elevation(frame, sun, theta) <= SUN_DARK_ELEVATION
        rows.append((when, azimuth, elevation, distance, above, lit, dark, position, theta))
        when += _FINE

    best: tuple[int, int] | None = None
    run_start: int | None = None
    for index, row in enumerate(rows + [None]):
        visible = row is not None and row[4] and row[5] and row[6]
        if visible and run_start is None:
            run_start = index
        elif not visible and run_start is not None:
            if best is None or index - run_start > best[1] - best[0]:
                best = (run_start, index)
            run_start = None
    if best is None:
        return None
    first, stop = best
    last = stop - 1
    if (rows[last][0] - rows[first][0]).total_seconds() < MIN_VISIBLE_SECONDS:
        return None

    run = rows[first:stop]
    peak_row = max(run, key=lambda row: row[2])
    # Brightness is quoted at the highest point, as published pass tables do.
    observer = rotate_z(frame.position, -peak_row[8])
    to_observer = (
        observer[0] - peak_row[7][0],
        observer[1] - peak_row[7][1],
        observer[2] - peak_row[7][2],
    )
    cos_phase = dot(to_observer, sun) / math.sqrt(dot(to_observer, to_observer))
    phase_degrees = math.degrees(math.acos(max(-1.0, min(1.0, cos_phase))))
    magnitude = estimate_magnitude(peak_row[3], phase_degrees)

    above_rows = [row for row in rows if row[4]]
    earlier = rows[first][0] - timedelta(minutes=10)
    sun_before = sun_elevation(frame, sun_vector(earlier), gmst(*julian(earlier)))
    sun_at_start = sun_elevation(frame, sun, rows[first][8])
    period = PERIOD_EVENING if sun_at_start < sun_before else PERIOD_MORNING

    path = [
        (offset, round(run[offset][1], 1), round(run[offset][2], 1))
        for offset in range(0, len(run), PATH_STEP_SECONDS)
    ]
    if path[-1][0] != len(run) - 1:
        path.append((len(run) - 1, round(run[-1][1], 1), round(run[-1][2], 1)))

    return Pass(
        start=rows[first][0],
        peak=peak_row[0],
        end=rows[last][0],
        rise=above_rows[0][0],
        set=above_rows[-1][0],
        peak_elevation=peak_row[2],
        peak_azimuth=peak_row[1],
        start_azimuth=rows[first][1],
        start_elevation=rows[first][2],
        end_azimuth=rows[last][1],
        end_elevation=rows[last][2],
        max_elevation=max(row[2] for row in above_rows),
        magnitude=magnitude,
        quality=quality_for(peak_row[2]),
        period=period,
        starts_in_shadow=first > 0 and rows[first - 1][4] and not rows[first - 1][5],
        ends_in_shadow=stop < len(rows) and rows[stop][4] and not rows[stop][5],
        path=tuple(path),
    )


def find_passes(
    orbit: Orbit, observer: Observer, start: datetime, end: datetime
) -> list[Pass]:
    """Every visible pass whose window opens between start and end.

    Returns all of them, whatever their quality: filtering is Criteria's job.
    """
    frame = observer_frame(observer)
    passes: list[Pass] = []
    when = start
    window_start: datetime | None = None
    while when <= end:
        elevation = _elevation(orbit, frame, when)
        if elevation >= MIN_ELEVATION:
            if window_start is None:
                window_start = max(start, when - _COARSE)
            when += _COARSE
            continue
        if window_start is not None:
            found = _resolve(orbit, frame, window_start, when)
            if found is not None:
                passes.append(found)
            window_start = None
        when += _coarse_step(elevation)
    if window_start is not None:
        found = _resolve(orbit, frame, window_start, when + timedelta(minutes=12))
        if found is not None:
            passes.append(found)
    return passes


def look_now(
    orbit: Orbit, observer: Observer, when: datetime
) -> tuple[float, float, float]:
    """Azimuth, elevation (degrees) and range (km) of the station right now."""
    position, _velocity, theta = orbit.teme(when)
    return look_angles(observer_frame(observer), rotate_z(position, theta))

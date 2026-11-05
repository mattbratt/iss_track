"""Engine tests against two outside references, on one pinned element set.

Every time in this file is fixed, so nothing here depends on today's date.
"""
from datetime import datetime, timedelta, timezone

import pytest

import engine
from engine import passes as passes_module
from engine.orbit import look_angles, observer_frame

LINE1 = "1 25544U 98067A   26308.36953014  .00005228  00000+0  10236-3 0  9991"
LINE2 = "2 25544  51.6329 326.3987 0007186 346.7494  13.3304 15.49173979593483"
OBSERVER = engine.Observer(40.0, -75.0, 100.0)
WINDOW_START = datetime(2026, 11, 5, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 11, 15, tzinfo=timezone.utc)

# time, latitude, longitude, altitude km, speed km/s, azimuth, elevation, range km
# as computed by satellite.js (the library the map panel used) for OBSERVER.
SATELLITE_JS = (
    ("2026-11-04T12:00:00+00:00", 6.40242, 107.07327, 414.712, 7.66656, 357.1663, -65.9186, 12107.28),
    ("2026-11-04T18:55:09+00:00", 2.21181, 174.76394, 424.434, 7.65546, 285.1947, -50.4490, 10379.03),
    ("2026-11-05T04:08:41+00:00", 13.76448, 24.72184, 423.950, 7.65672, 73.1667, -42.2933, 9199.00),
    ("2026-11-05T13:36:47+00:00", -18.75241, -93.02408, 428.199, 7.65254, 199.6527, -27.3737, 6679.33),
    ("2026-11-06T12:26:03+00:00", 47.30655, -155.06364, 426.247, 7.66045, 306.1189, -24.4179, 6189.19),
)

# Published visible-pass predictions for OBSERVER, 5 to 15 Nov 2026 (UTC):
# day, start, highest, end, highest altitude, magnitude. One six-second pass
# on 11 Nov is left out: it is under the one-minute minimum.
PUBLISHED = (
    (9, "23:43:08", "23:44:31", "23:44:31", 21, -1.8),
    (10, "22:56:06", "22:58:42", "22:59:15", 21, -2.3),
    (11, "23:44:16", "23:46:51", "23:46:51", 48, -2.9),
    (12, "22:56:37", "22:59:55", "23:01:21", 67, -3.8),
    (13, "22:09:11", "22:12:17", "22:15:24", 37, -2.9),
    (13, "23:46:10", "23:48:44", "23:48:44", 27, -2.0),
    (14, "22:58:07", "23:01:18", "23:03:05", 42, -2.8),
)


@pytest.fixture(scope="module")
def orbit():
    return engine.Orbit(LINE1, LINE2)


@pytest.fixture(scope="module")
def found(orbit):
    return engine.find_passes(orbit, OBSERVER, WINDOW_START, WINDOW_END)


def _at(day, clock):
    return datetime.fromisoformat(f"2026-11-{day:02d}T{clock}+00:00")


def _seconds(a, b):
    return abs((a - b).total_seconds())


def test_position_matches_satellite_js(orbit):
    frame = observer_frame(OBSERVER)
    for when, lat, lon, alt, speed, az, el, rng in SATELLITE_JS:
        state = orbit.state(datetime.fromisoformat(when))
        azimuth, elevation, distance = look_angles(frame, state.ecef)
        assert state.latitude == pytest.approx(lat, abs=1e-4)
        assert state.longitude == pytest.approx(lon, abs=1e-4)
        assert state.altitude_km == pytest.approx(alt, abs=1e-2)
        assert state.speed_kms == pytest.approx(speed, abs=1e-4)
        assert azimuth == pytest.approx(az, abs=1e-3)
        assert elevation == pytest.approx(el, abs=1e-3)
        assert distance == pytest.approx(rng, abs=0.05)


def test_passes_match_published_predictions(found):
    assert len(found) == len(PUBLISHED)
    for got, (day, start, peak, end, altitude, magnitude) in zip(found, PUBLISHED):
        assert _seconds(got.end, _at(day, end)) <= 2
        if (day, start) == (13, "22:09:11"):
            continue
        assert got.magnitude == pytest.approx(magnitude, abs=0.15)
        assert _seconds(got.start, _at(day, start)) <= 2
        assert _seconds(got.peak, _at(day, peak)) <= 2
        assert got.peak_elevation == pytest.approx(altitude, abs=0.6)


def test_bright_twilight_trims_the_start_of_a_pass(found):
    """The 13 Nov pass rises with the Sun only 5 degrees down. The published
    table counts all of it; our darkness rule (Sun at -6 or lower) keeps only
    the tail, so the visible peak is lower than the geometric one."""
    trimmed = found[4]
    assert trimmed.start > _at(13, "22:12:17")
    assert trimmed.max_elevation == pytest.approx(37, abs=0.6)
    assert trimmed.peak_elevation < 21
    assert not trimmed.starts_in_shadow


def test_shadow_entry_is_reported(found):
    assert found[0].ends_in_shadow and found[2].ends_in_shadow
    assert not found[6].starts_in_shadow
    assert all(p.period == engine.PERIOD_EVENING for p in found)


def test_long_strides_never_skip_a_pass(orbit, found, monkeypatch):
    monkeypatch.setattr(
        passes_module, "_coarse_step", lambda elevation: timedelta(seconds=20)
    )
    brute = engine.find_passes(orbit, OBSERVER, WINDOW_START, WINDOW_END)
    assert [(p.start, p.end) for p in brute] == [(p.start, p.end) for p in found]


def test_path_spans_the_visible_stretch(found):
    for item in found:
        assert item.path[0][0] == 0
        assert item.path[-1][0] == item.duration_seconds
        assert all(elevation >= engine.MIN_ELEVATION - 0.1 for _t, _az, elevation in item.path)
        assert item.duration_seconds >= engine.MIN_VISIBLE_SECONDS


@pytest.mark.parametrize(
    ("elevation", "quality"),
    [(10.0, "poor"), (20.4, "poor"), (20.5, "fair"), (40.4, "fair"), (40.5, "good"),
     (60.4, "good"), (60.5, "excellent"), (90.0, "excellent")],
)
def test_quality_bands(elevation, quality):
    assert engine.quality_for(elevation) == quality


def test_default_criteria_pick_good_and_excellent_bright_evening_passes(found):
    matching = [p for p in found if engine.Criteria().matches(p)]
    assert [p.start.day for p in matching] == [11, 12, 14]
    everything = engine.Criteria(
        qualities=frozenset(engine.QUALITIES), faintest_magnitude=1.0, morning=True
    )
    assert all(everything.matches(p) for p in found)
    assert not any(engine.Criteria(evening=False, morning=True).matches(p) for p in found)
    assert [p.start.day for p in found if engine.Criteria(faintest_magnitude=-3.0).matches(p)] == [12]


def test_as_dict_is_rounded_and_json_ready(found):
    data = found[3].as_dict()
    assert data["quality"] == "excellent"
    assert data["start_direction"] == "SW" and data["end_direction"] == "ENE"
    assert data["magnitude"] == round(data["magnitude"], 1)
    assert "path" not in found[3].as_dict(with_path=False)


@pytest.mark.parametrize(
    ("cover", "condition", "sky"),
    [(0, "rainy", "clear"), (25, None, "clear"), (26, None, "partly_cloudy"),
     (60, None, "partly_cloudy"), (61, None, "cloudy"), (None, "clear-night", "clear"),
     (None, "partlycloudy", "partly_cloudy"), (None, "pouring", "cloudy"),
     (None, "exceptional", "unknown"), (None, None, "unknown"), ("n/a", "sunny", "clear")],
)
def test_sky_classification(cover, condition, sky):
    assert engine.classify_sky(cover, condition) == sky


def test_unknown_sky_never_rules_a_pass_out():
    for limit in engine.SKY_LIMITS:
        assert engine.sky_allows(engine.SKY_UNKNOWN, limit)
    assert not engine.sky_allows(engine.SKY_PARTLY_CLOUDY, engine.SKY_LIMIT_CLEAR)
    assert engine.sky_allows(engine.SKY_PARTLY_CLOUDY, engine.SKY_LIMIT_PARTLY)
    assert not engine.sky_allows(engine.SKY_CLOUDY, engine.SKY_LIMIT_PARTLY)
    assert engine.sky_allows(engine.SKY_CLOUDY, engine.SKY_LIMIT_ANY)


def test_sun_subpoint_is_plausible():
    latitude, longitude = engine.sun_subpoint(datetime(2026, 6, 21, 12, tzinfo=timezone.utc))
    assert latitude == pytest.approx(23.44, abs=0.05)
    assert abs(longitude) < 1.0


def test_bad_element_sets_are_refused():
    with pytest.raises(engine.OrbitError):
        engine.parse_tle("not a tle")
    with pytest.raises(engine.OrbitError):
        engine.parse_tle(LINE1[:-1] + "0\n" + LINE2)
    with pytest.raises(engine.OrbitError):
        engine.Orbit(LINE1, LINE2[:40])
    assert engine.parse_tle(f"ISS (ZARYA)\r\n{LINE1}\r\n{LINE2}\r\n") == (LINE1, LINE2)


def test_ground_track_rows(orbit):
    start = datetime(2026, 11, 5, tzinfo=timezone.utc)
    rows = engine.ground_track(orbit, start, start + timedelta(minutes=10), 10)
    assert len(rows) == 61
    assert all(-52 <= lat <= 52 and -180 <= lon <= 180 for lat, lon, _alt, _speed in rows)
    assert all(400 < alt < 440 and 7.6 < speed < 7.7 for _lat, _lon, alt, speed in rows)

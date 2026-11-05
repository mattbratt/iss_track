"""Constants for ISS Track."""
from datetime import timedelta

DOMAIN = "iss_track"

PANEL_TITLE = "ISS Track"
PANEL_ICON = "mdi:space-station"
PANEL_URL_PATH = "iss-track"
PANEL_ELEMENT = "iss-track-panel"
STATIC_URL = "/iss_track_static"

CONF_UNIT_SYSTEM = "unit_system"
UNIT_SYSTEM_IMPERIAL = "imperial"
UNIT_SYSTEM_METRIC = "metric"
DEFAULT_UNIT_SYSTEM = UNIT_SYSTEM_IMPERIAL

# Pass settings. One record, edited from the panel or the Configure dialog.
CONF_QUALITIES = "qualities"
CONF_FAINTEST_MAGNITUDE = "faintest_magnitude"
CONF_EVENING = "evening"
CONF_MORNING = "morning"
CONF_WEATHER_ENTITY = "weather_entity"
CONF_SKY_LIMIT = "sky_limit"
CONF_PEOPLE = "people"
CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_QUALITIES = ["good", "excellent"]
DEFAULT_FAINTEST_MAGNITUDE = -2.0
DEFAULT_EVENING = True
DEFAULT_MORNING = False
DEFAULT_SKY_LIMIT = "partly_cloudy"
DEFAULT_UPDATE_INTERVAL = 30

MAGNITUDE_BRIGHTEST = -4.0
MAGNITUDE_FAINTEST = 1.0
MAGNITUDE_STEP = 0.5
UPDATE_INTERVAL_MIN = 5
UPDATE_INTERVAL_MAX = 300

TLE_URL = "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=2le"
TLE_REFRESH = timedelta(hours=2)
TLE_STALE_AFTER = timedelta(days=3)
ISSUE_STALE_TLE = "stale_tle"

PASS_HORIZON = timedelta(days=10)
PASS_LOOKBACK = timedelta(minutes=20)
PASS_REFRESH = timedelta(hours=6)
SKY_REFRESH = timedelta(minutes=30)
LIVE_UPDATE_INTERVAL = 5

# A person's passes are recomputed once they have moved this far.
MOVE_THRESHOLD_KM = 25.0
# The weather entity describes home; beyond this distance its sky is unknown.
WEATHER_RANGE_KM = 50.0

# Unseen overflights are only looked for close to now: the panel mentions
# one when it is under way or about to begin.
UNSEEN_LOOKBACK = timedelta(minutes=10)
UNSEEN_LOOKAHEAD = timedelta(minutes=90)

TRACK_SPAN = timedelta(minutes=100)
TRACK_STEP_SECONDS = 10

OBSERVER_HOME = "home"
OBSERVER_ME = "me"

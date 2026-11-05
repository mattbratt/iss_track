"""Sky condition for a pass: the one place a forecast becomes clear or cloudy.

A forecast that is missing is "unknown", and unknown never rules a pass out.
"""
from __future__ import annotations

SKY_CLEAR = "clear"
SKY_PARTLY_CLOUDY = "partly_cloudy"
SKY_CLOUDY = "cloudy"
SKY_UNKNOWN = "unknown"
SKIES = (SKY_CLEAR, SKY_PARTLY_CLOUDY, SKY_CLOUDY, SKY_UNKNOWN)

# What the user will accept, from most to least permissive.
SKY_LIMIT_ANY = "any"
SKY_LIMIT_PARTLY = "partly_cloudy"
SKY_LIMIT_CLEAR = "clear"
SKY_LIMITS = (SKY_LIMIT_ANY, SKY_LIMIT_PARTLY, SKY_LIMIT_CLEAR)

CLEAR_MAX_CLOUD = 25.0
PARTLY_MAX_CLOUD = 60.0

_CONDITION_SKY = {
    "clear-night": SKY_CLEAR,
    "sunny": SKY_CLEAR,
    "windy": SKY_CLEAR,
    "partlycloudy": SKY_PARTLY_CLOUDY,
    "windy-variant": SKY_PARTLY_CLOUDY,
    "cloudy": SKY_CLOUDY,
    "fog": SKY_CLOUDY,
    "hail": SKY_CLOUDY,
    "lightning": SKY_CLOUDY,
    "lightning-rainy": SKY_CLOUDY,
    "pouring": SKY_CLOUDY,
    "rainy": SKY_CLOUDY,
    "snowy": SKY_CLOUDY,
    "snowy-rainy": SKY_CLOUDY,
}


def classify_sky(cloud_coverage: object, condition: object) -> str:
    """Sky condition from a forecast's cloud percentage, else its condition word."""
    try:
        cover = float(cloud_coverage)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        cover = None
    if cover is not None and 0.0 <= cover <= 100.0:
        if cover <= CLEAR_MAX_CLOUD:
            return SKY_CLEAR
        if cover <= PARTLY_MAX_CLOUD:
            return SKY_PARTLY_CLOUDY
        return SKY_CLOUDY
    if isinstance(condition, str):
        return _CONDITION_SKY.get(condition, SKY_UNKNOWN)
    return SKY_UNKNOWN


def sky_allows(sky: str, limit: str) -> bool:
    """True when a pass under this sky is still worth an alert."""
    if sky == SKY_UNKNOWN or limit == SKY_LIMIT_ANY:
        return True
    if limit == SKY_LIMIT_CLEAR:
        return sky == SKY_CLEAR
    return sky in (SKY_CLEAR, SKY_PARTLY_CLOUDY)

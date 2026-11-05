"""WebSocket API: how the map panel and the dashboard card read the hub.

Neither page computes anything about the orbit. They draw what these
commands return.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import (
    CONF_EVENING,
    CONF_FAINTEST_MAGNITUDE,
    CONF_MORNING,
    CONF_QUALITIES,
    CONF_SKY_LIMIT,
    CONF_WEATHER_ENTITY,
    DOMAIN,
    MAGNITUDE_BRIGHTEST,
    MAGNITUDE_FAINTEST,
    OBSERVER_HOME,
    OBSERVER_ME,
    TLE_REFRESH,
    TRACK_SPAN,
    TRACK_STEP_SECONDS,
)
from .coordinator import (
    IssTrackCoordinator,
    ObserverBook,
    async_add_change_listener,
    observer_from_state,
)
from .engine import (
    QUALITIES,
    SKY_LIMITS,
    SKY_UNKNOWN,
    Observer,
    OrbitError,
    ground_track,
    sun_subpoint,
)

_LOCATED_DOMAINS = ("person.", "device_tracker.")


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_track)
    websocket_api.async_register_command(hass, ws_passes)
    websocket_api.async_register_command(hass, ws_settings_get)
    websocket_api.async_register_command(hass, ws_settings_set)
    websocket_api.async_register_command(hass, ws_subscribe)


def _coordinator(hass: HomeAssistant) -> IssTrackCoordinator | None:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data
    return None


def _not_ready(connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    connection.send_error(msg["id"], "not_ready", "ISS Track is not loaded yet")


def _milliseconds(when) -> int:
    return int(when.timestamp() * 1000)


@websocket_api.websocket_command({vol.Required("type"): "iss_track/track"})
@websocket_api.async_response
async def ws_track(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """The ground track around now, the Sun, and the state of the elements."""
    coordinator = _coordinator(hass)
    if coordinator is None or coordinator.orbit is None:
        _not_ready(connection, msg)
        return
    now = dt_util.utcnow().replace(microsecond=0)
    start = now - TRACK_SPAN
    end = now + TRACK_SPAN
    try:
        points = await hass.async_add_executor_job(
            ground_track, coordinator.orbit.copy(), start, end, TRACK_STEP_SECONDS
        )
    except OrbitError as err:
        connection.send_error(msg["id"], "orbit_error", str(err))
        return
    fetched = coordinator.tle_fetched_at
    home = coordinator.books[OBSERVER_HOME]
    connection.send_result(
        msg["id"],
        {
            "start": _milliseconds(start),
            "step": TRACK_STEP_SECONDS,
            "points": points,
            "sun": [
                [_milliseconds(when), *(round(value, 3) for value in sun_subpoint(when))]
                for when in (start, now, end)
            ],
            "period_minutes": round(coordinator.orbit.period_minutes, 2),
            "tle": {
                "fetched_at": _milliseconds(fetched) if fetched else None,
                "next_refresh": _milliseconds(fetched + TLE_REFRESH) if fetched else None,
                "epoch": coordinator.orbit.epoch.isoformat(),
                "stale": coordinator.tle_stale,
            },
            "units": coordinator.unit_system,
            "home": _place(home.name, home.observer),
        },
    )


def _place(name: str, observer: Observer | None) -> dict[str, Any]:
    return {
        "name": name,
        "latitude": None if observer is None else round(observer.latitude, 4),
        "longitude": None if observer is None else round(observer.longitude, 4),
    }


def _person_for_user(hass: HomeAssistant, user_id: str):
    for state in hass.states.async_all("person"):
        if state.attributes.get("user_id") == user_id:
            return state
    return None


async def _passes_for(
    hass: HomeAssistant,
    coordinator: IssTrackCoordinator,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> tuple[dict[str, Any], list, dict]:
    """Resolve who is looking, and return their passes and sky."""
    wanted: str = msg["observer"]

    def from_book(book: ObserverBook, source: str) -> tuple[dict[str, Any], list, dict]:
        info = {
            "key": book.key,
            "source": source,
            "available": book.observer is not None,
            "reason": None if book.observer is not None else "no_location",
            **_place(book.name, book.observer),
        }
        return info, book.passes, book.sky

    async def adhoc(key: str, name: str, source: str, observer: Observer):
        passes, sky = await coordinator.async_adhoc_passes(observer)
        info = {"key": key, "source": source, "available": True, "reason": None, **_place(name, observer)}
        return info, passes, sky

    def unavailable(key: str, name: str, source: str, reason: str):
        info = {"key": key, "source": source, "available": False, "reason": reason, **_place(name, None)}
        return info, [], {}

    if "latitude" in msg and "longitude" in msg:
        return await adhoc(
            "device", "This device", "browser", Observer(msg["latitude"], msg["longitude"], 0.0)
        )
    if wanted == OBSERVER_ME:
        person = _person_for_user(hass, connection.user.id)
        if person is None:
            return unavailable(OBSERVER_ME, "This device", "person", "no_person")
        wanted = person.entity_id
    if wanted in coordinator.books:
        return from_book(
            coordinator.books[wanted], "home" if wanted == OBSERVER_HOME else "person"
        )
    if wanted.startswith(_LOCATED_DOMAINS):
        state = hass.states.get(wanted)
        if state is None:
            return unavailable(wanted, wanted, "person", "no_person")
        observer = observer_from_state(state)
        if observer is None:
            return unavailable(wanted, state.name, "person", "no_location")
        return await adhoc(wanted, state.name, "person", observer)
    raise vol.Invalid(f"Unknown observer: {wanted}")


@websocket_api.websocket_command(
    {
        vol.Required("type"): "iss_track/passes",
        vol.Optional("observer", default=OBSERVER_HOME): str,
        vol.Inclusive("latitude", "coordinates"): vol.All(
            vol.Coerce(float), vol.Range(min=-90, max=90)
        ),
        vol.Inclusive("longitude", "coordinates"): vol.All(
            vol.Coerce(float), vol.Range(min=-180, max=180)
        ),
    }
)
@websocket_api.async_response
async def ws_passes(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Visible passes for home, a person, or the place the browser reports."""
    coordinator = _coordinator(hass)
    if coordinator is None or coordinator.orbit is None:
        _not_ready(connection, msg)
        return
    try:
        info, passes, sky = await _passes_for(hass, coordinator, connection, msg)
    except vol.Invalid as err:
        connection.send_error(msg["id"], "unknown_observer", str(err))
        return
    except OrbitError as err:
        connection.send_error(msg["id"], "orbit_error", str(err))
        return
    now = dt_util.utcnow()
    connection.send_result(
        msg["id"],
        {
            "observer": info,
            "now": _milliseconds(now),
            "passes": [
                coordinator.describe(item, sky.get(item.start, SKY_UNKNOWN), with_path=True)
                for item in passes
                if item.end >= now
            ],
            "settings": coordinator.settings(),
        },
    )


@websocket_api.websocket_command({vol.Required("type"): "iss_track/subscribe"})
@callback
def ws_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Tell the panel or card when passes, sky or pass settings change."""

    @callback
    def forward() -> None:
        connection.send_message(websocket_api.event_message(msg["id"], {"changed": True}))

    connection.subscriptions[msg["id"]] = async_add_change_listener(hass, forward)
    connection.send_result(msg["id"])


def _settings_payload(
    hass: HomeAssistant, coordinator: IssTrackCoordinator, connection: websocket_api.ActiveConnection
) -> dict[str, Any]:
    return {
        **coordinator.settings(),
        "can_edit": connection.user.is_admin,
        "units": coordinator.unit_system,
        "weather_entities": [
            {"entity_id": state.entity_id, "name": state.name}
            for state in sorted(hass.states.async_all("weather"), key=lambda s: s.name.lower())
        ],
    }


@websocket_api.websocket_command({vol.Required("type"): "iss_track/settings/get"})
@callback
def ws_settings_get(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    coordinator = _coordinator(hass)
    if coordinator is None:
        _not_ready(connection, msg)
        return
    connection.send_result(msg["id"], _settings_payload(hass, coordinator, connection))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "iss_track/settings/set",
        vol.Optional(CONF_QUALITIES): vol.All(
            cv.ensure_list, [vol.In(QUALITIES)], vol.Length(min=1)
        ),
        vol.Optional(CONF_FAINTEST_MAGNITUDE): vol.All(
            vol.Coerce(float), vol.Range(min=MAGNITUDE_BRIGHTEST, max=MAGNITUDE_FAINTEST)
        ),
        vol.Optional(CONF_EVENING): bool,
        vol.Optional(CONF_MORNING): bool,
        vol.Optional(CONF_WEATHER_ENTITY): vol.Any(None, cv.entity_id),
        vol.Optional(CONF_SKY_LIMIT): vol.In(SKY_LIMITS),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_settings_set(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Save pass settings into the integration's one options record."""
    coordinator = _coordinator(hass)
    if coordinator is None:
        _not_ready(connection, msg)
        return
    entry = coordinator.config_entry
    merged = {**coordinator.settings(), **{k: v for k, v in msg.items() if k not in ("id", "type")}}
    if not merged[CONF_EVENING] and not merged[CONF_MORNING]:
        connection.send_error(msg["id"], "no_period", "Choose evening passes, morning passes, or both")
        return
    options = dict(entry.options)
    for key in (
        CONF_QUALITIES,
        CONF_FAINTEST_MAGNITUDE,
        CONF_EVENING,
        CONF_MORNING,
        CONF_SKY_LIMIT,
        CONF_WEATHER_ENTITY,
    ):
        if key not in msg:
            continue
        if key == CONF_WEATHER_ENTITY and not msg[key]:
            options.pop(key, None)
        else:
            options[key] = msg[key]
    if options != dict(entry.options):
        # The entry's update listener re-reads the settings and refreshes the
        # entities; the reply below already reads the saved record.
        hass.config_entries.async_update_entry(entry, options=options)
    connection.send_result(msg["id"], _settings_payload(hass, coordinator, connection))

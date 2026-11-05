"""The hub: orbital elements, live position, passes and sky for every observer.

All arithmetic lives in the engine package. This module only decides when to
ask the engine, and for whom.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    EVENT_CORE_CONFIG_UPDATE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, State, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import (
    async_call_later,
    async_track_point_in_utc_time,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_EVENING,
    CONF_FAINTEST_MAGNITUDE,
    CONF_MORNING,
    CONF_PEOPLE,
    CONF_QUALITIES,
    CONF_SKY_LIMIT,
    CONF_UNIT_SYSTEM,
    CONF_UPDATE_INTERVAL,
    CONF_WEATHER_ENTITY,
    DEFAULT_EVENING,
    DEFAULT_FAINTEST_MAGNITUDE,
    DEFAULT_MORNING,
    DEFAULT_QUALITIES,
    DEFAULT_SKY_LIMIT,
    DEFAULT_UNIT_SYSTEM,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    ISSUE_STALE_TLE,
    LIVE_UPDATE_INTERVAL,
    MOVE_THRESHOLD_KM,
    OBSERVER_HOME,
    PASS_HORIZON,
    PASS_LOOKBACK,
    PASS_REFRESH,
    SKY_REFRESH,
    TLE_REFRESH,
    TLE_STALE_AFTER,
    TLE_URL,
    WEATHER_RANGE_KM,
)
from .engine import (
    QUALITIES,
    SKY_LIMITS,
    SKY_UNKNOWN,
    Criteria,
    Observer,
    Orbit,
    OrbitError,
    Pass,
    State as IssState,
    classify_sky,
    find_passes,
    ground_distance_km,
    look_now,
    parse_tle,
    sky_allows,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
_ADHOC_LIMIT = 8
_ADHOC_TTL = timedelta(hours=1)
_FORECAST_REACH = timedelta(minutes=90)
_SKY_RETRY_SECONDS = 120
_DATA_LISTENERS = "change_listeners"

type IssTrackConfigEntry = ConfigEntry[IssTrackCoordinator]


@dataclass(frozen=True, slots=True)
class Look:
    """Where the station is in one observer's sky."""

    azimuth: float
    elevation: float
    range_km: float
    distance_km: float


@dataclass(frozen=True, slots=True)
class LiveData:
    """One tick: the station's position, and how each observer sees it."""

    state: IssState
    looks: dict[str, Look]


@dataclass(slots=True)
class ObserverBook:
    """Everything known for one observer: home, or a tracked person."""

    key: str
    name: str
    observer: Observer | None = None
    passes: list[Pass] = field(default_factory=list)
    sky: dict[datetime, str] = field(default_factory=dict)
    computed_for: Observer | None = None

    def matching(self, criteria: Criteria) -> list[Pass]:
        return [item for item in self.passes if criteria.matches(item)]

    def current(self, criteria: Criteria, now: datetime) -> Pass | None:
        """The matching pass that is visible right now, if any."""
        for item in self.passes:
            if item.start <= now <= item.end and criteria.matches(item):
                return item
        return None

    def upcoming(self, criteria: Criteria, now: datetime) -> Pass | None:
        """The matching pass in progress, else the next one to come."""
        for item in self.passes:
            if item.end >= now and criteria.matches(item):
                return item
        return None

    def sky_for(self, item: Pass) -> str:
        return self.sky.get(item.start, SKY_UNKNOWN)


@callback
def async_add_change_listener(hass: HomeAssistant, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
    """Call listener whenever passes, sky or pass settings change.

    The registry outlives a reload of the entry, so an open panel or card
    keeps hearing about changes afterwards.
    """
    listeners: set[CALLBACK_TYPE] = hass.data.setdefault(DOMAIN, {}).setdefault(
        _DATA_LISTENERS, set()
    )
    listeners.add(listener)

    @callback
    def remove() -> None:
        listeners.discard(listener)

    return remove


@callback
def async_notify_changed(hass: HomeAssistant) -> None:
    for listener in list(hass.data.get(DOMAIN, {}).get(_DATA_LISTENERS, ())):
        listener()


def observer_from_state(state: State | None) -> Observer | None:
    """An observer from any entity that reports latitude and longitude."""
    if state is None:
        return None
    try:
        latitude = float(state.attributes[ATTR_LATITUDE])
        longitude = float(state.attributes[ATTR_LONGITUDE])
    except (KeyError, TypeError, ValueError):
        return None
    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        return None
    return Observer(latitude, longitude, 0.0)


def get_option(entry: ConfigEntry, key: str, default: Any) -> Any:
    """An option, falling back to the value given when the entry was created."""
    return entry.options.get(key, entry.data.get(key, default))


class IssTrackCoordinator(DataUpdateCoordinator[LiveData]):
    """Fetch orbital elements, tick the live position, keep passes current."""

    config_entry: IssTrackConfigEntry

    def __init__(self, hass: HomeAssistant, entry: IssTrackConfigEntry) -> None:
        self._interval = int(get_option(entry, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=self._interval),
        )
        self.orbit: Orbit | None = None
        self.tle_fetched_at: datetime | None = None
        self.books: dict[str, ObserverBook] = {}
        self._store: Store[dict[str, str]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.tle")
        self._unsubs: list[CALLBACK_TYPE] = []
        self._unsub_edge: CALLBACK_TYPE | None = None
        self._forecast: list[tuple[datetime, str]] = []
        self._current_sky = SKY_UNKNOWN
        self._forecast_entity: str | None = None
        self._sky_retry: CALLBACK_TYPE | None = None
        self._closed = False
        self._adhoc: dict[tuple[float, float, str], tuple[datetime, list[Pass]]] = {}

    # ----- settings, read from the one options record ---------------------

    @property
    def people(self) -> list[str]:
        return list(get_option(self.config_entry, CONF_PEOPLE, []))

    @property
    def update_seconds(self) -> int:
        return self._interval

    @property
    def unit_system(self) -> str:
        return get_option(self.config_entry, CONF_UNIT_SYSTEM, DEFAULT_UNIT_SYSTEM)

    @property
    def weather_entity(self) -> str | None:
        return get_option(self.config_entry, CONF_WEATHER_ENTITY, None) or None

    @property
    def sky_limit(self) -> str:
        limit = get_option(self.config_entry, CONF_SKY_LIMIT, DEFAULT_SKY_LIMIT)
        return limit if limit in SKY_LIMITS else DEFAULT_SKY_LIMIT

    @property
    def criteria(self) -> Criteria:
        entry = self.config_entry
        qualities = get_option(entry, CONF_QUALITIES, DEFAULT_QUALITIES)
        return Criteria(
            qualities=frozenset(q for q in qualities if q in QUALITIES),
            faintest_magnitude=float(
                get_option(entry, CONF_FAINTEST_MAGNITUDE, DEFAULT_FAINTEST_MAGNITUDE)
            ),
            evening=bool(get_option(entry, CONF_EVENING, DEFAULT_EVENING)),
            morning=bool(get_option(entry, CONF_MORNING, DEFAULT_MORNING)),
        )

    def settings(self) -> dict[str, Any]:
        """The pass settings, as the panel and card show them."""
        criteria = self.criteria
        return {
            CONF_QUALITIES: [q for q in QUALITIES if q in criteria.qualities],
            CONF_FAINTEST_MAGNITUDE: criteria.faintest_magnitude,
            CONF_EVENING: criteria.evening,
            CONF_MORNING: criteria.morning,
            CONF_WEATHER_ENTITY: self.weather_entity,
            CONF_SKY_LIMIT: self.sky_limit,
        }

    @property
    def tle_stale(self) -> bool:
        return (
            self.tle_fetched_at is None
            or dt_util.utcnow() - self.tle_fetched_at > TLE_STALE_AFTER
        )

    # ----- lifecycle ------------------------------------------------------

    async def async_start(self) -> None:
        """Load or fetch the elements, compute passes, start the timers."""
        stored = await self._store.async_load()
        if stored:
            try:
                self.orbit = Orbit(stored["line1"], stored["line2"])
                self.tle_fetched_at = dt_util.parse_datetime(stored["fetched_at"])
            except (KeyError, TypeError, OrbitError) as err:
                _LOGGER.warning("Stored orbital elements are unusable (%s); refetching", err)
                self.orbit = None
        if (
            self.orbit is None
            or self.tle_fetched_at is None
            or dt_util.utcnow() - self.tle_fetched_at >= TLE_REFRESH
        ):
            await self._async_fetch_tle()
        if self.orbit is None:
            raise ConfigEntryNotReady("No orbital elements yet: Celestrak could not be reached")
        self._update_stale_issue()

        self._build_books()
        for book in self.books.values():
            await self._async_compute(book)
        await self._async_load_forecast()
        self._annotate_sky()
        self._schedule_edge()

        hass = self.hass
        self._unsubs.append(async_track_time_interval(hass, self._handle_tle_timer, TLE_REFRESH))
        self._unsubs.append(async_track_time_interval(hass, self._handle_pass_timer, PASS_REFRESH))
        self._unsubs.append(async_track_time_interval(hass, self._handle_sky_timer, SKY_REFRESH))
        self._unsubs.append(hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, self._handle_home_moved))
        if self.people:
            self._unsubs.append(
                async_track_state_change_event(hass, self.people, self._handle_person)
            )
        await self.async_config_entry_first_refresh()
        async_notify_changed(self.hass)

    async def async_shutdown(self) -> None:
        # Work still in flight checks this, so it cannot re-arm a timer.
        self._closed = True
        if self._sky_retry is not None:
            self._sky_retry()
            self._sky_retry = None
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._unsub_edge is not None:
            self._unsub_edge()
            self._unsub_edge = None
        await super().async_shutdown()

    async def async_apply_options(self) -> None:
        """Pass settings changed: nothing to recompute, only to re-read."""
        await self._async_load_forecast()
        self._annotate_sky()
        self._schedule_edge()
        await self.async_refresh()
        async_notify_changed(self.hass)

    # ----- the live tick --------------------------------------------------

    async def _async_update_data(self) -> LiveData:
        if self.orbit is None:
            raise UpdateFailed("No orbital elements")
        now = dt_util.utcnow()
        try:
            state = self.orbit.state(now)
            looks: dict[str, Look] = {}
            for key, book in self.books.items():
                if book.observer is None:
                    continue
                azimuth, elevation, distance = look_now(self.orbit, book.observer, now)
                looks[key] = Look(
                    azimuth=azimuth,
                    elevation=elevation,
                    range_km=distance,
                    distance_km=ground_distance_km(
                        book.observer.latitude,
                        book.observer.longitude,
                        state.latitude,
                        state.longitude,
                    ),
                )
        except OrbitError as err:
            raise UpdateFailed(f"Could not propagate the orbit: {err}") from err
        return LiveData(state=state, looks=looks)

    # ----- orbital elements -----------------------------------------------

    async def _async_fetch_tle(self) -> bool:
        """Fetch fresh elements. On any failure the last good set stays."""
        session = async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(20):
                response = await session.get(TLE_URL)
                response.raise_for_status()
                text = await response.text()
            orbit = Orbit(*parse_tle(text))
        except (aiohttp.ClientError, TimeoutError, OrbitError) as err:
            _LOGGER.warning("Could not refresh ISS orbital elements from Celestrak: %s", err)
            return False
        changed = self.orbit is None or orbit.line1 != self.orbit.line1
        self.orbit = orbit
        self.tle_fetched_at = dt_util.utcnow()
        self._adhoc.clear()
        await self._store.async_save(
            {
                "line1": orbit.line1,
                "line2": orbit.line2,
                "fetched_at": self.tle_fetched_at.isoformat(),
            }
        )
        return changed

    @callback
    def _update_stale_issue(self) -> None:
        if self.tle_stale:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_STALE_TLE,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_STALE_TLE,
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_STALE_TLE)

    async def _handle_tle_timer(self, _now: datetime) -> None:
        changed = await self._async_fetch_tle()
        self._update_stale_issue()
        if changed:
            await self._async_recompute_all()
        else:
            self.async_update_listeners()

    # ----- observers and passes -------------------------------------------

    def _home_observer(self) -> Observer:
        config = self.hass.config
        return Observer(config.latitude, config.longitude, float(config.elevation or 0))

    @callback
    def _build_books(self) -> None:
        self.books = {
            OBSERVER_HOME: ObserverBook(
                key=OBSERVER_HOME,
                name=self.hass.config.location_name or "Home",
                observer=self._home_observer(),
            )
        }
        for entity_id in self.people:
            state = self.hass.states.get(entity_id)
            self.books[entity_id] = ObserverBook(
                key=entity_id,
                name=state.name if state else entity_id.split(".", 1)[-1],
                observer=observer_from_state(state),
            )

    async def _async_compute(self, book: ObserverBook) -> None:
        """Recompute one observer's passes. A failure keeps the previous list."""
        if self.orbit is None or book.observer is None:
            book.passes = []
            book.computed_for = None
            return
        # Whole seconds, so every pass time is a whole second too.
        now = dt_util.utcnow().replace(microsecond=0)
        observer = book.observer
        try:
            book.passes = await self.hass.async_add_executor_job(
                find_passes, self.orbit.copy(), observer, now - PASS_LOOKBACK, now + PASS_HORIZON
            )
        except OrbitError as err:
            _LOGGER.warning("Could not compute passes for %s: %s", book.name, err)
            return
        book.computed_for = observer

    async def _async_recompute(self, books: list[ObserverBook]) -> None:
        for book in books:
            await self._async_compute(book)
        if self._closed:
            return
        self._annotate_sky()
        self._schedule_edge()
        await self.async_refresh()
        async_notify_changed(self.hass)

    async def _async_recompute_all(self) -> None:
        await self._async_recompute(list(self.books.values()))

    async def _handle_pass_timer(self, _now: datetime) -> None:
        await self._async_recompute_all()

    async def _handle_home_moved(self, _event: Event) -> None:
        book = self.books[OBSERVER_HOME]
        book.observer = self._home_observer()
        book.name = self.hass.config.location_name or "Home"
        if book.observer != book.computed_for:
            await self._async_recompute([book])

    @callback
    def _handle_person(self, event: Event) -> None:
        book = self.books.get(event.data["entity_id"])
        if book is None:
            return
        new_state: State | None = event.data.get("new_state")
        book.observer = observer_from_state(new_state)
        if new_state is not None:
            book.name = new_state.name
        moved = book.observer is not None and (
            book.computed_for is None
            or ground_distance_km(
                book.observer.latitude,
                book.observer.longitude,
                book.computed_for.latitude,
                book.computed_for.longitude,
            )
            > MOVE_THRESHOLD_KM
        )
        if moved or (book.observer is None and book.passes):
            self.config_entry.async_create_task(
                self.hass, self._async_recompute([book]), f"{DOMAIN} passes for {book.key}"
            )

    async def async_adhoc_passes(self, observer: Observer) -> tuple[list[Pass], dict[datetime, str]]:
        """Passes for a place that has no entities, such as a browser's location."""
        if self.orbit is None:
            return [], {}
        now = dt_util.utcnow().replace(microsecond=0)
        key = (round(observer.latitude, 2), round(observer.longitude, 2), self.orbit.line1)
        cached = self._adhoc.get(key)
        if cached is not None and now - cached[0] < _ADHOC_TTL:
            passes = cached[1]
        else:
            passes = await self.hass.async_add_executor_job(
                find_passes, self.orbit.copy(), observer, now - PASS_LOOKBACK, now + PASS_HORIZON
            )
            self._adhoc[key] = (now, passes)
            while len(self._adhoc) > _ADHOC_LIMIT:
                self._adhoc.pop(next(iter(self._adhoc)))
        return passes, self._sky_for_passes(observer, passes)

    # ----- pass edges: exact to the second, never polled -------------------

    @callback
    def _schedule_edge(self) -> None:
        """Wake at the next moment a matching pass starts or ends."""
        if self._unsub_edge is not None:
            self._unsub_edge()
            self._unsub_edge = None
        if self._closed:
            return
        now = dt_util.utcnow()
        criteria = self.criteria
        edges: list[datetime] = []
        live = False
        for book in self.books.values():
            for item in book.matching(criteria):
                if item.start <= now <= item.end:
                    live = True
                for edge in (item.start, item.end + timedelta(seconds=1)):
                    if edge > now:
                        edges.append(edge)
        self.update_interval = timedelta(
            seconds=min(LIVE_UPDATE_INTERVAL, self._interval) if live else self._interval
        )
        if edges:
            self._unsub_edge = async_track_point_in_utc_time(
                self.hass, self._handle_edge, min(edges)
            )

    async def _handle_edge(self, _now: datetime) -> None:
        self._unsub_edge = None
        self._schedule_edge()
        await self.async_refresh()

    # ----- sky ------------------------------------------------------------

    async def _async_load_forecast(self) -> None:
        """Read the weather entity's hourly forecast and current condition.

        A weather entity that is not ready yet keeps the last good forecast
        and is asked again soon, so one bad moment never turns every pass's
        sky into "unknown".
        """
        entity_id = self.weather_entity
        if entity_id != self._forecast_entity:
            self._forecast = []
            self._current_sky = SKY_UNKNOWN
            self._forecast_entity = entity_id
        if self._sky_retry is not None:
            self._sky_retry()
            self._sky_retry = None
        if entity_id is None:
            return
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            if not self._closed:
                self._sky_retry = async_call_later(
                    self.hass, _SKY_RETRY_SECONDS, self._handle_sky_timer
                )
            return
        self._current_sky = classify_sky(state.attributes.get("cloud_coverage"), state.state)
        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": entity_id, "type": "hourly"},
                blocking=True,
                return_response=True,
            )
        except (HomeAssistantError, ValueError) as err:
            # No hourly forecast from this entity: its current condition still
            # covers a pass that is about to start.
            _LOGGER.debug("No hourly forecast from %s: %s", entity_id, err)
            self._forecast = []
            return
        rows = ((response or {}).get(entity_id) or {}).get("forecast") or []
        forecast: list[tuple[datetime, str]] = []
        for row in rows:
            when = dt_util.parse_datetime(str(row.get("datetime")))
            if when is None:
                continue
            forecast.append(
                (dt_util.as_utc(when), classify_sky(row.get("cloud_coverage"), row.get("condition")))
            )
        forecast.sort(key=lambda item: item[0])
        self._forecast = forecast

    def _sky_for_passes(self, observer: Observer | None, passes: list[Pass]) -> dict[datetime, str]:
        home = self.books[OBSERVER_HOME].observer if OBSERVER_HOME in self.books else None
        near_home = (
            observer is not None
            and home is not None
            and ground_distance_km(
                observer.latitude, observer.longitude, home.latitude, home.longitude
            )
            <= WEATHER_RANGE_KM
        )
        if not near_home or self.weather_entity is None:
            return {item.start: SKY_UNKNOWN for item in passes}
        now = dt_util.utcnow()
        result: dict[datetime, str] = {}
        for item in passes:
            sky = SKY_UNKNOWN
            for when, forecast_sky in self._forecast:
                if when > item.peak:
                    break
                if item.peak - when <= _FORECAST_REACH:
                    sky = forecast_sky
            if sky == SKY_UNKNOWN and item.end >= now and item.start - now <= timedelta(hours=1):
                sky = self._current_sky
            result[item.start] = sky
        return result

    @callback
    def _annotate_sky(self) -> None:
        for book in self.books.values():
            book.sky = self._sky_for_passes(book.observer, book.passes)

    async def _handle_sky_timer(self, _now: datetime) -> None:
        self._sky_retry = None
        if self._closed:
            return
        await self._async_load_forecast()
        self._annotate_sky()
        self.async_update_listeners()
        async_notify_changed(self.hass)

    # ----- shared wording of one pass, for the API and attributes ----------

    def describe(self, item: Pass, sky: str, *, with_path: bool) -> dict[str, Any]:
        """A pass as the panel, card and attributes all receive it."""
        data = item.as_dict(with_path=with_path)
        reason = self.criteria.reason(item)
        matches = reason is None
        data["matches"] = matches
        data["reason"] = reason
        data["sky"] = sky
        data["alert"] = matches and sky_allows(sky, self.sky_limit)
        return data


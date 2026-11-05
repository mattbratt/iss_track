"""Sensors: the station's live position, and each observer's sky and next pass."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    DEGREE,
    EntityCategory,
    UnitOfLength,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .coordinator import IssTrackConfigEntry, IssTrackCoordinator, ObserverBook
from .engine import QUALITIES, SKIES, Pass, compass
from .entity import OWNER_ISS, IssTrackEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IssSensorDescription(SensorEntityDescription):
    """A sensor and the one place its value is read from."""

    value_fn: Callable[[IssTrackCoordinator, ObserverBook | None], StateType | datetime]
    attrs_fn: Callable[[IssTrackCoordinator, ObserverBook | None], dict[str, Any] | None] | None = None


def _next_pass(coordinator: IssTrackCoordinator, book: ObserverBook | None) -> Pass | None:
    if book is None:
        return None
    return book.upcoming(coordinator.criteria, dt_util.utcnow())


def _next_pass_attrs(
    coordinator: IssTrackCoordinator, book: ObserverBook | None
) -> dict[str, Any] | None:
    item = _next_pass(coordinator, book)
    if item is None or book is None:
        return None
    data = coordinator.describe(item, book.sky_for(item), with_path=False)
    data.pop("matches", None)
    return data


def _position_text(latitude: float, longitude: float) -> str:
    return (
        f"{abs(latitude):.1f}° {'N' if latitude >= 0 else 'S'}, "
        f"{abs(longitude):.1f}° {'E' if longitude >= 0 else 'W'}"
    )


def _look(coordinator: IssTrackCoordinator, book: ObserverBook | None, name: str) -> float | None:
    if book is None:
        return None
    look = coordinator.data.looks.get(book.key)
    return None if look is None else getattr(look, name)


STATION_SENSORS: tuple[IssSensorDescription, ...] = (
    IssSensorDescription(
        key="latitude",
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=2,
        value_fn=lambda c, _b: round(c.data.state.latitude, 3),
    ),
    IssSensorDescription(
        key="longitude",
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=2,
        value_fn=lambda c, _b: round(c.data.state.longitude, 3),
    ),
    IssSensorDescription(
        key="altitude",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=0,
        value_fn=lambda c, _b: round(c.data.state.altitude_km, 1),
    ),
    IssSensorDescription(
        key="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=0,
        value_fn=lambda c, _b: round(c.data.state.speed_kms * 3600),
    ),
    # The one entity to add to a Map card: it carries latitude and longitude.
    IssSensorDescription(
        key="position",
        value_fn=lambda c, _b: _position_text(c.data.state.latitude, c.data.state.longitude),
        attrs_fn=lambda c, _b: {
            ATTR_LATITUDE: round(c.data.state.latitude, 4),
            ATTR_LONGITUDE: round(c.data.state.longitude, 4),
        },
    ),
    IssSensorDescription(
        key="tle_updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c, _b: c.tle_fetched_at,
        attrs_fn=lambda c, _b: {
            "epoch": c.orbit.epoch.isoformat() if c.orbit else None,
            "stale": c.tle_stale,
        },
    ),
)

OBSERVER_SENSORS: tuple[IssSensorDescription, ...] = (
    IssSensorDescription(
        key="elevation",
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=1,
        value_fn=lambda c, b: _round(_look(c, b, "elevation"), 1),
    ),
    IssSensorDescription(
        key="azimuth",
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=0,
        value_fn=lambda c, b: _round(_look(c, b, "azimuth"), 0),
        attrs_fn=lambda c, b: (
            None if _look(c, b, "azimuth") is None else {"direction": compass(_look(c, b, "azimuth"))}
        ),
    ),
    IssSensorDescription(
        key="distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=0,
        value_fn=lambda c, b: _round(_look(c, b, "distance_km"), 0),
    ),
    IssSensorDescription(
        key="next_pass",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c, b: getattr(_next_pass(c, b), "start", None),
        attrs_fn=_next_pass_attrs,
    ),
    IssSensorDescription(
        key="next_pass_quality",
        device_class=SensorDeviceClass.ENUM,
        options=list(QUALITIES),
        value_fn=lambda c, b: getattr(_next_pass(c, b), "quality", None),
    ),
    IssSensorDescription(
        key="next_pass_peak_elevation",
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=0,
        value_fn=lambda c, b: _round(getattr(_next_pass(c, b), "peak_elevation", None), 1),
    ),
    IssSensorDescription(
        key="next_pass_magnitude",
        suggested_display_precision=1,
        value_fn=lambda c, b: _round(getattr(_next_pass(c, b), "magnitude", None), 1),
    ),
    IssSensorDescription(
        key="next_pass_sky",
        device_class=SensorDeviceClass.ENUM,
        options=list(SKIES),
        value_fn=lambda c, b: (
            None if (item := _next_pass(c, b)) is None or b is None else b.sky_for(item)
        ),
    ),
)


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IssTrackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[IssTrackSensor] = [
        IssTrackSensor(coordinator, OWNER_ISS, description) for description in STATION_SENSORS
    ]
    for owner in coordinator.books:
        entities.extend(
            IssTrackSensor(coordinator, owner, description) for description in OBSERVER_SENSORS
        )
    async_add_entities(entities)


class IssTrackSensor(IssTrackEntity, SensorEntity):
    """One reading, taken from the hub on every update."""

    entity_description: IssSensorDescription
    # The coordinates change on every tick; keeping them out of the recorder
    # stops the position sensor from filling the attributes table.
    _unrecorded_attributes = frozenset({ATTR_LATITUDE, ATTR_LONGITUDE})

    def __init__(
        self, coordinator: IssTrackCoordinator, owner: str, description: IssSensorDescription
    ) -> None:
        super().__init__(coordinator, owner, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        return self.entity_description.value_fn(self.coordinator, self.book)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator, self.book)

"""Binary sensor: on for exactly as long as a matching pass is visible."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import IssTrackConfigEntry, IssTrackCoordinator
from .engine import Pass
from .entity import IssTrackEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IssTrackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(PassInProgress(coordinator, owner) for owner in coordinator.books)


class PassInProgress(IssTrackEntity, BinarySensorEntity):
    """The hub wakes at each pass's first and last second, so this is exact."""

    def __init__(self, coordinator: IssTrackCoordinator, owner: str) -> None:
        super().__init__(coordinator, owner, "pass_in_progress")

    def _current(self) -> Pass | None:
        book = self.book
        if book is None:
            return None
        return book.current(self.coordinator.criteria, dt_util.utcnow())

    @property
    def is_on(self) -> bool:
        return self._current() is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        item = self._current()
        book = self.book
        if item is None or book is None:
            return None
        return {"end": item.end.isoformat(), "sky": book.sky_for(item)}

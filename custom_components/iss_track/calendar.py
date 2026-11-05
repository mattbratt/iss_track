"""Calendar: every matching pass for the next ten days."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import IssTrackConfigEntry, IssTrackCoordinator
from .engine import Pass, compass
from .entity import IssTrackEntity

PARALLEL_UPDATES = 0

_QUALITY_LABEL = {"poor": "Poor", "fair": "Fair", "good": "Good", "excellent": "Excellent"}
_SKY_LABEL = {
    "clear": "Clear sky forecast.",
    "partly_cloudy": "Partly cloudy forecast.",
    "cloudy": "Cloudy forecast.",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IssTrackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(PassCalendar(coordinator, owner) for owner in coordinator.books)


def _event(item: Pass, sky: str) -> CalendarEvent:
    """One pass as a calendar event. Text shown to the user, so plain words."""
    parts = [
        f"Rises in the {compass(item.start_azimuth)}, "
        f"highest at {item.peak_elevation:.0f}° in the {compass(item.peak_azimuth)}, "
        f"ends in the {compass(item.end_azimuth)}.",
        f"Estimated magnitude {item.magnitude:.1f}.",
    ]
    if item.starts_in_shadow:
        parts.append("Appears as it leaves Earth's shadow.")
    if item.ends_in_shadow:
        parts.append("Fades as it enters Earth's shadow.")
    if sky in _SKY_LABEL:
        parts.append(_SKY_LABEL[sky])
    return CalendarEvent(
        start=dt_util.as_local(item.start),
        end=dt_util.as_local(item.end),
        summary=f"ISS pass: {_QUALITY_LABEL[item.quality]}, {item.peak_elevation:.0f}°",
        description=" ".join(parts),
        uid=item.start.isoformat(),
    )


class PassCalendar(IssTrackEntity, CalendarEntity):
    """Matching passes as events, so a calendar trigger can fire ahead of one."""

    def __init__(self, coordinator: IssTrackCoordinator, owner: str) -> None:
        super().__init__(coordinator, owner, "passes")

    @property
    def event(self) -> CalendarEvent | None:
        book = self.book
        if book is None:
            return None
        item = book.upcoming(self.coordinator.criteria, dt_util.utcnow())
        return None if item is None else _event(item, book.sky_for(item))

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        book = self.book
        if book is None:
            return []
        return [
            _event(item, book.sky_for(item))
            for item in book.matching(self.coordinator.criteria)
            if item.end >= start_date and item.start <= end_date
        ]

"""Base entity: device grouping and the observer an entity belongs to."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, OBSERVER_HOME, PANEL_TITLE
from .coordinator import IssTrackCoordinator, ObserverBook

# Unique ids are "<entry>|<owner>|<key>". The owner is "iss" for the station
# itself, "home", or a person's entity id.
OWNER_ISS = "iss"


def unique_id(entry_id: str, owner: str, key: str) -> str:
    return f"{entry_id}|{owner}|{key}"


class IssTrackEntity(CoordinatorEntity[IssTrackCoordinator]):
    """An entity on the ISS Track device, or on a tracked person's device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: IssTrackCoordinator, owner: str, key: str) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._owner = owner
        self._attr_unique_id = unique_id(entry_id, owner, key)
        self._attr_translation_key = key
        if owner in (OWNER_ISS, OBSERVER_HOME):
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, entry_id)},
                name=PANEL_TITLE,
                manufacturer=PANEL_TITLE,
                model="International Space Station",
                entry_type=DeviceEntryType.SERVICE,
            )
        else:
            book = coordinator.books.get(owner)
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{entry_id}|{owner}")},
                name=f"{PANEL_TITLE} {book.name if book else owner}",
                manufacturer=PANEL_TITLE,
                model="Passes for a person",
                entry_type=DeviceEntryType.SERVICE,
                via_device=(DOMAIN, entry_id),
            )

    @property
    def book(self) -> ObserverBook | None:
        """The observer this entity describes; None for the station itself."""
        return self.coordinator.books.get(self._owner)

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if self._owner == OWNER_ISS:
            return True
        book = self.book
        return book is not None and book.observer is not None

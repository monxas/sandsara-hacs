"""Sensor platform for Sandsara track info and playlist."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, get_pattern_name
from .coordinator import SandsaraCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sandsara sensor entities."""
    coordinator: SandsaraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        SandsaraTrackSensor(coordinator, entry),
        SandsaraProgressSensor(coordinator, entry),
        SandsaraPlaylistSensor(coordinator, entry),
    ])


class SandsaraTrackSensor(CoordinatorEntity[SandsaraCoordinator], SensorEntity):
    """Sensor showing current track name and index."""

    _attr_has_entity_name = True
    _attr_name = "Current track"
    _attr_icon = "mdi:music-note"

    def __init__(
        self, coordinator: SandsaraCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_current_track"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        )

    @property
    def available(self) -> bool:
        return self.coordinator.device_data.connected

    @property
    def native_value(self) -> str | None:
        idx = self.coordinator.device_data.current_track_index
        if idx is not None:
            return self.coordinator.device_data.current_track_name
        return None

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.device_data
        attrs = {}
        if data.current_track_index is not None:
            attrs["track_index"] = data.current_track_index
        attrs["playing"] = data.is_playing
        attrs["progress"] = data.progress
        return attrs


class SandsaraProgressSensor(CoordinatorEntity[SandsaraCoordinator], SensorEntity):
    """Sensor showing current track progress percentage."""

    _attr_has_entity_name = True
    _attr_name = "Track progress"
    _attr_icon = "mdi:progress-clock"
    _attr_native_unit_of_measurement = "%"

    def __init__(
        self, coordinator: SandsaraCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_progress"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        )

    @property
    def available(self) -> bool:
        return self.coordinator.device_data.connected

    @property
    def native_value(self) -> int:
        return self.coordinator.device_data.progress


class SandsaraPlaylistSensor(CoordinatorEntity[SandsaraCoordinator], SensorEntity):
    """Sensor showing current playlist."""

    _attr_has_entity_name = True
    _attr_name = "Playlist"
    _attr_icon = "mdi:playlist-music"

    def __init__(
        self, coordinator: SandsaraCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_playlist"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        )

    @property
    def available(self) -> bool:
        return self.coordinator.device_data.connected

    @property
    def native_value(self) -> str:
        names = self.coordinator.device_data.playlist_names
        if names:
            return f"{len(names)} patterns"
        return "Empty"

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.device_data
        return {
            "tracks": data.playlist,
            "track_names": data.playlist_names,
            "count": len(data.playlist),
        }

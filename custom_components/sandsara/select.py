"""Select platform for Sandsara pattern selection."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
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
    """Set up Sandsara select entities."""
    coordinator: SandsaraCoordinator = hass.data[DOMAIN][entry.entry_id]
    # Load playlists before creating entities
    await coordinator.async_load_playlists()
    async_add_entities([
        SandsaraPatternSelect(coordinator, entry),
        SandsaraPlaylistSelect(coordinator, entry),
    ])


class SandsaraPatternSelect(CoordinatorEntity[SandsaraCoordinator], SelectEntity):
    """Select entity for choosing a pattern from the playlist."""

    _attr_has_entity_name = True
    _attr_name = "Pattern"
    _attr_icon = "mdi:draw"

    def __init__(
        self, coordinator: SandsaraCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_pattern_select"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.device_data.connected

    @property
    def options(self) -> list[str]:
        """Return list of available patterns from current playlist."""
        playlist = self.coordinator.device_data.playlist
        if not playlist:
            # Fallback: show all available files
            available = self.coordinator.device_data.available_files
            if available:
                return [
                    f"{get_pattern_name(i)} ({i})"
                    for i, exists in sorted(available.items())
                    if exists
                ]
            return ["No patterns available"]
        return [
            f"{get_pattern_name(i)} ({i})"
            for i in playlist
        ]

    @property
    def current_option(self) -> str | None:
        """Return the currently selected pattern."""
        idx = self.coordinator.device_data.current_track_index
        if idx is not None:
            return f"{get_pattern_name(idx)} ({idx})"
        return None

    async def async_select_option(self, option: str) -> None:
        """Select a pattern by name."""
        # Extract index from "Pattern Name (N)" format
        try:
            idx_str = option.rsplit("(", 1)[1].rstrip(")")
            track_index = int(idx_str)
        except (IndexError, ValueError):
            _LOGGER.error("Sandsara: could not parse pattern index from '%s'", option)
            return

        await self.coordinator.async_select_track(track_index)


class SandsaraPlaylistSelect(CoordinatorEntity[SandsaraCoordinator], SelectEntity):
    """Select entity for choosing and activating a saved playlist."""

    _attr_has_entity_name = True
    _attr_name = "Playlist"
    _attr_icon = "mdi:playlist-music"

    def __init__(
        self, coordinator: SandsaraCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_playlist_select"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        )

    @property
    def available(self) -> bool:
        return self.coordinator.device_data.connected

    @property
    def options(self) -> list[str]:
        playlists = self.coordinator.playlists
        if not playlists:
            return ["No playlists"]
        return list(playlists.keys())

    @property
    def current_option(self) -> str | None:
        return self.coordinator.device_data.active_playlist_name

    async def async_select_option(self, option: str) -> None:
        if option == "No playlists":
            return
        await self.coordinator.async_play_playlist(option)

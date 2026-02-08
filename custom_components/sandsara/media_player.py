"""Media player platform for Sandsara playback control."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SandsaraCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sandsara media player."""
    coordinator: SandsaraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SandsaraPlayer(coordinator, entry)])


class SandsaraPlayer(CoordinatorEntity[SandsaraCoordinator], MediaPlayerEntity):
    """Sandsara playback control entity."""

    _attr_has_entity_name = True
    _attr_name = "Playback"
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.STOP
    )

    def __init__(
        self, coordinator: SandsaraCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the media player."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_player"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            name=entry.title or "Sandsara",
            manufacturer="Sandsara",
            model=coordinator.device_data.model or "Mini Pro",
            sw_version=coordinator.device_data.firmware,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.device_data.connected

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current state."""
        if not self.coordinator.device_data.connected:
            return MediaPlayerState.OFF
        if self.coordinator.device_data.is_playing:
            return MediaPlayerState.PLAYING
        return MediaPlayerState.PAUSED

    async def async_media_play(self) -> None:
        """Send play command."""
        await self.coordinator.async_play()

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.coordinator.async_pause()

    async def async_media_stop(self) -> None:
        """Send sleep command."""
        await self.coordinator.async_sleep()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.coordinator.async_next_track()

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.coordinator.async_previous_track()

    @property
    def media_title(self) -> str | None:
        """Return current track name."""
        return self.coordinator.device_data.current_track_name

    @property
    def media_track(self) -> int | None:
        """Return current track index."""
        return self.coordinator.device_data.current_track_index

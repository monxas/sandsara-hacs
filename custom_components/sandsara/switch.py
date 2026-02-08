"""Switch platform for Sandsara shuffle toggle."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up Sandsara switch entities."""
    coordinator: SandsaraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        SandsaraShuffleSwitch(coordinator, entry),
        SandsaraSpiralSwitch(coordinator, entry),
    ])


class SandsaraShuffleSwitch(CoordinatorEntity[SandsaraCoordinator], SwitchEntity):
    """Switch to toggle shuffle mode."""

    _attr_has_entity_name = True
    _attr_name = "Shuffle"
    _attr_icon = "mdi:shuffle-variant"

    def __init__(
        self, coordinator: SandsaraCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_shuffle"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        )

    @property
    def available(self) -> bool:
        return self.coordinator.device_data.connected

    @property
    def is_on(self) -> bool:
        return self.coordinator.device_data.shuffle

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_shuffle(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_shuffle(False)


class SandsaraSpiralSwitch(CoordinatorEntity[SandsaraCoordinator], SwitchEntity):
    """Switch to toggle spiral before pattern."""

    _attr_has_entity_name = True
    _attr_name = "Spiral before pattern"
    _attr_icon = "mdi:spiral"

    def __init__(
        self, coordinator: SandsaraCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_spiral_before_pattern"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        )

    @property
    def available(self) -> bool:
        return self.coordinator.device_data.connected

    @property
    def is_on(self) -> bool:
        return self.coordinator.device_data.spiral_before_pattern

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_spiral_before_pattern(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_spiral_before_pattern(False)

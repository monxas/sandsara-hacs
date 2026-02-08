"""Number platform for Sandsara speed controls."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
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
    """Set up Sandsara number entities."""
    coordinator: SandsaraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        SandsaraBallSpeed(coordinator, entry),
        SandsaraLedSpeed(coordinator, entry),
        SandsaraPauseBetweenPatterns(coordinator, entry),
    ])


class SandsaraBallSpeed(CoordinatorEntity[SandsaraCoordinator], NumberEntity):
    """Ball/motor speed control."""

    _attr_has_entity_name = True
    _attr_name = "Ball speed"
    _attr_icon = "mdi:speedometer"
    _attr_native_min_value = 1
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self, coordinator: SandsaraCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_ball_speed"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.device_data.connected

    @property
    def native_value(self) -> float:
        """Return current ball speed."""
        return self.coordinator.device_data.ball_speed

    async def async_set_native_value(self, value: float) -> None:
        """Set ball speed."""
        await self.coordinator.async_set_ball_speed(int(value))


class SandsaraLedSpeed(CoordinatorEntity[SandsaraCoordinator], NumberEntity):
    """LED animation speed control."""

    _attr_has_entity_name = True
    _attr_name = "LED animation speed"
    _attr_icon = "mdi:led-strip-variant"
    _attr_native_min_value = 1
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self, coordinator: SandsaraCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_led_speed"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.device_data.connected

    @property
    def native_value(self) -> float:
        """Return current LED speed."""
        return self.coordinator.device_data.led_speed

    async def async_set_native_value(self, value: float) -> None:
        """Set LED animation speed."""
        await self.coordinator.async_set_led_speed(int(value))


class SandsaraPauseBetweenPatterns(CoordinatorEntity[SandsaraCoordinator], NumberEntity):
    """Pause duration between patterns (seconds)."""

    _attr_has_entity_name = True
    _attr_name = "Pause between patterns"
    _attr_icon = "mdi:timer-sand"
    _attr_native_min_value = 0
    _attr_native_max_value = 300
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "s"
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self, coordinator: SandsaraCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_pause_between_patterns"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        )

    @property
    def available(self) -> bool:
        return self.coordinator.device_data.connected

    @property
    def native_value(self) -> float:
        return self.coordinator.device_data.pause_between_patterns

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_pause_between_patterns(int(value))

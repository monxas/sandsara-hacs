"""Light platform for Sandsara LED control."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SandsaraCoordinator, SandsaraData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sandsara light."""
    coordinator: SandsaraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SandsaraLight(coordinator, entry)])


class SandsaraLight(CoordinatorEntity[SandsaraCoordinator], LightEntity):
    """Sandsara LED light entity."""

    _attr_has_entity_name = True
    _attr_name = "LED"
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    def __init__(
        self, coordinator: SandsaraCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_light"
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
    def is_on(self) -> bool:
        """Return true if LED is on."""
        return self.coordinator.device_data.led_on

    @property
    def brightness(self) -> int | None:
        """Return brightness (HA uses 0-255 scale)."""
        return int(self.coordinator.device_data.brightness * 255 / 100)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return current RGB color."""
        return self.coordinator.device_data.rgb_color

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the LED."""
        if ATTR_BRIGHTNESS in kwargs:
            # HA sends 0-255, device expects 0-100
            ha_brightness = kwargs[ATTR_BRIGHTNESS]
            device_brightness = max(1, int(ha_brightness * 100 / 255))
            await self.coordinator.async_set_brightness(device_brightness)

        if ATTR_RGB_COLOR in kwargs:
            r, g, b = kwargs[ATTR_RGB_COLOR]
            await self.coordinator.async_set_color(r, g, b)

        if not self.coordinator.device_data.led_on:
            await self.coordinator.async_led_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the LED."""
        await self.coordinator.async_led_off()

"""Button entities for Sandsara."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SandsaraCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sandsara button entities."""
    coordinator: SandsaraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        SandsaraDisconnectButton(coordinator, entry),
        SandsaraConnectButton(coordinator, entry),
    ])


class SandsaraDisconnectButton(ButtonEntity):
    """Button to disconnect from Sandsara."""

    _attr_has_entity_name = True
    _attr_name = "Disconnect"
    _attr_icon = "mdi:bluetooth-off"

    def __init__(self, coordinator: SandsaraCoordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_disconnect"
        self._attr_device_info = coordinator.device_data

    async def async_press(self) -> None:
        """Disconnect from device."""
        await self.coordinator.async_disconnect()


class SandsaraConnectButton(ButtonEntity):
    """Button to reconnect to Sandsara."""

    _attr_has_entity_name = True
    _attr_name = "Connect"
    _attr_icon = "mdi:bluetooth-connect"

    def __init__(self, coordinator: SandsaraCoordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_connect"
        self._attr_device_info = coordinator.device_data

    async def async_press(self) -> None:
        """Reconnect to device."""
        await self.coordinator.async_reconnect()

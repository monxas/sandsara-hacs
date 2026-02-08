"""Sandsara integration for Home Assistant."""
from __future__ import annotations

import logging
import os

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import SandsaraCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

SERVICE_UPLOAD_PATTERN = "upload_pattern"
SERVICE_UPLOAD_SCHEMA = vol.Schema({
    vol.Required("file_path"): cv.string,
    vol.Optional("entry_id"): cv.string,
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sandsara from a config entry."""
    address = entry.data.get(CONF_ADDRESS) or entry.unique_id
    if not address:
        raise ConfigEntryNotReady("No device address configured")

    coordinator = SandsaraCoordinator(hass, address, entry)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"Unable to connect to Sandsara: {err}") from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register upload service (once for the domain)
    if not hass.services.has_service(DOMAIN, SERVICE_UPLOAD_PATTERN):
        async def handle_upload_pattern(call: ServiceCall) -> None:
            """Handle the upload_pattern service call."""
            file_path = call.data["file_path"]
            entry_id = call.data.get("entry_id")

            if not os.path.isfile(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            # Find the coordinator
            if entry_id and entry_id in hass.data[DOMAIN]:
                coord = hass.data[DOMAIN][entry_id]
            else:
                # Use the first (or only) Sandsara device
                coordinators = [
                    v for v in hass.data[DOMAIN].values()
                    if isinstance(v, SandsaraCoordinator)
                ]
                if not coordinators:
                    raise RuntimeError("No Sandsara device configured")
                coord = coordinators[0]

            await coord.async_upload_pattern(file_path)

        hass.services.async_register(
            DOMAIN,
            SERVICE_UPLOAD_PATTERN,
            handle_upload_pattern,
            schema=SERVICE_UPLOAD_SCHEMA,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: SandsaraCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

        # Remove service if no more entries
        remaining = [
            v for v in hass.data.get(DOMAIN, {}).values()
            if isinstance(v, SandsaraCoordinator)
        ]
        if not remaining:
            hass.services.async_remove(DOMAIN, SERVICE_UPLOAD_PATTERN)

    return unload_ok

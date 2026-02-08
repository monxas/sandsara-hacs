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
    Platform.BUTTON,
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

SERVICE_CREATE_PLAYLIST = "create_playlist"
SERVICE_CREATE_PLAYLIST_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string,
    vol.Required("tracks"): vol.All(cv.ensure_list, [vol.Coerce(int)]),
    vol.Optional("entry_id"): cv.string,
})

SERVICE_DELETE_PLAYLIST = "delete_playlist"
SERVICE_DELETE_PLAYLIST_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string,
    vol.Optional("entry_id"): cv.string,
})

SERVICE_PLAY_PLAYLIST = "play_playlist"
SERVICE_PLAY_PLAYLIST_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string,
    vol.Optional("entry_id"): cv.string,
})

SERVICE_ADD_TO_PLAYLIST = "add_to_playlist"
SERVICE_ADD_TO_PLAYLIST_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string,
    vol.Required("track_index"): vol.Coerce(int),
    vol.Optional("entry_id"): cv.string,
})

SERVICE_REMOVE_FROM_PLAYLIST = "remove_from_playlist"
SERVICE_REMOVE_FROM_PLAYLIST_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string,
    vol.Required("track_index"): vol.Coerce(int),
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

            _LOGGER.warning("Sandsara: upload_pattern service called with file_path=%s", file_path)
            try:
                result = await coord.async_upload_pattern(file_path)
                _LOGGER.warning("Sandsara: upload_pattern completed, result=%s", result)
            except Exception as err:
                _LOGGER.error("Sandsara: upload_pattern FAILED: %s", err, exc_info=True)
                raise

        hass.services.async_register(
            DOMAIN,
            SERVICE_UPLOAD_PATTERN,
            handle_upload_pattern,
            schema=SERVICE_UPLOAD_SCHEMA,
        )

    def _get_coordinator(call: ServiceCall) -> SandsaraCoordinator:
        """Get coordinator from service call."""
        entry_id = call.data.get("entry_id")
        if entry_id and entry_id in hass.data[DOMAIN]:
            return hass.data[DOMAIN][entry_id]
        coordinators = [
            v for v in hass.data[DOMAIN].values()
            if isinstance(v, SandsaraCoordinator)
        ]
        if not coordinators:
            raise RuntimeError("No Sandsara device configured")
        return coordinators[0]

    if not hass.services.has_service(DOMAIN, SERVICE_CREATE_PLAYLIST):
        async def handle_create_playlist(call: ServiceCall) -> None:
            coord = _get_coordinator(call)
            await coord.async_create_playlist(call.data["name"], call.data["tracks"])

        async def handle_delete_playlist(call: ServiceCall) -> None:
            coord = _get_coordinator(call)
            await coord.async_delete_playlist(call.data["name"])

        async def handle_play_playlist(call: ServiceCall) -> None:
            coord = _get_coordinator(call)
            await coord.async_play_playlist(call.data["name"])

        async def handle_add_to_playlist(call: ServiceCall) -> None:
            coord = _get_coordinator(call)
            await coord.async_add_to_playlist(call.data["name"], call.data["track_index"])

        async def handle_remove_from_playlist(call: ServiceCall) -> None:
            coord = _get_coordinator(call)
            await coord.async_remove_from_playlist(call.data["name"], call.data["track_index"])

        hass.services.async_register(DOMAIN, SERVICE_CREATE_PLAYLIST, handle_create_playlist, schema=SERVICE_CREATE_PLAYLIST_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_DELETE_PLAYLIST, handle_delete_playlist, schema=SERVICE_DELETE_PLAYLIST_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_PLAY_PLAYLIST, handle_play_playlist, schema=SERVICE_PLAY_PLAYLIST_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_ADD_TO_PLAYLIST, handle_add_to_playlist, schema=SERVICE_ADD_TO_PLAYLIST_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_REMOVE_FROM_PLAYLIST, handle_remove_from_playlist, schema=SERVICE_REMOVE_FROM_PLAYLIST_SCHEMA)

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
            for svc in (SERVICE_UPLOAD_PATTERN, SERVICE_CREATE_PLAYLIST, SERVICE_DELETE_PLAYLIST, SERVICE_PLAY_PLAYLIST, SERVICE_ADD_TO_PLAYLIST, SERVICE_REMOVE_FROM_PLAYLIST):
                hass.services.async_remove(DOMAIN, svc)

    return unload_ok

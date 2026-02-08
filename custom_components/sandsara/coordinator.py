"""BLE connection coordinator for Sandsara."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta

from bleak.exc import BleakError
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    establish_connection,
)

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from homeassistant.helpers.storage import Store

from .const import (
    CHAR_COMMAND,
    CHAR_DATETIME,
    CHAR_FILE_DATA,
    CHAR_FILE_FLAG,
    CHAR_FILE_UNKNOWN,
    CHAR_MODEL,
    CHAR_PLAYBACK,
    CHAR_SETTINGS,
    CHAR_STATUS,
    CHAR_VERSION,
    CMD_BALL_SPEED,
    CMD_BRIGHTNESS,
    CMD_INIT,
    CMD_LED_COLOR,
    CMD_LED_SPEED,
    CMD_LED_TOGGLE,
    DOMAIN,
    DT_INIT_FILE_ARRAY_END,
    DT_INIT_FILE_ARRAY_START,
    DT_INIT_NAME_END,
    DT_INIT_NAME_START,
    FILE_CHUNK_SIZE,
    FILE_TRANSFER_START_CMD,
    PB_ADD_TO_PLAYLIST,
    PB_INIT,
    PB_NEXT,
    PB_NOTIFY_ACK,
    PB_NOTIFY_DONE,
    PB_NOTIFY_PROGRESS,
    PB_NOTIFY_STATE,
    PB_NOTIFY_STATUS,
    PB_NOTIFY_TRACK,
    PB_PAUSE,
    PB_PLAY,
    PB_PREV,
    PB_SELECT,
    PB_SHUFFLE,
    PB_SLEEP,
    STATUS_PLAYING,
    get_pattern_name,
)

_LOGGER = logging.getLogger(__name__)


class SandsaraData:
    """Current state of the Sandsara device."""

    def __init__(self) -> None:
        """Initialize state."""
        self.connected: bool = False
        self.model: str = ""
        self.firmware: str = ""
        self.device_name: str = ""
        self.is_playing: bool = False
        self.led_on: bool = True
        self.brightness: int = 50
        self.ball_speed: int = 50
        self.led_speed: int = 72
        self.rgb_color: tuple[int, int, int] = (255, 255, 255)
        # Playlist & track info
        self.playlist: list[int] = []
        self.playlist_names: list[str] = []
        self.current_track_index: int | None = None
        self.current_track_name: str = "Unknown"
        self.progress: int = 0
        self.shuffle: bool = False
        # File existence array (index -> exists)
        self.available_files: dict[int, bool] = {}
        # Settings from CHAR_SETTINGS CSV
        self.pause_between_patterns: int = 0  # seconds
        self.spiral_before_pattern: bool = True
        self._settings_raw: list[str] = []  # preserve all CSV fields
        # Playlist manager
        self.active_playlist_name: str | None = None


class SandsaraCoordinator(DataUpdateCoordinator[SandsaraData]):
    """Coordinator to manage BLE connection to Sandsara."""

    def __init__(
        self, hass: HomeAssistant, address: str, entry: ConfigEntry
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.address = address
        self._entry = entry
        self._client: BleakClientWithServiceCache | None = None
        self._connect_lock = asyncio.Lock()
        self._initialized = False
        self._manual_disconnect = False
        self.device_data = SandsaraData()
        # File transfer (unused legacy vars removed — flow control is local now)
        # Playlist storage
        self._playlist_store = Store(hass, 1, "sandsara_playlists")
        self._playlists: dict[str, list[int]] = {}
        self._playlists_loaded = False
        # Custom pattern names (track_id -> friendly name)
        self._custom_names_store = Store(hass, 1, "sandsara_custom_names")
        self._custom_names: dict[str, str] = {}  # {"303": "Real Oviedo"}
        self._custom_names_loaded = False

    async def _async_update_data(self) -> SandsaraData:
        """Poll device state."""
        try:
            await self._ensure_connected()
            if self._client and self._client.is_connected:
                await self._read_status()
            return self.device_data
        except Exception as err:
            _LOGGER.error("Sandsara update failed: %s", err, exc_info=True)
            self.device_data.connected = False
            raise UpdateFailed(f"Failed to update: {err}") from err

    async def _ensure_connected(self) -> None:
        """Ensure connection to device."""
        if getattr(self, '_manual_disconnect', False):
            return
        if self._client and self._client.is_connected:
            return

        async with self._connect_lock:
            if self._client and self._client.is_connected:
                return

            _LOGGER.debug("Sandsara: looking up BLE device %s", self.address)
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if not ble_device:
                _LOGGER.warning(
                    "Sandsara: device %s not found in BLE scanner", self.address
                )
                raise UpdateFailed(f"Device {self.address} not found")

            _LOGGER.info(
                "Sandsara: connecting to %s (%s)",
                ble_device.name,
                self.address,
            )
            self._client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                ble_device.name or self.address,
                self._disconnected,
                max_attempts=3,
            )
            _LOGGER.info("Sandsara: connected, running init handshake")
            self._initialized = False
            await self._initialize_device()

    async def _initialize_device(self) -> None:
        """Run the init handshake sequence."""
        if not self._client or self._initialized:
            return

        client = self._client

        # Log all discovered services and characteristics
        for service in client.services:
            _LOGGER.debug("Sandsara: service %s", service.uuid)
            for char in service.characteristics:
                _LOGGER.debug(
                    "Sandsara:   char %s handle=%s props=%s",
                    char.uuid, char.handle, char.properties,
                )

        # Enable notifications on CHAR_DATETIME first
        try:
            await client.start_notify(CHAR_DATETIME, self._datetime_notification_handler)
        except Exception as err:
            _LOGGER.debug("Sandsara: failed to enable notify on DATETIME: %s", err)

        # Init DATETIME — write 0x00 to get device info + file array
        _LOGGER.debug("Sandsara: sending DATETIME init")
        await client.write_gatt_char(CHAR_DATETIME, bytes([0x00]), response=True)
        await asyncio.sleep(0.3)

        # Enable notifications on CHAR_PLAYBACK
        try:
            await client.start_notify(CHAR_PLAYBACK, self._playback_notification_handler)
        except Exception as err:
            _LOGGER.debug("Sandsara: failed to enable notify on PLAYBACK: %s", err)

        # Read playlist from CHAR_PLAYBACK
        try:
            playlist_bytes = await client.read_gatt_char(CHAR_PLAYBACK)
            playlist_str = playlist_bytes.decode("ascii", errors="replace").strip()
            _LOGGER.debug("Sandsara: playlist raw = %s", playlist_str)
            self._parse_playlist(playlist_str)
        except Exception as err:
            _LOGGER.debug("Sandsara: failed to read playlist: %s", err)

        # Init PLAYBACK — write 0x00 to get state blob
        await client.write_gatt_char(CHAR_PLAYBACK, bytes([PB_INIT]), response=True)
        await asyncio.sleep(0.2)

        # Read settings
        try:
            settings_bytes = await client.read_gatt_char(CHAR_SETTINGS)
            settings_str = settings_bytes.decode("ascii", errors="replace").strip()
            _LOGGER.debug("Sandsara: settings = %s", settings_str)
            self._parse_settings(settings_str)
        except Exception as err:
            _LOGGER.debug("Sandsara: failed to read settings: %s", err)

        # Enable notifications on CHAR_COMMAND
        try:
            await client.start_notify(CHAR_COMMAND, self._command_notification_handler)
        except Exception as err:
            _LOGGER.debug("Sandsara: failed to enable notify on COMMAND: %s", err)

        # Init COMMAND — write 0x00 to get config blob
        await client.write_gatt_char(CHAR_COMMAND, bytes([CMD_INIT]), response=True)
        await asyncio.sleep(0.3)

        # Sync datetime
        now = datetime.now().isoformat()
        await client.write_gatt_char(
            CHAR_DATETIME, b"\x04" + now.encode("ascii"), response=True
        )
        _LOGGER.debug("Sandsara: datetime synced: %s", now)

        # Read device info
        try:
            model_bytes = await client.read_gatt_char(CHAR_MODEL)
            self.device_data.model = model_bytes.decode("ascii", errors="replace")
            _LOGGER.debug("Sandsara: model=%s", self.device_data.model)
        except Exception as err:
            _LOGGER.debug("Sandsara: failed to read model: %s", err)

        try:
            version_bytes = await client.read_gatt_char(CHAR_VERSION)
            self.device_data.firmware = version_bytes.decode(
                "ascii", errors="replace"
            )
            _LOGGER.debug("Sandsara: firmware=%s", self.device_data.firmware)
        except Exception as err:
            _LOGGER.debug("Sandsara: failed to read version: %s", err)

        self.device_data.connected = True
        self._initialized = True
        _LOGGER.info(
            "Sandsara initialized: model=%s firmware=%s playlist=%s",
            self.device_data.model,
            self.device_data.firmware,
            self.device_data.playlist,
        )

    def _parse_playlist(self, playlist_str: str) -> None:
        """Parse dash-separated playlist string into list of track indices."""
        if not playlist_str or playlist_str.strip() == "":
            self.device_data.playlist = []
            self.device_data.playlist_names = []
            return
        try:
            indices = [int(x) for x in playlist_str.split("-") if x.strip()]
            self.device_data.playlist = indices
            self.device_data.playlist_names = [
                get_pattern_name(i) for i in indices
            ]
            _LOGGER.debug(
                "Sandsara: parsed playlist: %d tracks — %s",
                len(indices), indices,
            )
        except ValueError as err:
            _LOGGER.warning("Sandsara: failed to parse playlist '%s': %s", playlist_str, err)

    @callback
    def _datetime_notification_handler(self, sender: int, data: bytearray) -> None:
        """Handle CHAR_DATETIME notifications."""
        if len(data) == 1:
            if data[0] == 0xFF:
                _LOGGER.debug("Sandsara: DATETIME ACK")
            elif data[0] == 0xFE:
                _LOGGER.debug("Sandsara: DATETIME done")
            return

        if len(data) > 2 and data[0] == 0x0B:
            # Brightness/settings notification: 0x0b + "100,0"
            text = data[1:].decode("ascii", errors="replace")
            _LOGGER.debug("Sandsara: DATETIME settings: %s", text)
            return

        if len(data) > 60 and data[0] == 0x00:
            # Init blob with device name + file existence array
            name_bytes = data[DT_INIT_NAME_START:DT_INIT_NAME_END]
            self.device_data.device_name = name_bytes.decode(
                "ascii", errors="replace"
            ).rstrip("\x00").strip()
            _LOGGER.debug("Sandsara: device name = '%s'", self.device_data.device_name)

            # Parse file existence array
            if len(data) >= DT_INIT_FILE_ARRAY_END:
                file_array = data[DT_INIT_FILE_ARRAY_START:DT_INIT_FILE_ARRAY_END]
                self.device_data.available_files = {
                    i: (b == 0x01) for i, b in enumerate(file_array)
                }
                available_count = sum(1 for v in self.device_data.available_files.values() if v)
                _LOGGER.debug(
                    "Sandsara: %d/%d file slots occupied",
                    available_count, len(file_array),
                )

    @callback
    def _playback_notification_handler(self, sender: int, data: bytearray) -> None:
        """Handle CHAR_PLAYBACK notifications."""
        if len(data) == 0:
            return

        cmd = data[0]

        if cmd == PB_NOTIFY_ACK:
            _LOGGER.debug("Sandsara: PLAYBACK ACK")
            return
        if cmd == PB_NOTIFY_DONE:
            _LOGGER.debug("Sandsara: PLAYBACK done")
            return

        if cmd == PB_NOTIFY_TRACK and len(data) > 1:
            # Track changed: 0x01 + "trackIdx,hash"
            text = data[1:].decode("ascii", errors="replace")
            parts = text.split(",", 1)
            try:
                track_idx = int(parts[0])
                self.device_data.current_track_index = track_idx
                self.device_data.current_track_name = get_pattern_name(track_idx)
                self.device_data.is_playing = True
                self.device_data.progress = 0
                _LOGGER.debug(
                    "Sandsara: track changed → %d (%s)",
                    track_idx, self.device_data.current_track_name,
                )
                self.async_set_updated_data(self.device_data)
            except (ValueError, IndexError):
                _LOGGER.debug("Sandsara: unparseable track notification: %s", text)
            return

        if cmd == PB_NOTIFY_PROGRESS and len(data) > 1:
            # Progress: 0x02 + "N"
            text = data[1:].decode("ascii", errors="replace")
            try:
                self.device_data.progress = int(text)
                # Only push update at key percentages to avoid flooding
                if self.device_data.progress in (0, 25, 50, 75, 100):
                    self.async_set_updated_data(self.device_data)
            except ValueError:
                _LOGGER.debug("Sandsara: unparseable progress: %s", text)
            return

        if cmd == PB_NOTIFY_STATUS and len(data) > 1:
            # Status: 0x03 + "status,time"
            text = data[1:].decode("ascii", errors="replace")
            parts = text.split(",", 1)
            try:
                status = int(parts[0])
                self.device_data.is_playing = status == 0
                if status == 1:
                    # Track ended
                    self.device_data.progress = 100
                _LOGGER.debug("Sandsara: status → %s (playing=%s)", text, status == 0)
                self.async_set_updated_data(self.device_data)
            except (ValueError, IndexError):
                _LOGGER.debug("Sandsara: unparseable status: %s", text)
            return

        if cmd == PB_NOTIFY_STATE and len(data) > 10:
            # Full state blob after init
            # Parse track info from the ASCII portion
            try:
                ascii_part = data[10:].decode("ascii", errors="replace").rstrip("\x00")
                if "," in ascii_part:
                    parts = ascii_part.split(",", 1)
                    track_str = parts[0].strip()
                    if track_str.isdigit():
                        idx = int(track_str)
                        self.device_data.current_track_index = idx
                        self.device_data.current_track_name = get_pattern_name(idx)
                    status_str = parts[1].strip() if len(parts) > 1 else ""
                    self.device_data.is_playing = status_str != "-1"
            except Exception as err:
                _LOGGER.debug("Sandsara: error parsing state blob: %s", err)
            return

    @callback
    def _command_notification_handler(self, sender: int, data: bytearray) -> None:
        """Handle CHAR_COMMAND notifications."""
        if len(data) == 1:
            return  # ACK/DONE

        if len(data) > 10 and data[0] == 0x00:
            # Config blob
            self.device_data.led_speed = data[1]
            self.device_data.ball_speed = data[2]
            self.device_data.brightness = data[5]
            self.device_data.is_playing = data[6] == 1
            _LOGGER.debug(
                "Sandsara config: led_speed=%d ball_speed=%d brightness=%d playing=%s",
                data[1], data[2], data[5], data[6] == 1,
            )

    async def async_disconnect(self) -> None:
        """Manually disconnect from device."""
        self._manual_disconnect = True
        if self._client and self._client.is_connected:
            _LOGGER.info("Sandsara: manual disconnect requested")
            await self._client.disconnect()
        self.device_data.connected = False
        self._initialized = False
        self._client = None
        self.async_set_updated_data(self.device_data)

    async def async_reconnect(self) -> None:
        """Manually reconnect to device."""
        self._manual_disconnect = False
        _LOGGER.info("Sandsara: manual reconnect requested")
        self._client = None
        self._initialized = False
        await self._ensure_connected()
        self.device_data.connected = True
        self.async_set_updated_data(self.device_data)

    @callback
    def _disconnected(self, client: BleakClientWithServiceCache) -> None:
        """Handle disconnection."""
        _LOGGER.warning("Sandsara disconnected")
        self.device_data.connected = False
        self._initialized = False
        self.async_set_updated_data(self.device_data)

    async def _read_status(self) -> None:
        """Read current status from device."""
        if not self._client:
            return
        try:
            status_bytes = await self._client.read_gatt_char(CHAR_STATUS)
            status = status_bytes.decode("ascii", errors="replace").strip()
            self.device_data.is_playing = status == STATUS_PLAYING
        except Exception as err:
            _LOGGER.debug("Sandsara: failed to read status: %s", err)

    def _resolve_char(self, uuid: str):
        """Resolve a characteristic by UUID from the service cache."""
        if not self._client:
            return None
        for service in self._client.services:
            for char in service.characteristics:
                if char.uuid.lower() == uuid.lower():
                    return char
        return None

    async def _write_command(self, data: bytes) -> None:
        """Write to the command characteristic."""
        await self._ensure_connected()
        if not self._client:
            _LOGGER.error("Sandsara: no client for write_command")
            return
        char = self._resolve_char(CHAR_COMMAND)
        if char:
            _LOGGER.debug(
                "Sandsara: write cmd %s to handle %s (uuid=%s)",
                data.hex(), char.handle, char.uuid,
            )
            await self._client.write_gatt_char(char, data, response=True)
        else:
            _LOGGER.error("Sandsara: CHAR_COMMAND %s not found!", CHAR_COMMAND)

    async def _write_playback(self, data: bytes) -> None:
        """Write to the playback characteristic."""
        await self._ensure_connected()
        if not self._client:
            _LOGGER.error("Sandsara: no client for write_playback")
            return
        char = self._resolve_char(CHAR_PLAYBACK)
        if char:
            _LOGGER.debug(
                "Sandsara: write pb %s to handle %s (uuid=%s)",
                data.hex(), char.handle, char.uuid,
            )
            await self._client.write_gatt_char(char, data, response=True)
        else:
            _LOGGER.error("Sandsara: CHAR_PLAYBACK %s not found!", CHAR_PLAYBACK)

    # ── Public API ──────────────────────────────────────────────────────

    async def async_play(self) -> None:
        """Start playing."""
        _LOGGER.info("Sandsara: play")
        await self._write_playback(bytes([PB_PLAY]))
        self.device_data.is_playing = True
        self.async_set_updated_data(self.device_data)

    async def async_pause(self) -> None:
        """Pause playback."""
        _LOGGER.info("Sandsara: pause")
        await self._write_playback(bytes([PB_PAUSE]))
        self.device_data.is_playing = False
        self.async_set_updated_data(self.device_data)

    async def async_next_track(self) -> None:
        """Skip to next track."""
        _LOGGER.info("Sandsara: next")
        await self._write_playback(bytes([PB_NEXT]))

    async def async_previous_track(self) -> None:
        """Skip to previous track."""
        _LOGGER.info("Sandsara: previous")
        await self._write_playback(bytes([PB_PREV]))

    async def async_sleep(self) -> None:
        """Put device to sleep."""
        _LOGGER.info("Sandsara: sleep")
        await self._write_playback(bytes([PB_SLEEP]))
        self.device_data.is_playing = False
        self.async_set_updated_data(self.device_data)

    async def async_add_track_to_device_playlist(self, track_id: int) -> None:
        """Add a track to the device's active playlist via BLE command 0x0B.

        This is the critical step the official app performs after uploading a
        pattern.  Without it the track exists on flash but is not in the
        playback rotation, so selecting it fails (device briefly switches
        then reverts).

        Protocol (from HCI capture):
          Write to PLAYBACK: 0x0B + ASCII track_id  (e.g. 0x0B "303")
        """
        _LOGGER.info(
            "Sandsara: adding track %d to device playlist (cmd 0x0B)", track_id,
        )
        payload = bytes([PB_ADD_TO_PLAYLIST]) + str(track_id).encode("ascii")
        await self._write_playback(payload)
        await asyncio.sleep(0.3)

        # Refresh the playlist from the device
        if self._client:
            try:
                playlist_bytes = await self._client.read_gatt_char(CHAR_PLAYBACK)
                playlist_str = playlist_bytes.decode("ascii", errors="replace").strip()
                _LOGGER.debug("Sandsara: refreshed playlist = %s", playlist_str)
                self._parse_playlist(playlist_str)
                self.async_set_updated_data(self.device_data)
            except Exception as err:
                _LOGGER.debug("Sandsara: failed to refresh playlist: %s", err)

    async def async_select_track(self, track_index: int) -> None:
        """Select a specific track by file index.

        If the track is not in the device playlist, add it first.
        """
        _LOGGER.info("Sandsara: select track %d (%s)", track_index, get_pattern_name(track_index))

        # If track is not in the device playlist, add it first
        playlist = self.device_data.playlist or []
        if track_index not in playlist and track_index >= 100:
            _LOGGER.info(
                "Sandsara: track %d not in device playlist %s, adding first",
                track_index, playlist,
            )
            await self.async_add_track_to_device_playlist(track_index)

        payload = bytes([PB_SELECT]) + str(track_index).encode("ascii")
        await self._write_playback(payload)
        self.device_data.current_track_index = track_index
        self.device_data.current_track_name = get_pattern_name(track_index)
        self.device_data.is_playing = True
        self.device_data.progress = 0
        self.async_set_updated_data(self.device_data)

    async def async_set_shuffle(self, enabled: bool) -> None:
        """Toggle shuffle mode."""
        _LOGGER.info("Sandsara: shuffle=%s", enabled)
        await self._write_playback(bytes([PB_SHUFFLE, 0x01 if enabled else 0x00]))
        self.device_data.shuffle = enabled
        self.async_set_updated_data(self.device_data)

    async def async_set_brightness(self, value: int) -> None:
        """Set LED brightness (0-100)."""
        value = max(0, min(100, value))
        _LOGGER.info("Sandsara: brightness=%d", value)
        await self._write_command(bytes([CMD_BRIGHTNESS, value]))
        self.device_data.brightness = value
        self.async_set_updated_data(self.device_data)

    async def async_set_ball_speed(self, value: int) -> None:
        """Set ball/motor speed (0-100)."""
        value = max(0, min(100, value))
        _LOGGER.info("Sandsara: ball_speed=%d", value)
        await self._write_command(bytes([CMD_BALL_SPEED, value]))
        self.device_data.ball_speed = value
        self.async_set_updated_data(self.device_data)

    async def async_set_led_speed(self, value: int) -> None:
        """Set LED animation speed (0-100)."""
        value = max(0, min(100, value))
        _LOGGER.info("Sandsara: led_speed=%d", value)
        await self._write_command(bytes([CMD_LED_SPEED, value]))
        self.device_data.led_speed = value
        self.async_set_updated_data(self.device_data)

    async def async_led_on(self) -> None:
        """Turn LEDs on."""
        _LOGGER.info("Sandsara: led_on")
        await self._write_command(bytes([CMD_LED_TOGGLE, 0x01]))
        self.device_data.led_on = True
        self.async_set_updated_data(self.device_data)

    async def async_led_off(self) -> None:
        """Turn LEDs off."""
        _LOGGER.info("Sandsara: led_off")
        await self._write_command(bytes([CMD_LED_TOGGLE, 0x00]))
        self.device_data.led_on = False
        self.async_set_updated_data(self.device_data)

    async def async_set_color(self, r: int, g: int, b: int) -> None:
        """Set LED color (solid). Uses gradient format with same color on both ends."""
        _LOGGER.info("Sandsara: color=(%d,%d,%d)", r, g, b)
        payload = bytes([CMD_LED_COLOR, 0x02, 0x00, 0xFF, r, r, g, g, b, b])
        await self._write_command(payload)
        self.device_data.rgb_color = (r, g, b)
        self.device_data.led_on = True
        self.async_set_updated_data(self.device_data)

    async def async_set_gradient(
        self, r1: int, g1: int, b1: int, r2: int, g2: int, b2: int
    ) -> None:
        """Set LED gradient between two colors."""
        _LOGGER.info("Sandsara: gradient=(%d,%d,%d)->(%d,%d,%d)", r1, g1, b1, r2, g2, b2)
        payload = bytes([CMD_LED_COLOR, 0x02, 0x00, 0xFF, r1, r2, g1, g2, b1, b2])
        await self._write_command(payload)
        self.device_data.led_on = True
        self.async_set_updated_data(self.device_data)

    async def _load_custom_names(self) -> None:
        """Load custom pattern names from storage."""
        if self._custom_names_loaded:
            return
        data = await self._custom_names_store.async_load()
        if data and isinstance(data, dict):
            self._custom_names = data.get("names", {})
        self._custom_names_loaded = True

    async def _save_custom_names(self) -> None:
        """Save custom pattern names to storage."""
        await self._custom_names_store.async_save({"names": self._custom_names})

    def get_custom_pattern_name(self, track_id: str | int) -> str | None:
        """Get custom name for a track ID (e.g. '303' -> 'Real Oviedo')."""
        return self._custom_names.get(str(track_id))

    async def async_upload_pattern(
        self, file_path: str, name: str | None = None, add_to_playlist: str | None = None,
    ) -> str:
        """Upload a pattern file to the Sandsara via BLE file transfer.

        Real protocol (verified from HCI capture of working Android app):
        1. Stop other notification subscriptions (avoid BLE contention)
        2. Enable notifications on File Flag CCCD
        3. Receive 0x00 on File Flag = "device ready" (arrives ~85ms after CCCD write)
        4. Write 0x6F to File Flag = "start upload" command (FIXED constant, NOT chunk count!)
        5. Receive 0x01 + ASCII filename on File Flag = device assigned track ID
        6. For each 244-byte chunk: Write Request to File Data, wait for 0x02 ack on File Flag
        7. Write 0x01 to File Flag = "transfer complete"
        8. Disable File Flag notifications, re-enable other notifications

        Args:
            file_path: Path to the .bin pattern file
            name: Optional friendly name (stored in HA, e.g. "Real Oviedo")
            add_to_playlist: Optional playlist name to add the track to after upload

        Returns the device-assigned filename (e.g. "303").
        """
        import math

        await self._ensure_connected()
        if not self._client:
            raise RuntimeError("Not connected to Sandsara")

        # Read file into memory first (in executor to avoid blocking)
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Pattern file not found: {file_path}")

        file_data = await self.hass.async_add_executor_job(
            lambda p=file_path: open(p, "rb").read()
        )
        file_size = len(file_data)
        total_chunks = math.ceil(file_size / FILE_CHUNK_SIZE)

        _LOGGER.warning(
            "Sandsara UPLOAD: file='%s' size=%d chunks=%d chunk_size=%d name='%s'",
            file_path, file_size, total_chunks, FILE_CHUNK_SIZE, name or "(none)",
        )

        # Notification handler with proper race condition handling
        _flag_event = asyncio.Event()
        _flag_data = bytearray()
        _notify_count = 0

        @callback
        def _file_flag_handler(sender: int, data: bytearray) -> None:
            nonlocal _flag_data, _notify_count
            _notify_count += 1
            _LOGGER.warning(
                "Sandsara UPLOAD: FILE_FLAG notify #%d: %s sender=%s",
                _notify_count, data.hex() if data else "empty", sender,
            )
            _flag_data[:] = data  # replace contents
            _flag_event.set()

        assigned_name = ""

        # ── Stop ALL other notifications to avoid BLE contention ──
        stopped_notifs: list[tuple[str, str]] = []
        for char_uuid, char_name in [
            (CHAR_DATETIME, "DATETIME"),
            (CHAR_PLAYBACK, "PLAYBACK"),
            (CHAR_COMMAND, "COMMAND"),
        ]:
            try:
                await self._client.stop_notify(char_uuid)
                stopped_notifs.append((char_uuid, char_name))
                _LOGGER.warning("Sandsara UPLOAD: stopped %s notifications", char_name)
            except Exception as e:
                _LOGGER.debug("Sandsara UPLOAD: %s stop_notify skipped: %s", char_name, e)

        await asyncio.sleep(0.3)

        try:
            mtu = getattr(self._client, 'mtu_size', None)
            _LOGGER.warning("Sandsara UPLOAD: MTU=%s", mtu)

            # ── Step 1: Set up event BEFORE enabling notifications (race condition fix) ──
            # The 0x00 ready signal can arrive before start_notify returns.
            # By NOT clearing the event after start_notify, we catch it either way.
            _flag_event.clear()

            _LOGGER.warning("Sandsara UPLOAD: [1/7] Enabling FILE_FLAG notifications...")
            await self._client.start_notify(CHAR_FILE_FLAG, _file_flag_handler)
            _LOGGER.warning("Sandsara UPLOAD: [1/7] FILE_FLAG notifications enabled")

            # ── Step 2: Wait for 0x00 "ready" ──
            _LOGGER.warning("Sandsara UPLOAD: [2/7] Waiting for 0x00 ready signal...")
            try:
                await asyncio.wait_for(_flag_event.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                _LOGGER.warning(
                    "Sandsara UPLOAD: [2/7] No ready signal in 5s (notify_count=%d), continuing...",
                    _notify_count,
                )

            if _flag_data and _flag_data[0] == 0x00:
                _LOGGER.warning("Sandsara UPLOAD: [2/7] ✓ Device ready (0x00)")
            else:
                _LOGGER.warning(
                    "Sandsara UPLOAD: [2/7] Ready signal was: %s (expected 0x00, continuing)",
                    _flag_data.hex() if _flag_data else "none",
                )

            # ── Step 3: Write 0x6F "start upload" command to FILE_FLAG ──
            # CRITICAL FIX: The app writes 0x6F (a fixed command), NOT the chunk count!
            # The old code wrote bytes([total_chunks]) which the device didn't recognize.
            _flag_event.clear()
            _LOGGER.warning(
                "Sandsara UPLOAD: [3/7] Writing START UPLOAD command 0x6F to FILE_FLAG..."
            )
            await self._client.write_gatt_char(
                CHAR_FILE_FLAG, bytes([FILE_TRANSFER_START_CMD]), response=True,
            )
            _LOGGER.warning("Sandsara UPLOAD: [3/7] ✓ 0x6F written")

            # ── Step 4: Wait for 0x01 + ASCII filename ──
            _LOGGER.warning("Sandsara UPLOAD: [4/7] Waiting for filename assignment (0x01+name)...")
            try:
                await asyncio.wait_for(_flag_event.wait(), timeout=15.0)
            except asyncio.TimeoutError:
                _LOGGER.error(
                    "Sandsara UPLOAD: [4/7] ✗ TIMEOUT! No filename ack in 15s. "
                    "flag_data=%s notify_count=%d",
                    _flag_data.hex() if _flag_data else "empty", _notify_count,
                )
                raise RuntimeError(
                    "Sandsara upload: device did not assign filename after 0x6F command (15s timeout)"
                )

            if _flag_data and _flag_data[0] == 0x01 and len(_flag_data) > 1:
                assigned_name = _flag_data[1:].decode("ascii", errors="replace")
                _LOGGER.warning(
                    "Sandsara UPLOAD: [4/7] ✓ Device assigned track ID: '%s'", assigned_name
                )
            else:
                _LOGGER.warning(
                    "Sandsara UPLOAD: [4/7] Unexpected response: %s (expected 0x01+name)",
                    _flag_data.hex() if _flag_data else "empty",
                )
                # Don't abort — some firmware versions might differ

            # ── Step 5: Send data chunks with 0x02 ack per chunk ──
            _LOGGER.warning(
                "Sandsara UPLOAD: [5/7] Sending %d chunks (%d bytes each, last may be shorter)...",
                total_chunks, FILE_CHUNK_SIZE,
            )

            for chunk_idx in range(total_chunks):
                offset = chunk_idx * FILE_CHUNK_SIZE
                chunk = file_data[offset : offset + FILE_CHUNK_SIZE]
                if not chunk:
                    _LOGGER.error("Sandsara UPLOAD: [5/7] Empty chunk at idx %d!", chunk_idx)
                    break

                _flag_event.clear()

                # Write chunk to FILE_DATA (Write Request with response)
                try:
                    await self._client.write_gatt_char(
                        CHAR_FILE_DATA, chunk, response=True,
                    )
                except Exception as write_err:
                    _LOGGER.error(
                        "Sandsara UPLOAD: [5/7] ✗ Chunk %d/%d write FAILED: %s",
                        chunk_idx + 1, total_chunks, write_err,
                    )
                    raise RuntimeError(
                        f"Chunk write failed at {chunk_idx + 1}/{total_chunks}: {write_err}"
                    ) from write_err

                # Wait for 0x02 ack on FILE_FLAG
                try:
                    await asyncio.wait_for(_flag_event.wait(), timeout=10.0)
                except asyncio.TimeoutError:
                    _LOGGER.error(
                        "Sandsara UPLOAD: [5/7] ✗ TIMEOUT waiting for ack on chunk %d/%d",
                        chunk_idx + 1, total_chunks,
                    )
                    raise RuntimeError(
                        f"Chunk ack timeout at {chunk_idx + 1}/{total_chunks}"
                    )

                if not _flag_data or _flag_data[0] != 0x02:
                    _LOGGER.warning(
                        "Sandsara UPLOAD: [5/7] Chunk %d ack unexpected: %s (expected 0x02)",
                        chunk_idx + 1, _flag_data.hex() if _flag_data else "empty",
                    )

                # Progress logging every 20 chunks + first + last
                if chunk_idx == 0 or (chunk_idx + 1) % 20 == 0 or chunk_idx == total_chunks - 1:
                    pct = round((chunk_idx + 1) / total_chunks * 100)
                    _LOGGER.warning(
                        "Sandsara UPLOAD: [5/7] Progress: %d/%d chunks (%d%%) — last chunk %d bytes",
                        chunk_idx + 1, total_chunks, pct, len(chunk),
                    )

            # ── Step 6: Signal transfer complete ──
            _LOGGER.warning("Sandsara UPLOAD: [6/7] Writing 0x01 (transfer complete) to FILE_FLAG...")
            await self._client.write_gatt_char(
                CHAR_FILE_FLAG, bytes([0x01]), response=True,
            )
            _LOGGER.warning(
                "Sandsara UPLOAD: [6/7] ✓ Transfer complete! Track ID='%s', %d chunks, %d bytes",
                assigned_name, total_chunks, file_size,
            )

            # ── Step 7: Post-transfer housekeeping ──
            _LOGGER.warning("Sandsara UPLOAD: [7/7] Post-transfer cleanup...")

            # Store custom name if provided
            if name and assigned_name:
                await self._load_custom_names()
                self._custom_names[assigned_name] = name
                await self._save_custom_names()
                _LOGGER.warning(
                    "Sandsara UPLOAD: [7/7] Stored custom name: track '%s' = '%s'",
                    assigned_name, name,
                )

            # Add to playlist if requested
            if add_to_playlist and assigned_name:
                try:
                    track_idx = int(assigned_name)
                    await self.async_load_playlists()
                    if add_to_playlist in self._playlists:
                        if track_idx not in self._playlists[add_to_playlist]:
                            self._playlists[add_to_playlist].append(track_idx)
                            await self._save_playlists()
                            _LOGGER.warning(
                                "Sandsara UPLOAD: [7/7] Added track %d to playlist '%s'",
                                track_idx, add_to_playlist,
                            )
                        else:
                            _LOGGER.warning(
                                "Sandsara UPLOAD: [7/7] Track %d already in playlist '%s'",
                                track_idx, add_to_playlist,
                            )
                    else:
                        # Create the playlist with just this track
                        self._playlists[add_to_playlist] = [track_idx]
                        await self._save_playlists()
                        _LOGGER.warning(
                            "Sandsara UPLOAD: [7/7] Created playlist '%s' with track %d",
                            add_to_playlist, track_idx,
                        )
                except ValueError:
                    _LOGGER.warning(
                        "Sandsara UPLOAD: [7/7] Can't add to playlist — "
                        "assigned_name '%s' is not numeric", assigned_name,
                    )

            # ── Step 7b: Add track to device playlist (critical missing step!) ──
            # The official app sends 0x0B + track_id to PLAYBACK after upload.
            # Without this, the track exists on flash but isn't in the active
            # playlist, so selecting it fails.
            if assigned_name:
                try:
                    track_id = int(assigned_name)
                    _LOGGER.warning(
                        "Sandsara UPLOAD: [7/7] Adding track %d to device playlist...",
                        track_id,
                    )
                    await self.async_add_track_to_device_playlist(track_id)
                    _LOGGER.warning(
                        "Sandsara UPLOAD: [7/7] ✓ Track %d added to device playlist",
                        track_id,
                    )
                except (ValueError, Exception) as err:
                    _LOGGER.warning(
                        "Sandsara UPLOAD: [7/7] Failed to add to device playlist: %s", err,
                    )

            # Refresh file existence array
            try:
                await self._client.write_gatt_char(
                    CHAR_DATETIME, bytes([0x00]), response=True,
                )
                await asyncio.sleep(0.5)
            except Exception as err:
                _LOGGER.debug("Sandsara UPLOAD: refresh file array failed: %s", err)

        except Exception as upload_err:
            _LOGGER.error(
                "Sandsara UPLOAD: ❌ FAILED: %s", upload_err, exc_info=True
            )
            raise

        finally:
            # Always clean up: disable file flag notifications
            try:
                await self._client.stop_notify(CHAR_FILE_FLAG)
                _LOGGER.warning("Sandsara UPLOAD: FILE_FLAG notifications stopped")
            except Exception:
                pass

            # Re-enable other notifications
            for char_uuid, char_name in stopped_notifs:
                handler_map = {
                    CHAR_DATETIME: self._datetime_notification_handler,
                    CHAR_PLAYBACK: self._playback_notification_handler,
                    CHAR_COMMAND: self._command_notification_handler,
                }
                handler = handler_map.get(char_uuid)
                if handler:
                    try:
                        await self._client.start_notify(char_uuid, handler)
                        _LOGGER.warning("Sandsara UPLOAD: re-enabled %s notifications", char_name)
                    except Exception as e:
                        _LOGGER.warning(
                            "Sandsara UPLOAD: failed to re-enable %s: %s", char_name, e
                        )

        return assigned_name

    async def async_list_device_files(self) -> list[str]:
        """List files on the Sandsara device via File Unknown characteristic.

        Protocol:
        1. Enable notifications on File Unknown CCCD
        2. Wait for 0xFF = "ready"
        3. Write 0x01 = "list files"
        4. Collect notifications: 0x01 + ASCII name(s) until 0xFE = "end"
        5. Disable notifications

        Returns list of file name strings (e.g. ["302", "303"]).
        """
        await self._ensure_connected()
        if not self._client:
            raise RuntimeError("Not connected to Sandsara")

        _event = asyncio.Event()
        _data = bytearray()
        _files: list[str] = []
        _done = asyncio.Event()

        @callback
        def _handler(sender: int, data: bytearray) -> None:
            nonlocal _data
            _LOGGER.debug("Sandsara: File Unknown notify: %s", data.hex())
            _data = data
            if data and data[0] == 0xFF:
                _event.set()  # ready
            elif data and data[0] == 0x01 and len(data) > 1:
                # File entry: 0x01 + ASCII names (dash-separated)
                names_str = data[1:].decode("ascii", errors="replace")
                for name in names_str.split("-"):
                    name = name.strip()
                    if name:
                        _files.append(name)
            elif data and data[0] == 0xFE:
                _done.set()  # end of list

        try:
            await self._client.start_notify(CHAR_FILE_UNKNOWN, _handler)

            # Wait for 0xFF ready
            try:
                await asyncio.wait_for(_event.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                _LOGGER.warning("Sandsara: no ready signal on File Unknown")

            # Write 0x01 = list files
            await self._client.write_gatt_char(
                CHAR_FILE_UNKNOWN, bytes([0x01]), response=True
            )

            # Wait for end marker 0xFE
            try:
                await asyncio.wait_for(_done.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                _LOGGER.warning("Sandsara: timeout waiting for file list end")

            _LOGGER.info("Sandsara: device files: %s", _files)
        finally:
            try:
                await self._client.stop_notify(CHAR_FILE_UNKNOWN)
            except Exception:
                pass

        return _files

    def _parse_settings(self, settings_str: str) -> None:
        """Parse CHAR_SETTINGS CSV: speed,pause_seconds,spiral_enabled,reserved."""
        if not settings_str:
            return
        parts = settings_str.split(",")
        self.device_data._settings_raw = parts
        if len(parts) >= 2:
            try:
                self.device_data.pause_between_patterns = int(parts[1])
            except ValueError:
                pass
        if len(parts) >= 3:
            try:
                self.device_data.spiral_before_pattern = parts[2] == "1"
            except (ValueError, IndexError):
                pass

    async def async_write_settings(self) -> None:
        """Write the current settings back to CHAR_SETTINGS as CSV."""
        await self._ensure_connected()
        if not self._client:
            return
        parts = list(self.device_data._settings_raw) if self.device_data._settings_raw else ["100", "0", "1", "0000000000000"]
        # Ensure minimum length
        while len(parts) < 4:
            parts.append("0")
        parts[1] = str(self.device_data.pause_between_patterns)
        parts[2] = "1" if self.device_data.spiral_before_pattern else "0"
        csv_str = ",".join(parts)
        _LOGGER.info("Sandsara: writing settings: %s", csv_str)
        char = self._resolve_char(CHAR_SETTINGS)
        if char:
            await self._client.write_gatt_char(char, csv_str.encode("ascii"), response=True)
        else:
            _LOGGER.error("Sandsara: CHAR_SETTINGS not found")

    async def async_set_pause_between_patterns(self, seconds: int) -> None:
        """Set pause between patterns in seconds."""
        self.device_data.pause_between_patterns = seconds
        await self.async_write_settings()
        self.async_set_updated_data(self.device_data)

    async def async_set_spiral_before_pattern(self, enabled: bool) -> None:
        """Set spiral before pattern on/off."""
        self.device_data.spiral_before_pattern = enabled
        await self.async_write_settings()
        self.async_set_updated_data(self.device_data)

    async def async_set_device_playlist(self, track_indices: list[int]) -> None:
        """Write a playlist to the device via CHAR_PLAYBACK.

        Writes dash-separated track indices (same format as read).
        """
        await self._ensure_connected()
        if not self._client:
            return
        playlist_str = "-".join(str(i) for i in track_indices)
        _LOGGER.info("Sandsara: setting device playlist: %s", playlist_str)
        char = self._resolve_char(CHAR_PLAYBACK)
        if char:
            await self._client.write_gatt_char(
                char, playlist_str.encode("ascii"), response=True
            )
            self._parse_playlist(playlist_str)
            self.async_set_updated_data(self.device_data)

    # ── Playlist Manager (HA-side storage) ──────────────────────────────

    async def async_load_playlists(self) -> None:
        """Load playlists from storage."""
        if self._playlists_loaded:
            return
        data = await self._playlist_store.async_load()
        if data and isinstance(data, dict):
            self._playlists = {
                k: v for k, v in data.get("playlists", {}).items()
                if isinstance(v, list)
            }
            self.device_data.active_playlist_name = data.get("active")
        self._playlists_loaded = True

    async def _save_playlists(self) -> None:
        """Save playlists to storage."""
        await self._playlist_store.async_save({
            "playlists": self._playlists,
            "active": self.device_data.active_playlist_name,
        })

    @property
    def custom_names(self) -> dict[str, str]:
        """Return custom track names."""
        return self._custom_names

    @property
    def playlists(self) -> dict[str, list[int]]:
        """Return all playlists."""
        return self._playlists

    async def async_create_playlist(self, name: str, tracks: list[int]) -> None:
        """Create a new playlist."""
        await self.async_load_playlists()
        self._playlists[name] = tracks
        await self._save_playlists()
        self.async_set_updated_data(self.device_data)

    async def async_delete_playlist(self, name: str) -> None:
        """Delete a playlist."""
        await self.async_load_playlists()
        self._playlists.pop(name, None)
        if self.device_data.active_playlist_name == name:
            self.device_data.active_playlist_name = None
        await self._save_playlists()
        self.async_set_updated_data(self.device_data)

    async def async_add_to_playlist(self, name: str, track_index: int) -> None:
        """Add a track to an existing playlist."""
        await self.async_load_playlists()
        if name not in self._playlists:
            raise ValueError(f"Playlist '{name}' not found")
        self._playlists[name].append(track_index)
        await self._save_playlists()
        self.async_set_updated_data(self.device_data)

    async def async_remove_from_playlist(self, name: str, track_index: int) -> None:
        """Remove a track from a playlist."""
        await self.async_load_playlists()
        if name not in self._playlists:
            raise ValueError(f"Playlist '{name}' not found")
        try:
            self._playlists[name].remove(track_index)
        except ValueError:
            pass
        await self._save_playlists()
        self.async_set_updated_data(self.device_data)

    async def async_play_playlist(self, name: str) -> None:
        """Activate a playlist: write tracks to device and start playing."""
        await self.async_load_playlists()
        if name not in self._playlists:
            raise ValueError(f"Playlist '{name}' not found")
        tracks = self._playlists[name]
        if not tracks:
            raise ValueError(f"Playlist '{name}' is empty")
        self.device_data.active_playlist_name = name
        await self._save_playlists()
        await self.async_set_device_playlist(tracks)
        # Start playback
        await self.async_play()

    async def async_shutdown(self) -> None:
        """Disconnect from device."""
        _LOGGER.info("Sandsara: shutting down")
        if self._client and self._client.is_connected:
            await self._client.disconnect()
        self._client = None
        self._initialized = False

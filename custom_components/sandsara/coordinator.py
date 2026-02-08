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

from .const import (
    CHAR_COMMAND,
    CHAR_DATETIME,
    CHAR_FILE_DATA,
    CHAR_FILE_FLAG,
    CHAR_FILE_STATUS,
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
        self.device_data = SandsaraData()
        # File transfer synchronization
        self._file_status_event = asyncio.Event()
        self._file_status_value: str = ""
        self._file_data_ack_event = asyncio.Event()
        self._file_data_ack_value: str = ""

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

    @callback
    def _file_status_notification_handler(self, sender: int, data: bytearray) -> None:
        """Handle File Status notifications during file transfer."""
        text = data.decode("ascii", errors="replace").strip()
        _LOGGER.debug("Sandsara: file status notification: %s", text)
        self._file_status_value = text
        self._file_status_event.set()

    @callback
    def _file_data_ack_handler(self, sender: int, data: bytearray) -> None:
        """Handle File Data notifications (chunk acks) during file transfer."""
        text = data.decode("ascii", errors="replace").strip()
        _LOGGER.debug("Sandsara: file data ack: %s", text)
        self._file_data_ack_value = text
        self._file_data_ack_event.set()

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

    async def async_select_track(self, track_index: int) -> None:
        """Select a specific track by file index."""
        _LOGGER.info("Sandsara: select track %d (%s)", track_index, get_pattern_name(track_index))
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

    async def async_upload_pattern(self, file_path: str) -> None:
        """Upload a pattern file to the Sandsara via BLE file transfer.

        Protocol:
        1. Write filename to File Flag → wait for "ok" on File Status
        2. Write 512-byte chunks to File Data → wait for "1" ack each
        3. Write any byte to File Flag → wait for "done" on File Status
        """
        await self._ensure_connected()
        if not self._client:
            raise RuntimeError("Not connected to Sandsara")

        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Pattern file not found: {file_path}")

        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        _LOGGER.info("Sandsara: uploading pattern '%s' (%d bytes)", filename, file_size)

        # Enable notifications on File Status (for "ok" and "done")
        try:
            await self._client.start_notify(
                CHAR_FILE_STATUS, self._file_status_notification_handler
            )
        except Exception as err:
            _LOGGER.warning("Sandsara: failed to enable File Status notify: %s", err)
            raise

        # Enable notifications on File Data (for chunk acks "1")
        try:
            await self._client.start_notify(
                CHAR_FILE_DATA, self._file_data_ack_handler
            )
        except Exception as err:
            _LOGGER.warning("Sandsara: failed to enable File Data notify: %s", err)
            await self._client.stop_notify(CHAR_FILE_STATUS)
            raise

        try:
            # Step 1: Write filename to File Flag
            self._file_status_event.clear()
            await self._client.write_gatt_char(
                CHAR_FILE_FLAG, filename.encode("ascii"), response=True
            )
            # Wait for "ok" response on File Status
            if not await self._wait_file_status("ok", timeout=10.0):
                raise RuntimeError("Sandsara: no 'ok' response after sending filename")

            # Step 2: Send file data in 512-byte chunks
            with open(file_path, "rb") as f:
                chunk_num = 0
                while True:
                    chunk = f.read(FILE_CHUNK_SIZE)
                    if not chunk:
                        break
                    self._file_data_ack_event.clear()
                    await self._client.write_gatt_char(
                        CHAR_FILE_DATA, chunk, response=True
                    )
                    # Wait for "1" ack on File Data notification
                    if not await self._wait_file_data_ack("1", timeout=10.0):
                        raise RuntimeError(
                            f"Sandsara: no ack for chunk {chunk_num}"
                        )
                    chunk_num += 1
                    if chunk_num % 50 == 0:
                        _LOGGER.debug(
                            "Sandsara: uploaded %d chunks (%d bytes)",
                            chunk_num, chunk_num * FILE_CHUNK_SIZE,
                        )

            # Step 3: Signal transfer complete
            self._file_status_event.clear()
            await self._client.write_gatt_char(
                CHAR_FILE_FLAG, bytes([0x00]), response=True
            )
            if not await self._wait_file_status("done", timeout=30.0):
                raise RuntimeError("Sandsara: no 'done' response after transfer")

            _LOGGER.info(
                "Sandsara: pattern '%s' uploaded successfully (%d chunks)",
                filename, chunk_num,
            )

            # Re-read file existence array after upload
            try:
                await self._client.write_gatt_char(
                    CHAR_DATETIME, bytes([0x00]), response=True
                )
                await asyncio.sleep(0.5)
            except Exception as err:
                _LOGGER.debug("Sandsara: failed to refresh file array after upload: %s", err)
        finally:
            # Disable notifications
            for char in (CHAR_FILE_STATUS, CHAR_FILE_DATA):
                try:
                    await self._client.stop_notify(char)
                except Exception:
                    pass

    async def _wait_file_status(self, expected: str, timeout: float = 10.0) -> bool:
        """Wait for a specific file status notification."""
        try:
            await asyncio.wait_for(self._file_status_event.wait(), timeout=timeout)
            return self._file_status_value == expected
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Sandsara: timeout waiting for file status '%s' (got '%s')",
                expected, self._file_status_value,
            )
            return False

    async def _wait_file_data_ack(self, expected: str, timeout: float = 10.0) -> bool:
        """Wait for a specific file data ack notification."""
        try:
            await asyncio.wait_for(self._file_data_ack_event.wait(), timeout=timeout)
            return self._file_data_ack_value == expected
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Sandsara: timeout waiting for file data ack '%s' (got '%s')",
                expected, self._file_data_ack_value,
            )
            return False

    async def async_shutdown(self) -> None:
        """Disconnect from device."""
        _LOGGER.info("Sandsara: shutting down")
        if self._client and self._client.is_connected:
            await self._client.disconnect()
        self._client = None
        self._initialized = False

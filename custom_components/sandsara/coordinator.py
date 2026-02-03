"""BLE connection coordinator for Sandsara."""
from __future__ import annotations

import asyncio
import logging
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
    CHAR_MODEL,
    CHAR_PLAYBACK,
    CHAR_STATUS,
    CHAR_VERSION,
    CMD_BALL_SPEED,
    CMD_BRIGHTNESS,
    CMD_INIT,
    CMD_LED_COLOR,
    CMD_LED_SPEED,
    CMD_LED_TOGGLE,
    DOMAIN,
    PB_INIT,
    PB_NEXT,
    PB_PAUSE,
    PB_PLAY,
    PB_SLEEP,
    STATUS_PLAYING,
)

_LOGGER = logging.getLogger(__name__)


class SandsaraData:
    """Current state of the Sandsara device."""

    def __init__(self) -> None:
        """Initialize state."""
        self.connected: bool = False
        self.model: str = ""
        self.firmware: str = ""
        self.is_playing: bool = False
        self.led_on: bool = True
        self.brightness: int = 50
        self.ball_speed: int = 50
        self.led_speed: int = 72
        self.rgb_color: tuple[int, int, int] = (255, 255, 255)


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

        # Enable notifications on notify-capable characteristics
        for service in client.services:
            for char in service.characteristics:
                if "notify" in char.properties:
                    try:
                        await client.start_notify(
                            char.uuid, self._notification_handler
                        )
                    except Exception as err:
                        _LOGGER.debug(
                            "Sandsara: failed to enable notify on %s: %s",
                            char.uuid, err,
                        )

        # Init handshake: write 0x00 to datetime, playback, command
        _LOGGER.debug("Sandsara: sending init handshake")
        await client.write_gatt_char(CHAR_DATETIME, bytes([0x00]), response=True)
        await client.write_gatt_char(CHAR_PLAYBACK, bytes([PB_INIT]), response=True)
        await client.write_gatt_char(CHAR_COMMAND, bytes([CMD_INIT]), response=True)

        # Sync datetime
        now = datetime.now().isoformat()
        await client.write_gatt_char(
            CHAR_DATETIME, b"\x04" + now.encode("ascii"), response=True
        )
        _LOGGER.debug("Sandsara: datetime synced: %s", now)

        await asyncio.sleep(0.5)

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
            "Sandsara initialized: model=%s firmware=%s",
            self.device_data.model,
            self.device_data.firmware,
        )

    @callback
    def _notification_handler(self, sender: int, data: bytearray) -> None:
        """Handle BLE notifications."""
        uuid_str = str(getattr(sender, "uuid", sender))
        short = uuid_str.split("-")[0] if "-" in uuid_str else uuid_str

        # Config blob from command characteristic
        if CHAR_COMMAND in uuid_str and len(data) > 10 and data[0] == 0x00:
            self.device_data.led_speed = data[1]
            self.device_data.ball_speed = data[2]
            self.device_data.brightness = data[5]
            self.device_data.is_playing = data[6] == 1
            _LOGGER.debug(
                "Sandsara config: led_speed=%d ball_speed=%d brightness=%d playing=%s",
                data[1],
                data[2],
                data[5],
                data[6] == 1,
            )

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

    # Public API

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

    async def async_sleep(self) -> None:
        """Put device to sleep."""
        _LOGGER.info("Sandsara: sleep")
        await self._write_playback(bytes([PB_SLEEP]))
        self.device_data.is_playing = False
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

    async def async_shutdown(self) -> None:
        """Disconnect from device."""
        _LOGGER.info("Sandsara: shutting down")
        if self._client and self._client.is_connected:
            await self._client.disconnect()
        self._client = None
        self._initialized = False

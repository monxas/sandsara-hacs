"""Constants for the Sandsara integration."""

DOMAIN = "sandsara"

# BLE Service UUIDs
SERVICE_MAIN = "fd31a2be-22e7-11eb-adc1-0242ac120002"
SERVICE_FILE_TRANSFER = "fd31abc4-22e7-11eb-adc1-0242ac120002"

# BLE Characteristic UUIDs — Main Service
CHAR_COMMAND = "e914c2c0-cde3-4939-adb2-ca61a3cc9b4e"
CHAR_PLAYBACK = "10b59496-bf86-44a8-ba7a-67d8e26a93eb"
CHAR_DATETIME = "0ecc71c5-20a8-462f-92d0-0618c5051cf0"
CHAR_MODEL = "caf74386-dd8b-4f54-9dd9-71c75f6d679a"
CHAR_VERSION = "7b204278-30c3-11eb-adc1-0242ac120002"
CHAR_STATUS = "9e23e02e-8921-4bf9-84f5-f58fa81c726e"
CHAR_SETTINGS = "20e01699-0346-45c7-91ae-3ebd8a16a2e6"
CHAR_POSITION = "9d277d03-0855-4d8c-8687-316ebca89a61"
CHAR_SENSOR = "eb940790-03f8-406d-bfc4-2f232cf65f84"

# BLE Characteristic UUIDs — File Transfer Service
CHAR_FILE_FLAG = "fcbff68e-2af1-11eb-adc1-0242ac120002"
CHAR_FILE_DATA = "fcbffa44-2af1-11eb-adc1-0242ac120002"
CHAR_FILE_UNKNOWN = "27566b01-59c3-4a6f-a40e-c35606b0a29b"
CHAR_FILE_STATUS = "250e79ac-f0d7-43cc-ad6a-63544b5c6663"

# Command bytes for CHAR_COMMAND
CMD_INIT = 0x00
CMD_LED_SPEED = 0x01
CMD_BALL_SPEED = 0x02
CMD_BRIGHTNESS = 0x05
CMD_LED_TOGGLE = 0x06
CMD_LED_COLOR = 0x07

# Playback commands for CHAR_PLAYBACK
PB_INIT = 0x00
PB_SELECT = 0x01
PB_SLEEP = 0x04
PB_PREV = 0x05
PB_NEXT = 0x06
PB_PLAY = 0x07
PB_PAUSE = 0x08
PB_SHUFFLE = 0x0D

# Playback notification sub-commands
PB_NOTIFY_STATE = 0x00
PB_NOTIFY_TRACK = 0x01
PB_NOTIFY_PROGRESS = 0x02
PB_NOTIFY_STATUS = 0x03
PB_NOTIFY_ACK = 0xFF
PB_NOTIFY_DONE = 0xFE

# Status codes
STATUS_CALIBRATING = "1"
STATUS_PLAYING = "2"
STATUS_PAUSED = "3"
STATUS_SLEEPING = "4"
STATUS_BUSY = "5"

# File transfer
FILE_CHUNK_SIZE = 512

# CHAR_DATETIME init blob offsets
DT_INIT_NAME_START = 1
DT_INIT_NAME_END = 32
DT_INIT_FILE_ARRAY_START = 62
DT_INIT_FILE_ARRAY_END = 163  # 101 bytes (indices 0-100)

# Pattern names by file index.
# Only include names that are verified from the Sandsara app.
# Unknown patterns use the fallback format "Track NNN".
PATTERN_NAMES: dict[int, str] = {}


def get_pattern_name(index: int) -> str:
    """Get human-readable pattern name for a file index."""
    return PATTERN_NAMES.get(index, f"Track {index:03d}")

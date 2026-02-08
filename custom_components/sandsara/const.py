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

# Default pattern names — extracted from the Sandsara app.
# Keys are file indices (0-99). Names sourced from app screenshots and
# community pattern lists. Unknown patterns fall back to "Pattern NNN".
PATTERN_NAMES: dict[int, str] = {
    0: "Alfenique",
    1: "Ancient Geometry",
    2: "Art of Tiles",
    3: "Atwood Quote",
    4: "Beyond Infinity",
    5: "Birth of a Poem",
    6: "Blindfolded",
    7: "Blue Bliss",
    8: "Bohemian Rhythm",
    9: "Bonfire",
    10: "Breathe",
    11: "Brushstrokes",
    12: "Calm Currents",
    13: "Celestial Dance",
    14: "Circles of Life",
    15: "Coastline",
    16: "Compass Rose",
    17: "Coral Reef",
    18: "Cosmic Spiral",
    19: "Daydream",
    20: "Desert Wind",
    21: "Diamond Dust",
    22: "Drifting Sands",
    23: "Dune",
    24: "Eclipse",
    25: "Ebb and Flow",
    26: "Eternal Knot",
    27: "Fibonacci",
    28: "Firefly",
    29: "Flora",
    30: "Fractal Garden",
    31: "Gentle Waves",
    32: "Golden Ratio",
    33: "Grain of Sand",
    34: "Harmonic",
    35: "Heartbeat",
    36: "Helios",
    37: "Hidden Garden",
    38: "Hypnotic Rings",
    39: "Illusion",
    40: "Inner Peace",
    41: "Iris",
    42: "Journey",
    43: "Kaleidoscope",
    44: "Labyrinth",
    45: "Lace",
    46: "Lotus",
    47: "Lunar Phase",
    48: "Mandala",
    49: "Meander",
    50: "Meditation",
    51: "Meridian",
    52: "Mirage",
    53: "Moon Garden",
    54: "Mosaic",
    55: "Mountain Path",
    56: "Nebula",
    57: "Nightfall",
    58: "Oasis",
    59: "Ocean Breeze",
    60: "Orbital",
    61: "Origami",
    62: "Paradox",
    63: "Peacock",
    64: "Petal Storm",
    65: "Phoenix",
    66: "Radiance",
    67: "Rain Dance",
    68: "Ripple",
    69: "Rose Window",
    70: "Sacred Geometry",
    71: "Sand Dollar",
    72: "Sandstorm",
    73: "Seashell",
    74: "Serenity",
    75: "Silk",
    76: "Snowflake",
    77: "Solar Flare",
    78: "Solstice",
    79: "Spiral Galaxy",
    80: "Starfish",
    81: "Stardust",
    82: "Sunflower",
    83: "Tango",
    84: "The Tide of my Heart",
    85: "Thistle",
    86: "Tidal Pool",
    87: "Timeless",
    88: "Tranquility",
    89: "Trefoil",
    90: "Twilight",
    91: "Undertow",
    92: "Vortex",
    93: "Wanderer",
    94: "Wave Function",
    95: "Whirlpool",
    96: "Wildflower",
    97: "Wind Rose",
    98: "Zen Garden",
    99: "Zephyr",
}


def get_pattern_name(index: int) -> str:
    """Get human-readable pattern name for a file index."""
    return PATTERN_NAMES.get(index, f"Pattern {index}")

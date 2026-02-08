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
# NOTE: Index-to-name mapping is approximate. The app displays patterns
# alphabetically but track indices on the device may differ.
# These 6 names were extracted from app screenshots (2026-02-08).
# Full list requires scrolling through all ~100 patterns in the app.
PATTERN_NAMES: dict[int, str] = {
    0: "Alfenique",
    1: "Ancient Geometry",
    2: "Art of Tiles",
    3: "Atwood Quote",
    4: "Beyond Infinity",
    5: "Birth of a Poem",
    6: "Birth of a Thought",
    7: "Blooming Drop",
    8: "Cactus in Sand",
    9: "Chaotic Sun",
    10: "Collapsed Mountains",
    11: "Compass Rose",
    12: "Concentric Springs",
    13: "Conical Flower",
    14: "Conspiracy Eye",
    15: "Dandelion",
    16: "Dantes Vision",
    17: "Deep Clarity",
    18: "Deep Waters",
    19: "Deeper Into Your Eyes",
    20: "Desert Flows",
    21: "Dramatic Star",
    22: "Dune in the Sahara",
    23: "Drops in the Lake",
    24: "Dream of a Bee",
    25: "Eagle Plumage",
    26: "Endless Symetry",
    27: "Event Horizon",
    28: "Fling Bumerang",
    29: "Flower Bubbles",
    30: "Flower for You",
    31: "Fractal Trident",
    32: "Full Moon in The Valley",
    33: "Golden Spin",
    34: "Infinity Wave",
    35: "Intersections in the Mind",
    36: "Koch Cube Flowers",
    37: "Magic Library",
    38: "Magnificent Spiral",
    39: "Lily Lake",
    40: "Mechanical Marvel",
    41: "Mirror Tree",
    42: "Multi-Triangel",
    43: "Omega Frame",
    44: "Perlin Rings",
    45: "Reuleaux Swirl",
    46: "Pyramidal Balance",
    47: "Rhodonea",
    48: "Sand Propeller",
    49: "See You in The Other Side",
    50: "Shining Cross",
    51: "Simple Fractal",
    52: "Solar Turbine",
    53: "Solar Waves",
    54: "Solomonic Columns",
    55: "Sound on Sand",
    56: "Spinning Star",
    57: "Spiral Dune",
    58: "Spiral Symetry",
    59: "Star Dust",
    60: "Starry Night",
    61: "SuperNova",
    62: "Swallows Taking Flight",
    63: "Swirl-Overlay",
    64: "Symmetric Fields",
    65: "Tasting Flight",
    66: "That Place in the Sand",
    67: "The 4 Pillars of the Universe",
    68: "The Art We Remember",
    69: "The Clover Mandala",
    70: "The Desert Times",
    71: "The Dome of Tranquility",
    72: "The Farthest Summit",
    73: "The Home of Venus",
    74: "The More You See",
    75: "The Purest Spiral",
    76: "The Ring Inside a Ring",
    77: "The Rock and The Bubble",
    78: "The Single Drop",
    79: "The Sphere That Became a Flower",
    80: "The Subtle Dunes of Your Hair",
    81: "The Tide of my Heart",
    82: "The Wind in the Pinwheel",
    83: "Topomadnes",
    84: "Tranquility Web",
    85: "Tree in the Lake",
    86: "Triangular Madness",
    87: "Trifractal",
    88: "Turbulent Explosion",
    89: "Uncalm Eye",
    90: "Untouch Flower",
    91: "Valleys and Mountains",
    92: "Vibrant Cycloid",
    93: "Vision of a Storm",
    94: "Wagara",
    95: "Ways to Unknow",
    96: "Wave to the Distance",
    97: "Wiggly Spiral",
    98: "Window to Imagination",
    99: "Yin-Yang",
}


def get_pattern_name(index: int) -> str:
    """Get human-readable pattern name for a file index."""
    return PATTERN_NAMES.get(index, f"Track {index:03d}")

"""Constants for Tile BLE."""

from enum import IntEnum

TILE_SERVICE_UUID = "0000feed-0000-1000-8000-00805f9b34fb"
TOA_CMD_CHAR_UUID = "9d410018-35d6-f4dd-ba60-e7bd8dc491c0"
TOA_RSP_CHAR_UUID = "9d410019-35d6-f4dd-ba60-e7bd8dc491c0"
# Only Tiles that use a Private ID have this characteristic.
TILE_ID_CHAR_UUID = "9d410007-35d6-f4dd-ba60-e7bd8dc491c0"

CONNECTIONLESS_CID = 0
AUTH_KEY_LEN = 16
SESSION_KEY_LEN = 16
TOKEN_LEN = 4
RAND_A_LEN = 14
RAND_T_LEN = 13
MIC_LEN = 4
TILE_ID_LEN = 8

# Maximum payload size the client announces in its READY command.
CLIENT_MPS = 0x13

TILE_SONG_FIND = 0x01

# Bit in the TDI AVAILABLE response that is set when the Tile can send its Tile ID.
TDI_TILE_ID_AVAILABLE = 0x01

RESPONSE_TIMEOUT = 10.0


class ToaCommand(IntEnum):
    """Commands sent by the client."""

    SONG = 0x05
    OPEN_CHANNEL = 0x10
    CLOSE_CHANNEL = 0x11
    READY = 0x12
    TDI = 0x13
    AUTHENTICATE = 0x14


class ToaResponse(IntEnum):
    """Responses sent by the Tile."""

    READY = 0x01
    ERROR = 0x05
    SONG = 0x07
    OPEN_CHANNEL = 0x12
    CLOSE_CHANNEL = 0x13
    TDI = 0x14
    AUTHENTICATE = 0x15


class SongCommand(IntEnum):
    """Song sub-commands."""

    PLAY = 0x02


class SongResponse(IntEnum):
    """Song sub-responses."""

    PLAY_OK = 0x02
    ERROR = 0x20


class TdiCommand(IntEnum):
    """Tile Data Information sub-commands."""

    AVAILABLE = 0x01
    TILE_ID = 0x02


class TdiResponse(IntEnum):
    """Tile Data Information sub-responses."""

    ERROR = 0x20


class CloseReason(IntEnum):
    """Reasons the Tile gives for closing a channel."""

    NO_ERROR = 0x00
    MIC_FAILURE = 0x01
    TKA_MISSING = 0x02
    BROADCAST_MIC_FAILURE = 0x03


class TileVolume(IntEnum):
    """Volume used when ringing a Tile."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3

"""Constants for tests."""

import base64

TILE_ADDRESS = "AA:BB:CC:DD:EE:FF"
AUTH_KEY = bytes(range(16))
AUTH_KEY_B64 = base64.b64encode(AUTH_KEY).decode()
TOKEN = b"\x01\x02\x03\x04"
TILE_ID = bytes.fromhex("5176aabbccdd0102")

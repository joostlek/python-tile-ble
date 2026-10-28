"""Tile Over-the-Air (TOA) protocol, used to talk to a Tile over Bluetooth.

The protocol is undocumented; this follows node-tile
(https://github.com/lesleyxyz/node-tile, MIT, Copyright (c) 2024 Lesley De Keyser).
"""

import base64
import binascii
from dataclasses import dataclass
import hashlib
import hmac

from tile_ble.const import (
    AUTH_KEY_LEN,
    CONNECTIONLESS_CID,
    MIC_LEN,
    SESSION_KEY_LEN,
    TILE_ID_LEN,
    TdiResponse,
)
from tile_ble.exceptions import TileBleError

_HMAC_INPUT_LEN = 32


@dataclass(frozen=True, slots=True)
class ToaMessage:
    """A response received from the Tile."""

    code: int
    payload: bytes


def _hmac_sha256(key: bytes, *parts: bytes) -> bytes:
    """Return HMAC-SHA256 over the parts, zero-padded or truncated to 32 bytes."""
    data = b"".join(parts)[:_HMAC_INPUT_LEN].ljust(_HMAC_INPUT_LEN, b"\x00")
    return hmac.new(key, data, hashlib.sha256).digest()


def decode_auth_key(auth_key: str) -> bytes:
    """Decode the base64 auth key provided by the Tile cloud API."""
    try:
        key = base64.b64decode(auth_key, validate=True)
    except binascii.Error as err:
        msg = "Auth key is not valid base64"
        raise ValueError(msg) from err
    if len(key) != AUTH_KEY_LEN:
        msg = f"Auth key must be {AUTH_KEY_LEN} bytes, got {len(key)}"
        raise ValueError(msg)
    return key


def compute_sres(auth_key: bytes, rand_a: bytes, rand_t: bytes) -> bytes:
    """Return the SRES the Tile sends in its AUTHENTICATE response."""
    data = rand_a.ljust(16, b"\x00") + rand_t.ljust(16, b"\x00")
    return hmac.new(auth_key, data, hashlib.sha256).digest()[4:8]


def derive_session_key(
    auth_key: bytes, rand_a: bytes, rand_t: bytes, cid: int, token: bytes
) -> bytes:
    """Derive the key used to sign messages on an open channel."""
    return _hmac_sha256(auth_key, rand_a, rand_t, bytes([cid]), token)[:SESSION_KEY_LEN]


def compute_mic(session_key: bytes, nonce: int, message: bytes) -> bytes:
    """Return the message integrity code for a channel message."""
    return _hmac_sha256(
        session_key,
        nonce.to_bytes(8, "little"),
        bytes([0x01, len(message)]),
        message,
    )[:MIC_LEN]


def build_connectionless_frame(token: bytes, command: int, payload: bytes) -> bytes:
    """Build a frame for the connectionless channel."""
    return bytes([CONNECTIONLESS_CID]) + token + bytes([command]) + payload


def build_channel_frame(
    cid: int, session_key: bytes, nonce: int, message: bytes
) -> bytes:
    """Build a signed frame for an open channel."""
    return bytes([cid]) + message + compute_mic(session_key, nonce, message)


def parse_connectionless_frame(data: bytes, token: bytes) -> ToaMessage | None:
    """Parse a connectionless response addressed to this client."""
    if len(data) < 6 or data[0] != CONNECTIONLESS_CID or data[1:5] != token:
        return None
    return ToaMessage(data[5], data[6:])


def parse_channel_frame(data: bytes, cid: int) -> ToaMessage | None:
    """Parse a response on an open channel.

    The trailing MIC is stripped but not verified, as the Tile's signing scheme
    for responses is not documented.
    """
    if len(data) < 2 + MIC_LEN or data[0] != cid:
        return None
    return ToaMessage(data[1], data[2:-MIC_LEN])


def parse_tdi_response(message: ToaMessage) -> bytes:
    """Return the data of a TDI response, without its sub-response code."""
    if not message.payload or message.payload[0] == TdiResponse.ERROR:
        msg = f"The Tile returned a TDI error: {message.payload.hex()}"
        raise TileBleError(msg)
    return message.payload[1:]


def parse_tile_id(data: bytes) -> str:
    """Return the Tile ID sent by the Tile as hex."""
    if len(data) != TILE_ID_LEN:
        msg = f"The Tile sent an invalid Tile ID: {data.hex()}"
        raise TileBleError(msg)
    return data.hex()


def address_matches_tile_id(address: str, tile_id: str) -> bool:
    """Return whether a Bluetooth address belongs to the Tile with this Tile ID.

    Older Tiles use the first 6 bytes of their Tile ID as address. Tiles with a
    Private ID set the two highest bits of the first byte, as Bluetooth requires
    for a static random address. That rule is inferred from two Tiles only:
    Tile ID 5176… uses D1:76…, and Tile ID b9b4… uses F9:B4….
    """
    try:
        mac = bytes.fromhex(address.replace(":", ""))
        tile = bytes.fromhex(tile_id)
    except ValueError:
        return False
    if len(mac) != 6 or len(tile) != TILE_ID_LEN:
        return False
    prefix = tile[:6]
    return mac in (prefix, bytes([prefix[0] | 0xC0]) + prefix[1:])

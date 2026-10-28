"""Tests for the Tile Over-the-Air protocol."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

import pytest

from tile_ble.exceptions import TileBleError
from tile_ble.protocol import (
    ToaMessage,
    address_matches_tile_id,
    build_channel_frame,
    build_connectionless_frame,
    compute_mic,
    compute_sres,
    decode_auth_key,
    derive_session_key,
    parse_channel_frame,
    parse_connectionless_frame,
    parse_tdi_response,
    parse_tile_id,
)

from .const import AUTH_KEY, TILE_ID, TOKEN

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion


def test_decode_auth_key() -> None:
    """Test decoding a base64 auth key."""
    assert decode_auth_key(base64.b64encode(AUTH_KEY).decode()) == AUTH_KEY


@pytest.mark.parametrize(
    "auth_key",
    [
        pytest.param("not base64!", id="invalid_base64"),
        pytest.param(base64.b64encode(b"short").decode(), id="wrong_length"),
    ],
)
def test_decode_auth_key_invalid(auth_key: str) -> None:
    """Test invalid auth keys are rejected."""
    with pytest.raises(ValueError, match="Auth key"):
        decode_auth_key(auth_key)


def test_session_key_and_mic_are_deterministic() -> None:
    """Test the session key and MIC depend on all their inputs."""
    rand_a, rand_t = b"\xaa" * 14, b"\xbb" * 13
    session_key = derive_session_key(AUTH_KEY, rand_a, rand_t, 3, TOKEN)
    assert len(session_key) == 16
    assert session_key == derive_session_key(AUTH_KEY, rand_a, rand_t, 3, TOKEN)
    assert session_key != derive_session_key(AUTH_KEY, rand_a, rand_t, 4, TOKEN)

    mic = compute_mic(session_key, 1, b"\x12\x13")
    assert len(mic) == 4
    assert mic != compute_mic(session_key, 2, b"\x12\x13")


def test_crypto_known_answers(snapshot: SnapshotAssertion) -> None:
    """Test the SRES, session key and MIC for fixed inputs."""
    rand_a, rand_t = b"\xaa" * 14, b"\xbb" * 13
    session_key = derive_session_key(AUTH_KEY, rand_a, rand_t, 3, TOKEN)
    assert {
        "sres": compute_sres(AUTH_KEY, rand_a, rand_t[:10]),
        "session_key": session_key,
        "mic": compute_mic(session_key, 1, b"\x12\x13"),
    } == snapshot


def test_frames() -> None:
    """Test building frames."""
    assert build_connectionless_frame(TOKEN, 0x10, b"\xaa") == (
        b"\x00" + TOKEN + b"\x10\xaa"
    )
    session_key = bytes(16)
    frame = build_channel_frame(3, session_key, 1, b"\x12\x13")
    assert frame == b"\x03\x12\x13" + compute_mic(session_key, 1, b"\x12\x13")


def test_parse_connectionless_frame() -> None:
    """Test parsing connectionless responses."""
    frame = b"\x00" + TOKEN + b"\x15\xaa\xbb"
    assert parse_connectionless_frame(frame, TOKEN) == ToaMessage(0x15, b"\xaa\xbb")
    assert parse_connectionless_frame(frame, b"\x09\x09\x09\x09") is None
    assert parse_connectionless_frame(b"\x00" + TOKEN, TOKEN) is None


def test_parse_channel_frame() -> None:
    """Test parsing channel responses strips the MIC."""
    frame = b"\x03\x07\x02" + b"\xff" * 4
    assert parse_channel_frame(frame, 3) == ToaMessage(0x07, b"\x02")
    assert parse_channel_frame(frame, 4) is None
    assert parse_channel_frame(b"\x03\x07", 3) is None


def test_parse_tdi_response() -> None:
    """Test the TDI sub-response code is stripped."""
    assert parse_tdi_response(ToaMessage(0x14, b"\x02" + TILE_ID)) == TILE_ID


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(b"", id="empty"),
        pytest.param(b"\x20\x01", id="error"),
    ],
)
def test_parse_tdi_response_error(payload: bytes) -> None:
    """Test TDI errors are raised."""
    with pytest.raises(TileBleError, match="TDI error"):
        parse_tdi_response(ToaMessage(0x14, payload))


def test_parse_tile_id() -> None:
    """Test the Tile ID is returned as hex."""
    assert parse_tile_id(TILE_ID) == "5176aabbccdd0102"


def test_parse_tile_id_invalid() -> None:
    """Test a Tile ID with the wrong length is rejected."""
    with pytest.raises(TileBleError, match="invalid Tile ID"):
        parse_tile_id(TILE_ID[:6])


@pytest.mark.parametrize(
    ("address", "tile_id", "matches"),
    [
        pytest.param("51:76:AA:BB:CC:DD", "5176aabbccdd0102", True, id="older_tile"),
        pytest.param("D1:76:AA:BB:CC:DD", "5176aabbccdd0102", True, id="private_id"),
        pytest.param(
            "F9:B4:AA:BB:CC:DD", "b9b4aabbccdd0102", True, id="private_id_b9b4"
        ),
        pytest.param("d1:76:aa:bb:cc:dd", "5176AABBCCDD0102", True, id="case"),
        pytest.param("D1:76:AA:BB:CC:DE", "5176aabbccdd0102", False, id="other_tile"),
        pytest.param("91:76:AA:BB:CC:DD", "5176aabbccdd0102", False, id="other_bits"),
        pytest.param("D1:76:AA:BB:CC:DD", "p!5176aabbccdd01", False, id="phone"),
        pytest.param("D1:76:AA:BB:CC:DD", "5176aabbccdd", False, id="short_tile_id"),
        pytest.param("D1:76:AA:BB:CC", "5176aabbccdd0102", False, id="short_address"),
    ],
)
def test_address_matches_tile_id(address: str, tile_id: str, *, matches: bool) -> None:
    """Test matching a Bluetooth address to a Tile ID."""
    assert address_matches_tile_id(address, tile_id) is matches

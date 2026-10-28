"""Tests for talking to a Tile over Bluetooth."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

from bleak.exc import BleakError
import pytest

from tile_ble import (
    TileBleAuthenticationError,
    TileBleConnectionError,
    TileBleDevice,
    TileBleError,
    TileVolume,
    async_read_tile_id,
)

from .const import AUTH_KEY, AUTH_KEY_B64
from .fake_tile import FakeBleakClient, FakeTile

if TYPE_CHECKING:
    from collections.abc import Iterator

    from bleak.backends.device import BLEDevice


@contextmanager
def _connect_to(client: FakeBleakClient) -> Iterator[None]:
    with patch("tile_ble.device.establish_connection", AsyncMock(return_value=client)):
        yield


@pytest.mark.parametrize(
    ("volume", "song"),
    [
        pytest.param(TileVolume.HIGH, b"\x02\x01\x03", id="high"),
        pytest.param(TileVolume.LOW, b"\x02\x01\x01", id="low"),
    ],
)
async def test_ring(ble_device: BLEDevice, volume: TileVolume, song: bytes) -> None:
    """Test ringing plays the find song and cleans up."""
    tile = FakeTile(AUTH_KEY)
    client = FakeBleakClient(tile)
    with _connect_to(client):
        await TileBleDevice(ble_device, AUTH_KEY_B64).async_ring(volume)

    assert tile.songs == [song]
    assert tile.closed_by_client
    assert client.disconnected


async def test_ignores_other_frames(ble_device: BLEDevice) -> None:
    """Test frames addressed to other clients are ignored."""
    tile = FakeTile(AUTH_KEY, send_noise=True)
    with _connect_to(FakeBleakClient(tile)):
        await TileBleDevice(ble_device, AUTH_KEY_B64).async_ring()

    assert tile.songs == [b"\x02\x01\x03"]


async def test_authenticate(ble_device: BLEDevice) -> None:
    """Test authenticating does not ring."""
    tile = FakeTile(AUTH_KEY)
    client = FakeBleakClient(tile)
    with _connect_to(client):
        await TileBleDevice(ble_device, AUTH_KEY_B64).async_authenticate()

    assert not tile.songs
    assert tile.closed_by_client
    assert client.disconnected


async def test_wrong_key(ble_device: BLEDevice) -> None:
    """Test a key that belongs to another Tile is rejected."""
    tile = FakeTile(bytes(16))
    client = FakeBleakClient(tile)
    with _connect_to(client), pytest.raises(TileBleAuthenticationError):
        await TileBleDevice(ble_device, AUTH_KEY_B64).async_ring()

    assert not tile.songs
    assert not tile.closed_by_client
    assert client.disconnected


@pytest.mark.parametrize(
    ("tile_kwargs", "match"),
    [
        pytest.param({"song_response": 0x20}, "refused to ring", id="refused"),
        pytest.param({"song_error": True}, "returned an error", id="error_response"),
        pytest.param(
            {"truncate_open_channel": True},
            "invalid OPEN_CHANNEL",
            id="invalid_open_channel",
        ),
    ],
)
async def test_ring_tile_error(
    ble_device: BLEDevice, tile_kwargs: dict[str, Any], match: str
) -> None:
    """Test the Tile refusing to ring or returning an error."""
    client = FakeBleakClient(FakeTile(AUTH_KEY, **tile_kwargs))
    with _connect_to(client), pytest.raises(TileBleError, match=match):
        await TileBleDevice(ble_device, AUTH_KEY_B64).async_ring()
    assert client.disconnected


async def test_no_response(ble_device: BLEDevice) -> None:
    """Test a Tile that does not respond."""
    client = FakeBleakClient(FakeTile(AUTH_KEY, respond=False))
    with (
        patch("tile_ble.device.RESPONSE_TIMEOUT", 0.01),
        _connect_to(client),
        pytest.raises(TileBleConnectionError, match="Timed out"),
    ):
        await TileBleDevice(ble_device, AUTH_KEY_B64).async_ring()
    assert client.disconnected


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(BleakError("out of range"), id="bleak_error"),
        pytest.param(TimeoutError, id="timeout"),
    ],
)
async def test_connect_fails(
    ble_device: BLEDevice, side_effect: type[Exception] | Exception
) -> None:
    """Test the Tile cannot be connected to."""
    with (
        patch(
            "tile_ble.device.establish_connection",
            AsyncMock(side_effect=side_effect),
        ),
        pytest.raises(TileBleConnectionError, match="Could not connect"),
    ):
        await TileBleDevice(ble_device, AUTH_KEY_B64).async_ring()


async def test_notify_fails(ble_device: BLEDevice) -> None:
    """Test enabling notifications failing."""
    client = FakeBleakClient(FakeTile(AUTH_KEY))
    client.start_notify = AsyncMock(side_effect=BleakError("CCCD"))  # type: ignore[method-assign]
    with (
        _connect_to(client),
        pytest.raises(TileBleConnectionError, match="Could not communicate"),
    ):
        await TileBleDevice(ble_device, AUTH_KEY_B64).async_ring()
    assert client.disconnected


def test_invalid_auth_key(ble_device: BLEDevice) -> None:
    """Test an invalid auth key is rejected up front."""
    with pytest.raises(ValueError, match="Auth key"):
        TileBleDevice(ble_device, "invalid")


@pytest.mark.parametrize(
    ("private_id", "notifications"),
    [
        pytest.param(True, False, id="characteristic"),
        pytest.param(False, True, id="tdi"),
    ],
)
async def test_read_tile_id(
    ble_device: BLEDevice, *, private_id: bool, notifications: bool
) -> None:
    """Test reading the Tile ID from the characteristic or with TDI."""
    tile = FakeTile(AUTH_KEY, private_id=private_id)
    client = FakeBleakClient(tile)
    with _connect_to(client):
        assert await async_read_tile_id(ble_device) == "5176aabbccdd0102"

    assert (client.callback is not None) is notifications
    assert not tile.closed_by_client
    assert client.disconnected


@pytest.mark.parametrize(
    ("tile_kwargs", "match"),
    [
        pytest.param({"tdi_error": True}, "TDI error", id="tdi_error"),
        pytest.param({"tdi_available": 0x0E}, "does not provide", id="no_tile_id"),
        pytest.param({"tile_id": b"\x01\x02"}, "invalid Tile ID", id="tdi_short"),
        pytest.param(
            {"tile_id": b"\x01\x02", "private_id": True},
            "invalid Tile ID",
            id="characteristic_short",
        ),
    ],
)
async def test_read_tile_id_error(
    ble_device: BLEDevice, tile_kwargs: dict[str, Any], match: str
) -> None:
    """Test the Tile not sending a valid Tile ID."""
    client = FakeBleakClient(FakeTile(AUTH_KEY, **tile_kwargs))
    with _connect_to(client), pytest.raises(TileBleError, match=match):
        await async_read_tile_id(ble_device)
    assert client.disconnected

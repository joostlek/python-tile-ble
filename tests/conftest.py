"""Asynchronous Python client for Tile trackers over Bluetooth."""

from bleak.backends.device import BLEDevice
import pytest

from .const import TILE_ADDRESS


@pytest.fixture
def ble_device() -> BLEDevice:
    """Return the Tile's BLEDevice."""
    return BLEDevice(TILE_ADDRESS, "Tile", None)

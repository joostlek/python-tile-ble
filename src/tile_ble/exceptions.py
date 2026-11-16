"""Asynchronous Python client for Tile trackers over Bluetooth."""


class TileBleError(Exception):
    """Base exception for talking to a Tile over Bluetooth."""


class TileBleConnectionError(TileBleError):
    """Raised when the Tile cannot be reached or does not respond."""


class TileBleAuthenticationError(TileBleError):
    """Raised when the Tile rejects the auth key."""


class TileCloudError(TileBleError):
    """Raised when a Tile cloud request fails."""


class TileCloudAuthenticationError(TileCloudError):
    """Raised when the Tile cloud rejects the credentials."""

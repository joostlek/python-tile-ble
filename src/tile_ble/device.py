"""Asynchronous Python client for Tile trackers over Bluetooth."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
import logging
import os
from typing import TYPE_CHECKING

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

from tile_ble.const import (
    CLIENT_MPS,
    CONNECTIONLESS_CID,
    RAND_A_LEN,
    RAND_T_LEN,
    RESPONSE_TIMEOUT,
    TDI_TILE_ID_AVAILABLE,
    TILE_ID_CHAR_UUID,
    TILE_SONG_FIND,
    TOA_CMD_CHAR_UUID,
    TOA_RSP_CHAR_UUID,
    TOKEN_LEN,
    CloseReason,
    SongCommand,
    SongResponse,
    TdiCommand,
    TileVolume,
    ToaCommand,
    ToaResponse,
)
from tile_ble.exceptions import (
    TileBleAuthenticationError,
    TileBleConnectionError,
    TileBleError,
)
from tile_ble.protocol import (
    ToaMessage,
    build_channel_frame,
    build_connectionless_frame,
    compute_sres,
    decode_auth_key,
    derive_session_key,
    parse_channel_frame,
    parse_connectionless_frame,
    parse_tdi_response,
    parse_tile_id,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from bleak.backends.characteristic import BleakGATTCharacteristic
    from bleak.backends.device import BLEDevice

_LOGGER = logging.getLogger(__package__)


class _Channel:
    """A TOA channel on a connected Tile.

    Until a channel is open, the client talks on the connectionless CID.
    """

    def __init__(self, client: BleakClient) -> None:
        self._client = client
        self._token = os.urandom(TOKEN_LEN)
        self._cid = CONNECTIONLESS_CID
        self._session_key = b""
        self._nonce = 0
        self._closed = False
        self._waiters: dict[int, asyncio.Future[ToaMessage]] = {}

    def handle_notification(
        self, _characteristic: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Dispatch a response from the Tile to the request waiting for it."""
        frame = bytes(data)
        if self._cid == CONNECTIONLESS_CID:
            message = parse_connectionless_frame(frame, self._token)
        else:
            message = parse_channel_frame(frame, self._cid)
        if message is None:
            return

        if message.code == ToaResponse.CLOSE_CHANNEL:
            self._closed = True
            reason = message.payload[0] if message.payload else None
            if reason == CloseReason.MIC_FAILURE:
                self._fail_waiters(
                    TileBleAuthenticationError("The Tile rejected the auth key")
                )
            else:
                self._fail_waiters(
                    TileBleError(f"The Tile closed the channel: {reason}")
                )
            return
        if message.code == ToaResponse.ERROR:
            self._fail_waiters(
                TileBleError(f"The Tile returned an error: {message.payload.hex()}")
            )
            return

        if (waiter := self._waiters.pop(message.code, None)) and not waiter.done():
            waiter.set_result(message)

    def _fail_waiters(self, err: TileBleError) -> None:
        for waiter in self._waiters.values():
            if not waiter.done():
                waiter.set_exception(err)
        self._waiters.clear()

    async def _send(self, frame: bytes, response: ToaResponse) -> ToaMessage:
        waiter: asyncio.Future[ToaMessage] = asyncio.get_running_loop().create_future()
        self._waiters[response] = waiter
        try:
            await self._client.write_gatt_char(TOA_CMD_CHAR_UUID, frame, response=False)
            async with asyncio.timeout(RESPONSE_TIMEOUT):
                return await waiter
        except TimeoutError as err:
            msg = f"Timed out waiting for {response.name} from the Tile"
            raise TileBleConnectionError(msg) from err
        finally:
            self._waiters.pop(response, None)

    async def _send_connectionless(
        self, command: ToaCommand, payload: bytes, response: ToaResponse
    ) -> ToaMessage:
        frame = build_connectionless_frame(self._token, command, payload)
        return await self._send(frame, response)

    async def request(self, message: bytes, response: ToaResponse) -> ToaMessage:
        """Send a signed message on the channel and wait for the response."""
        self._nonce += 1
        frame = build_channel_frame(self._cid, self._session_key, self._nonce, message)
        return await self._send(frame, response)

    async def open(self, auth_key: bytes) -> None:
        """Authenticate and open a channel."""
        rand_a = os.urandom(RAND_A_LEN)
        authenticated = await self._send_connectionless(
            ToaCommand.AUTHENTICATE, rand_a, ToaResponse.AUTHENTICATE
        )
        rand_t, sres = authenticated.payload[:10], authenticated.payload[10:14]
        # Only logged: the channel handshake below is what proves the key.
        _LOGGER.debug(
            "Tile SRES %s the auth key",
            "matches"
            if sres == compute_sres(auth_key, rand_a, rand_t)
            else "does not match",
        )

        opened = await self._send_connectionless(
            ToaCommand.OPEN_CHANNEL, rand_a, ToaResponse.OPEN_CHANNEL
        )
        if len(opened.payload) < 1 + RAND_T_LEN:
            msg = "The Tile sent an invalid OPEN_CHANNEL response"
            raise TileBleError(msg)
        cid = opened.payload[0]
        self._session_key = derive_session_key(
            auth_key, rand_a, opened.payload[1 : 1 + RAND_T_LEN], cid, self._token
        )
        self._cid = cid
        await self.request(bytes([ToaCommand.READY, CLIENT_MPS]), ToaResponse.READY)

    async def read_tile_id(self) -> str:
        """Request the Tile ID with connectionless TDI commands."""
        available = parse_tdi_response(
            await self._send_connectionless(
                ToaCommand.TDI, bytes([TdiCommand.AVAILABLE]), ToaResponse.TDI
            )
        )
        if not available or not available[0] & TDI_TILE_ID_AVAILABLE:
            msg = "The Tile does not provide its Tile ID"
            raise TileBleError(msg)
        tile_id = parse_tdi_response(
            await self._send_connectionless(
                ToaCommand.TDI, bytes([TdiCommand.TILE_ID]), ToaResponse.TDI
            )
        )
        return parse_tile_id(tile_id)

    async def close(self) -> None:
        """Close the channel if it is still open."""
        if self._cid == CONNECTIONLESS_CID or self._closed:
            return
        self._closed = True
        self._nonce += 1
        frame = build_channel_frame(
            self._cid,
            self._session_key,
            self._nonce,
            bytes([ToaCommand.CLOSE_CHANNEL, CloseReason.NO_ERROR]),
        )
        await self._client.write_gatt_char(TOA_CMD_CHAR_UUID, frame, response=False)


@asynccontextmanager
async def _connect(ble_device: BLEDevice) -> AsyncIterator[BleakClient]:
    """Connect to the Tile and raise Bluetooth errors as TileBleConnectionError."""
    try:
        client = await establish_connection(
            BleakClient, ble_device, ble_device.name or ble_device.address
        )
    except (BleakError, TimeoutError) as err:
        msg = f"Could not connect to the Tile: {err}"
        raise TileBleConnectionError(msg) from err

    try:
        yield client
    except BleakError as err:
        msg = f"Could not communicate with the Tile: {err}"
        raise TileBleConnectionError(msg) from err
    finally:
        with suppress(BleakError):
            await client.disconnect()


@asynccontextmanager
async def _listen(client: BleakClient) -> AsyncIterator[_Channel]:
    """Receive TOA responses on a channel, and close the channel on exit."""
    channel = _Channel(client)
    try:
        await client.start_notify(TOA_RSP_CHAR_UUID, channel.handle_notification)
        yield channel
    finally:
        with suppress(BleakError):
            await channel.close()


class TileBleDevice:
    """A Tile that can be reached over Bluetooth."""

    def __init__(self, ble_device: BLEDevice, auth_key: str) -> None:
        """Initialize the device with the base64 auth key from the Tile cloud."""
        self._ble_device = ble_device
        self._auth_key = decode_auth_key(auth_key)

    @asynccontextmanager
    async def _channel(self) -> AsyncIterator[_Channel]:
        async with _connect(self._ble_device) as client, _listen(client) as channel:
            await channel.open(self._auth_key)
            yield channel

    async def async_authenticate(self) -> None:
        """Check that the auth key belongs to this Tile."""
        async with self._channel():
            pass

    async def async_ring(self, volume: TileVolume = TileVolume.HIGH) -> None:
        """Make the Tile play its find song."""
        async with self._channel() as channel:
            response = await channel.request(
                bytes([ToaCommand.SONG, SongCommand.PLAY, TILE_SONG_FIND, volume]),
                ToaResponse.SONG,
            )
        if response.payload[:1] != bytes([SongResponse.PLAY_OK]):
            msg = f"The Tile refused to ring: {response.payload.hex()}"
            raise TileBleError(msg)


async def async_read_tile_id(ble_device: BLEDevice) -> str:
    """Return the Tile ID of a Tile as hex. This does not need an auth key."""
    async with _connect(ble_device) as client:
        if characteristic := client.services.get_characteristic(TILE_ID_CHAR_UUID):
            return parse_tile_id(bytes(await client.read_gatt_char(characteristic)))
        async with _listen(client) as channel:
            return await channel.read_tile_id()

"""Tests for fetching auth keys from the Tile cloud."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer
import pytest

from tile_ble import (
    TileCloudAuthenticationError,
    TileCloudError,
    TileCloudTile,
    async_get_tiles,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

AUTH_KEY = "AAECAwQFBgcICQoLDA0ODw=="


def _ok(result: object) -> web.Response:
    return web.json_response({"result": result})


async def _client(_: web.Request) -> web.Response:
    return _ok({})


async def _session(request: web.Request) -> web.Response:
    if (await request.post())["password"] != "secret":
        raise web.HTTPUnauthorized
    return _ok({})


async def _details(request: web.Request) -> web.Response:
    tile_id = request.match_info["tile_id"]
    if tile_id == "19264d2dffdbca32":
        return _ok({"tile_uuid": tile_id, "name": "Wallet", "auth_key": AUTH_KEY})
    if tile_id == "aaaaaaaaaaaaaaaa":
        return _ok({"tile_uuid": tile_id, "name": "Keys"})
    if tile_id == "bbbbbbbbbbbbbbbb":
        raise web.HTTPPreconditionFailed
    raise web.HTTPInternalServerError


@pytest.fixture(name="tile_ids")
def tile_ids_fixture() -> list[str]:
    """Return the Tile IDs the fake Tile cloud lists."""
    return ["19264d2dffdbca32", "aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb"]


@pytest.fixture(name="session")
async def session_fixture(
    monkeypatch: pytest.MonkeyPatch, tile_ids: list[str]
) -> AsyncIterator[ClientSession]:
    """Return a session pointed at a fake Tile cloud."""

    async def _states(_: web.Request) -> web.Response:
        return _ok([{"tile_id": tile_id} for tile_id in tile_ids])

    app = web.Application()
    app.router.add_put("/clients/{client_uuid}", _client)
    app.router.add_post("/clients/{client_uuid}/sessions", _session)
    app.router.add_get("/tiles/tile_states", _states)
    app.router.add_get("/tiles/{tile_id}", _details)
    async with TestServer(app) as server, ClientSession() as client_session:
        monkeypatch.setattr(
            "tile_ble.cloud.API_URL", str(server.make_url("")).rstrip("/")
        )
        yield client_session


async def test_get_tiles(session: ClientSession) -> None:
    """Test Tiles are returned with their auth keys and labels are skipped."""
    assert await async_get_tiles(session, "user@example.com", "secret") == [
        TileCloudTile("19264d2dffdbca32", "Wallet", AUTH_KEY),
        TileCloudTile("aaaaaaaaaaaaaaaa", "Keys", None),
    ]


async def test_invalid_credentials(session: ClientSession) -> None:
    """Test a 401 on login raises an authentication error."""
    with pytest.raises(TileCloudAuthenticationError):
        await async_get_tiles(session, "user@example.com", "wrong")


@pytest.mark.parametrize("tile_ids", [["cccccccccccccccc"]])
async def test_details_error(session: ClientSession) -> None:
    """Test a failed details request other than 412 raises."""
    with pytest.raises(TileCloudError):
        await async_get_tiles(session, "user@example.com", "secret")


async def test_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test a connection error raises a cloud error."""
    monkeypatch.setattr("tile_ble.cloud.API_URL", "http://127.0.0.1:1")
    async with ClientSession() as session:
        with pytest.raises(TileCloudError):
            await async_get_tiles(session, "user@example.com", "secret")

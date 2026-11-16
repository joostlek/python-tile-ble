"""Fetch Tile auth keys from the Tile cloud."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from aiohttp import ClientError, ClientResponseError

from .exceptions import TileCloudAuthenticationError, TileCloudError

if TYPE_CHECKING:
    from aiohttp import ClientSession

API_URL = "https://production.tile-api.com/api/v1"
API_VERSION = "1.0"
APP_ID = "ios-tile-production"
APP_VERSION = "2.89.1.4774"
USER_AGENT = "Tile/4774 CFNetwork/1312 Darwin/21.0.0"


@dataclass(frozen=True, slots=True)
class TileCloudTile:
    """A Tile as the Tile cloud lists it."""

    tile_id: str
    name: str
    auth_key: str | None


async def async_get_tiles(
    session: ClientSession, email: str, password: str, *, locale: str = "en-US"
) -> list[TileCloudTile]:
    """Log in to the Tile cloud and return the Tiles of the account."""
    client_uuid = str(uuid4())

    async def request(method: str, endpoint: str, **kwargs: Any) -> Any:
        headers = {
            "User-Agent": USER_AGENT,
            "tile_api_version": API_VERSION,
            "tile_app_id": APP_ID,
            "tile_app_version": APP_VERSION,
            "tile_client_uuid": client_uuid,
        }
        try:
            async with session.request(
                method, f"{API_URL}/{endpoint}", headers=headers, **kwargs
            ) as resp:
                resp.raise_for_status()
                result = (await resp.json())["result"]
        except ClientResponseError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                msg = "Invalid Tile credentials"
                raise TileCloudAuthenticationError(msg) from err
            msg = f"Error requesting {endpoint}: {err}"
            raise TileCloudError(msg) from err
        except (ClientError, TimeoutError) as err:
            msg = f"Error requesting {endpoint}: {err}"
            raise TileCloudError(msg) from err
        return result

    await request(
        "put",
        f"clients/{client_uuid}",
        data={"app_id": APP_ID, "app_version": APP_VERSION, "locale": locale},
    )
    await request(
        "post",
        f"clients/{client_uuid}/sessions",
        data={"email": email, "password": password},
    )

    async def details(tile_id: str) -> dict[str, Any] | None:
        try:
            result: dict[str, Any] = await request("get", f"tiles/{tile_id}")
        except TileCloudError as err:
            # Tile Labels return HTTP 412 because they have no details.
            if (
                isinstance(err.__cause__, ClientResponseError)
                and err.__cause__.status == HTTPStatus.PRECONDITION_FAILED
            ):
                return None
            raise
        return result

    states = await request("get", "tiles/tile_states")
    # The state list holds no auth key, so each Tile needs its own details request.
    results = await asyncio.gather(*(details(state["tile_id"]) for state in states))
    return [
        TileCloudTile(
            tile_id=result["tile_uuid"],
            name=result["name"],
            auth_key=result.get("auth_key"),
        )
        for result in results
        if result is not None
    ]

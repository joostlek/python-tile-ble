# Python: Tile BLE

[![GitHub Release][releases-shield]][releases]
[![Python Versions][python-versions-shield]][pypi]
![Project Stage][project-stage-shield]
![Project Maintenance][maintenance-shield]
[![License][license-shield]](LICENSE.md)

[![Build Status][build-shield]][build]
[![Code Coverage][codecov-shield]][codecov]

Asynchronous Python client for Tile trackers over Bluetooth.

## About

This package talks to a Tile over Bluetooth Low Energy with [bleak][bleak]. It can:

- check that an auth key belongs to a Tile;
- make a Tile ring;
- read the Tile ID of a Tile, without an auth key.

This package is not affiliated with, endorsed by, or connected to Tile or Life360.

## Installation

```bash
pip install tile-ble
```

## Usage

Each Tile has its own auth key. The key is a base64 string from the Tile cloud. For example, [pytile][pytile] exposes it as `Tile.auth_key` once that change is released.

```python
import asyncio

from bleak import BleakScanner

from tile_ble import TileBleDevice, TileVolume


async def main() -> None:
    """Ring a Tile."""
    ble_device = await BleakScanner.find_device_by_address("D1:76:AA:BB:CC:DD")
    assert ble_device is not None

    tile = TileBleDevice(ble_device, "AAECAwQFBgcICQoLDA0ODw==")
    await tile.async_authenticate()
    await tile.async_ring(volume=TileVolume.MEDIUM)


if __name__ == "__main__":
    asyncio.run(main())
```

`async_authenticate()` proves that the key belongs to this Tile. It does not ring the Tile.

Tiles advertise the `TILE_SERVICE_UUID` service. Use it to find Tiles in a scan.

### Find which Tile is which

The Tile cloud lists each Tile with its Tile ID. You can match a Tile ID to a Bluetooth address without a connection:

```python
from tile_ble import address_matches_tile_id

address_matches_tile_id("D1:76:AA:BB:CC:DD", "5176aabbccdd0102")  # True
```

You can also connect to a Tile and read its Tile ID. This does not need an auth key:

```python
from tile_ble import async_read_tile_id

tile_id = await async_read_tile_id(ble_device)
```

### Exceptions

All exceptions derive from `TileBleError`.

| Exception                    | Raised when                                                          |
| ---------------------------- | -------------------------------------------------------------------- |
| `TileBleConnectionError`     | The Tile cannot be reached, a Bluetooth call fails, or it times out. |
| `TileBleAuthenticationError` | The Tile rejects the auth key.                                       |
| `TileBleError`               | The Tile returns an error, or refuses to ring.                       |

`TileBleDevice` raises `ValueError` when the auth key is not a 16-byte base64 value.

## Known limitations

- Only Tiles that support multi-endpoint TOA are supported.
- Newer Tiles (firmware 48.x) are reported to fail to enable notifications under BlueZ.
- It is unknown whether a Tile accepts a connection while the phone of the owner is connected to it.
- There is no command to stop a ring. A ring stops by itself after a time-out.
- The protocol is not documented. Tile can change it at any time.
- `address_matches_tile_id()` uses a rule for Tiles with a Private ID that is inferred from two Tiles only.

## Credits

The protocol implementation follows [node-tile][node-tile], MIT License, Copyright (c) 2024 Lesley De Keyser. [jeretile][jeretile] uses the same sequence. The Tile header `toa.h` in the Nordic nRF5 SDK 16 and the paper ["Security and Privacy Analysis of Tile's Location Tracking Protocol"][paper] also document parts of the protocol.

## Changelog & Releases

This repository keeps a change log using [GitHub's releases][releases]
functionality. The format of the log is based on
[Keep a Changelog][keepchangelog].

Releases are based on [Semantic Versioning][semver], and use the format
of `MAJOR.MINOR.PATCH`. In a nutshell, the version will be incremented
based on the following:

- `MAJOR`: Incompatible or major changes.
- `MINOR`: Backwards-compatible new features and enhancements.
- `PATCH`: Backwards-compatible bugfixes and package updates.

## Contributing

This is an active open-source project. We are always open to people who want to
use the code or contribute to it.

We've set up a separate document for our
[contribution guidelines](.github/CONTRIBUTING.md).

Thank you for being involved! :heart_eyes:

## Setting up development environment

This Python project is fully managed using the [uv][uv] dependency manager. But also relies on the use of NodeJS for certain checks during development.

You need at least:

- Python 3.13+
- [uv][uv-install]
- NodeJS 12+ (including NPM)

To install all packages, including all development requirements:

```bash
npm install
uv sync --all-groups
```

As this repository uses the [prek][prek] framework, all changes
are linted and tested with each commit. You can run all checks and tests
manually, using the following command:

```bash
uv run prek run --all-files
```

To run just the Python tests:

```bash
uv run pytest
```

## Authors & contributors

The content is by [Joost Lekkerkerker][joostlek].

For a full list of all authors and contributors,
check [the contributor's page][contributors].

## License

MIT License

Copyright (c) 2026 Joost Lekkerkerker

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

The protocol implementation is based on [node-tile][node-tile]. See
[LICENSE.md](LICENSE.md) for its copyright and permission notice.

[bleak]: https://github.com/hbldh/bleak
[build-shield]: https://github.com/joostlek/python-tile-ble/actions/workflows/tests.yaml/badge.svg
[build]: https://github.com/joostlek/python-tile-ble/actions
[codecov-shield]: https://codecov.io/gh/joostlek/python-tile-ble/branch/master/graph/badge.svg
[codecov]: https://codecov.io/gh/joostlek/python-tile-ble
[commits-shield]: https://img.shields.io/github/commit-activity/y/joostlek/python-tile-ble.svg
[commits]: https://github.com/joostlek/python-tile-ble/commits/master
[contributors]: https://github.com/joostlek/python-tile-ble/graphs/contributors
[jeretile]: https://github.com/jeremad/jeretile
[joostlek]: https://github.com/joostlek
[keepchangelog]: http://keepachangelog.com/en/1.0.0/
[license-shield]: https://img.shields.io/github/license/joostlek/python-tile-ble.svg
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[node-tile]: https://github.com/lesleyxyz/node-tile
[paper]: https://arxiv.org/abs/2510.00350
[poetry-install]: https://python-poetry.org/docs/#installation
[poetry]: https://python-poetry.org
[prek]: https://prek.j178.dev/
[pytile]: https://github.com/bachya/pytile
[uv]: https://docs.astral.sh/uv/
[uv-install]: https://docs.astral.sh/uv/getting-started/installation/
[project-stage-shield]: https://img.shields.io/badge/project%20stage-beta-yellow.svg
[python-versions-shield]: https://img.shields.io/pypi/pyversions/tile-ble
[releases-shield]: https://img.shields.io/github/release/joostlek/python-tile-ble.svg
[releases]: https://github.com/joostlek/python-tile-ble/releases
[semver]: http://semver.org/spec/v2.0.0.html
[pypi]: https://pypi.org/project/tile-ble/

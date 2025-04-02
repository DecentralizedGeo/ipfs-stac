# IPFS-STAC

[![PyPI version](https://badge.fury.io/py/ipfs-stac.svg)](https://badge.fury.io/py/ipfs-stac)
[![PyPI license](https://img.shields.io/pypi/l/ansicolortags.svg)](https://pypi.python.org/pypi/ansicolortags/)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/ansicolortags.svg)](https://pypi.python.org/pypi/ipfs-stac/)

`ipfs-stac` is a Python library that provides functionality for querying and interacting with STAC catalogs enriched with IPFS. The library supports seamless operations between leveraging STAC APIs enriched with IPFS metadata and interfacing with IPFS itself given a node. Visit the [documentation](https://decentralizedgeo.github.io/ipfs-stac/) for more information.

## Features

- Query/search STAC APIs
- Fetch content via CIDs
- Start/stop local IPFS Daemon
- Retrieve asset names
- Retrieve catalogs and item collections
- Upload content to IPFS
- Parse IPFS data into DataFrames
- Transform assets to NumPy arrays
- Pin IPFS CIDs
- Host IPFS content on the mutable file system (MFS)

---

### Installation

The client can be installed through pip

```shell
pip install ipfs-stac
```

---

## Attributions

This project was made possible by the following

- [ipfsspec](https://github.com/fsspec/ipfsspec)
- [pystac-client](https://github.com/stac-utils/pystac-client)

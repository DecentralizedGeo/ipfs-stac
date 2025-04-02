# Install ipfs-stac

`ipfs-stac` currently requires Python 3.11 or above. To install from the Python Package index (PyPi) run the following command:

```shell
python pip install ipfs-stac
```

## Development Installation

we use <a href="https://python-poetry.org/" target="_blank">poetry</a> for dependency management.

To install a development version from source:

```shell
git clone https://github.com/DecentralizedGeo/ipfs-stac.git
cd ipfs-stac
python -m venv .venv
poetry install --with dev
```

## Documentation

we use <a href="https://www.mkdocs.org/" target="_blank">mkdocs</a> and the <a href="https://mkdocs.github.io/mkdocs-material/" target="_blank">material theme</a> extension to build and generate our documentation.

To install the documentation dependencies:

```shell
poetry install --with docs
```

To build the documentation and view it locally:

```shell
mkdocs build
mkdocs server --clean --open
```

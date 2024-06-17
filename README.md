# stactools-noaa-hrrr

[![PyPI](https://img.shields.io/pypi/v/stactools-noaa-hrrr?style=for-the-badge)](https://pypi.org/project/stactools-noaa-hrrr/)
![GitHub Workflow Status (with event)](https://img.shields.io/github/actions/workflow/status/stactools-packages/noaa-hrrr/continuous-integration.yml?style=for-the-badge)

- Name: noaa-hrrr
- Package: `stactools.noaa_hrrr`
- [stactools-noaa-hrrr on PyPI](https://pypi.org/project/stactools-noaa-hrrr/)
- Owner: @hrodmn
- [Dataset homepage](https://rapidrefresh.noaa.gov/hrrr/)
- STAC extensions used:
  - [forecast](https://github.com/stac-extensions/forecast)
  - [item-assets](https://github.com/stac-extensions/item-assets)
  - [datacube](https://github.com/stac-extensions/datacube) (coming soon)
- Extra fields:
  - `noaa-hrrr:forecast_cycle_type`: either standard (18-hour) or extended (48-hour)
  - `noaa-hrrr:region`: either `conus` or `alaska`
- [Browse the example in human-readable form](https://radiantearth.github.io/stac-browser/#/external/raw.githubusercontent.com/stactools-packages/noaa-hrrr/main/examples/collection.json)
- [Browse a notebook demonstrating the example item and collection](https://github.com/stactools-packages/noaa-hrrr/tree/main/docs/example.ipynb)

A short description of the package and its usage.

## STAC examples

- [Collection](examples/collection.json)
- [Item](examples/item/item.json)

## Installation

Install `stactools-noaa-hrrr` with pip:

```shell
pip install stactools-noaa-hrrr
```

## Command-line usage

To create a collection object:

```shell
stac noaahrrr create-collection {region} {product} {cloud_provider} {destination_file}
```

e.g.

```shell
stac noaahrrr create-collection conus sfc azure example-collection.json
```

To create an item:

```shell
stac noaahrrr create-item \
  {region} \
  {product} \
  {cloud_provider} \
  {reference_datetime} \
  {forecast_hour} \
  {destination_file}
```

e.g.

```shell
stac noaahrrr create-item conus sfc azure 2024-05-01T12 10 example-item.json
```

To create all items for a date range:

```shell
stac noaahrrr create-item-collection \
  {region} \
  {product} \
  {cloud_provider} \
  {start_date} \
  {end_date} \
  {destination_folder}
```

e.g.

```shell
stac noaahrrr create-item-collection conus sfc azure 2024-05-01 2024-05-31 /tmp/items
```

### Docker

You can launch a jupyterhub server in a docker container with all of the
dependencies installed using these commands:

```shell
docker/build
docker/jupyter
```

Use `stac noaahrrr --help` to see all subcommands and options.

## Contributing

We use [pre-commit](https://pre-commit.com/) to check any changes.
To set up your development environment:

```shell
pip install -e '.[dev]'
pre-commit install
```

To check all files:

```shell
pre-commit run --all-files
```

To run the tests:

```shell
pytest -vv
```

If you've updated the STAC metadata output, update the examples:

```shell
scripts/update-examples
```

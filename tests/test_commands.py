from pathlib import Path

import pytest
from click import Group
from click.testing import CliRunner
from pystac import Collection, Item
from stactools.noaa_hrrr.commands import create_noaahrrr_command
from stactools.noaa_hrrr.constants import (
    PRODUCT_FORECAST_HOUR_SETS,
    CloudProvider,
    ForecastHourSet,
    Product,
    Region,
)

command = create_noaahrrr_command(Group())


product_forecast_hour_combinations = [
    (product, fh_set)
    for product, fh_sets in PRODUCT_FORECAST_HOUR_SETS.items()
    for fh_set in fh_sets
]


@pytest.mark.parametrize("region", list(Region))  # type: ignore
@pytest.mark.parametrize(
    "product, forecast_hour_set",
    product_forecast_hour_combinations,
)  # type: ignore
@pytest.mark.parametrize("cloud_provider", list(CloudProvider))  # type: ignore
def test_create_collection(
    region: Region,
    product: Product,
    forecast_hour_set: ForecastHourSet,
    cloud_provider: CloudProvider,
    tmp_path: Path,
) -> None:
    # Smoke test for the command line create-collection command
    #
    # Most checks should be done in test_stac.py::test_create_collection

    path = str(tmp_path / "collection.json")
    runner = CliRunner()
    result = runner.invoke(
        command,
        [
            "create-collection",
            region.value,
            product.value,
            forecast_hour_set.value,
            cloud_provider.value,
            path,
        ],
    )
    assert result.exit_code == 0, "\n{}".format(result.output)
    collection = Collection.from_file(path)
    collection.validate()


def test_create_item(tmp_path: Path) -> None:
    # Smoke test for the command line create-item command
    #
    # Most checks should be done in test_stac.py::test_create_item
    path = str(tmp_path / "item.json")
    runner = CliRunner()
    result = runner.invoke(
        command,
        ["create-item", "sfc", "2024-05-01T12", "0", "conus", "azure", path],
    )
    assert result.exit_code == 0, "\n{}".format(result.output)
    item = Item.from_file(path)
    item.validate()

from pathlib import Path

import pytest
from click import Group
from click.testing import CliRunner
from pystac import Collection, Item
from stactools.noaa_hrrr.commands import create_noaahrrr_command
from stactools.noaa_hrrr.metadata import (
    CloudProvider,
    Product,
    Region,
)

command = create_noaahrrr_command(Group())


@pytest.mark.parametrize("region", list(Region))  # type: ignore
@pytest.mark.parametrize("product", list(Product))  # type: ignore
@pytest.mark.parametrize("cloud_provider", list(CloudProvider))  # type: ignore
def test_create_collection(
    region: Region,
    product: Product,
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
        ["create-item", "conus", "sfc", "azure", "2024-05-01T12", "0", path],
    )
    assert result.exit_code == 0, "\n{}".format(result.output)
    item = Item.from_file(path)
    item.validate()

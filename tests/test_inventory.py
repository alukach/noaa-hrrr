import pandas as pd
import pytest
from stactools.noaa_hrrr.inventory import (
    DESCRIPTION_COLS,
    INVENTORY_COLS,
    generate_single_inventory_df,
    read_inventory_df,
)
from stactools.noaa_hrrr.metadata import (
    PRODUCT_CONFIGS,
    Product,
    Region,
)

product_forecast_hour_combinations = [
    (product, fh_set)
    for product, product_config in PRODUCT_CONFIGS.items()
    for fh_set in product_config.forecast_hour_sets
]


@pytest.mark.parametrize("region", list(Region))  # type: ignore
@pytest.mark.parametrize("product", list(Product))  # type: ignore
def test_read_inventory_df(
    region: Region,
    product: Product,
) -> None:
    inventory_df = read_inventory_df(
        region=region,
        product=product,
    )

    assert isinstance(inventory_df, pd.DataFrame)

    assert list(inventory_df.keys()) == INVENTORY_COLS + DESCRIPTION_COLS


@pytest.mark.parametrize("region", list(Region))  # type: ignore
@pytest.mark.parametrize("product", list(Product))  # type: ignore
def test_generate_single_inventory_df(
    region: Region,
    product: Product,
) -> None:
    inventory_df = generate_single_inventory_df(
        region=region, product=product, cycle_run_hour=0, forecast_hour=0
    )

    assert isinstance(inventory_df, pd.DataFrame)

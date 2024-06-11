import pandas as pd
import pytest
from stactools.noaa_hrrr.constants import (
    PRODUCT_FORECAST_HOUR_SETS,
    ForecastCycleType,
    ForecastHourSet,
    Product,
    Region,
)
from stactools.noaa_hrrr.inventory import (
    DATA_COLS,
    generate_single_inventory_df,
    load_inventory_df,
)

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
@pytest.mark.parametrize(
    "forecast_cycle_type",
    [ForecastCycleType(type) for type in ["standard", "extended"]],
)  # type: ignore
def test_load_inventory_df(
    region: Region,
    product: Product,
    forecast_hour_set: ForecastHourSet,
    forecast_cycle_type: ForecastCycleType,
) -> None:
    inventory_df = load_inventory_df(
        region=region,
        product=product,
        forecast_hour_set=forecast_hour_set,
        forecast_cycle_type=forecast_cycle_type,
    )

    assert isinstance(inventory_df, pd.DataFrame)

    assert list(inventory_df.keys()) == DATA_COLS + ["description", "unit"]


@pytest.mark.parametrize("region", list(Region))  # type: ignore
@pytest.mark.parametrize(
    "product, forecast_hour_set",
    product_forecast_hour_combinations,
)  # type: ignore
@pytest.mark.parametrize(
    "forecast_cycle_type",
    [ForecastCycleType(type) for type in ["standard", "extended"]],
)  # type: ignore
def test_generate_single_inventory_df(
    region: Region,
    product: Product,
    forecast_hour_set: ForecastHourSet,
    forecast_cycle_type: ForecastCycleType,
) -> None:
    inventory_df = generate_single_inventory_df(
        region=region,
        product=product,
        forecast_cycle_type=forecast_cycle_type,
        forecast_hour_set=forecast_hour_set,
        cycle_run_hour=0 if forecast_cycle_type.type == "extended" else 3,
        forecast_hour=0
        if forecast_hour_set in [ForecastHourSet.FH00, ForecastHourSet.FH01_18]
        else 3,
    )

    assert isinstance(inventory_df, pd.DataFrame)

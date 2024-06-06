import logging
import multiprocessing as mp
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from herbie import Herbie
from stactools.noaa_hrrr.constants import (
    DATA_DIR,
    PRODUCT_FORECAST_HOUR_SETS,
    REGION_CONFIGS,
    CloudProvider,
    ForecastCycleType,
    ForecastHourSet,
    Product,
    Region,
)

INVENTORY_CSV_GZ_FORMAT = "__".join(
    [
        "inventory",
        "{region}",
        "{product}",
        "{forecast_hour_set}",
        "{forecast_cycle_type}.csv.gz",
    ]
)

INDEX_COL = "forecast_hour"
DATA_COLS = ["grib_message", "variable", "level", "forecast_time", "search_this"]

dummy_datetime = datetime(year=2024, month=5, day=1)


def load_inventory_df(
    region: Region,
    product: Product,
    forecast_hour_set: ForecastHourSet,
    forecast_cycle_type: ForecastCycleType,
    forecast_hour: Optional[int] = None,
) -> pd.DataFrame:
    inventory_df = pd.read_csv(
        DATA_DIR
        / INVENTORY_CSV_GZ_FORMAT.format(
            region=region.value,
            product=product.value,
            forecast_hour_set=forecast_hour_set.value,
            forecast_cycle_type=forecast_cycle_type.type,
        ),
        index_col=INDEX_COL,
    )

    if forecast_hour is not None:
        inventory_df = inventory_df.loc[forecast_hour]

    return inventory_df


def generate_single_inventory_df(
    region: Region,
    product: Product,
    forecast_cycle_type: ForecastCycleType,
    cycle_run_hour: int,
    forecast_hour_set: ForecastHourSet,
    forecast_hour: int,
) -> pd.DataFrame:
    region_config = REGION_CONFIGS[region]
    herbie_metadata = Herbie(
        dummy_datetime + timedelta(hours=cycle_run_hour),
        model=region_config.herbie_model_id,
        product=product.value,
        fxx=forecast_hour,
        priority=[CloudProvider.azure],
        verbose=False,
    ).inventory()

    out = herbie_metadata.assign(
        region=region.value,
        product=product.value,
        forecast_hour_set=forecast_hour_set.value,
        forecast_cycle_type=forecast_cycle_type.type,
        forecast_hour=forecast_hour,
    ).set_index(keys=[INDEX_COL])[DATA_COLS]

    assert isinstance(out, pd.DataFrame)

    return out


def generate_inventory_csv_gzs(dest_dir: Path) -> None:
    for region in Region:
        for product, forecast_hour_sets in PRODUCT_FORECAST_HOUR_SETS.items():
            for cycle_run_hour in [3, 6]:
                forecast_cycle_type = ForecastCycleType.from_timestamp(
                    dummy_datetime + timedelta(hours=cycle_run_hour)
                )
                allowed_forecast_hours = list(
                    forecast_cycle_type.generate_forecast_hours()
                )
                for forecast_hour_set in forecast_hour_sets:
                    tasks = []
                    for forecast_hour in list(
                        set(forecast_hour_set.generate_forecast_hours())
                        & set(allowed_forecast_hours)
                    ):
                        tasks.append(
                            (
                                region,
                                product,
                                forecast_cycle_type,
                                cycle_run_hour,
                                forecast_hour_set,
                                forecast_hour,
                            )
                        )

                    with mp.Pool() as pool:
                        dfs = pool.starmap(generate_single_inventory_df, tasks)

                    full_df = pd.concat(dfs)

                    inventory_csv_gz = dest_dir / INVENTORY_CSV_GZ_FORMAT.format(
                        region=region.value,
                        product=product.value,
                        forecast_hour_set=forecast_hour_set.value,
                        forecast_cycle_type=forecast_cycle_type.type,
                    )
                    full_df.to_csv(inventory_csv_gz)

                    logging.info(f"Data successfully written to {inventory_csv_gz}")

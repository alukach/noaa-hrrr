import logging
import multiprocessing as mp
from datetime import datetime, timedelta
from typing import Union

import pandas as pd
import pystac
from pystac import (
    Collection,
    Extent,
    Item,
    SpatialExtent,
    TemporalExtent,
)
from pystac.catalog import CatalogType
from pystac.extensions.item_assets import AssetDefinition
from pystac.item_collection import ItemCollection
from pystac.provider import Provider, ProviderRole
from stactools.noaa_hrrr.constants import (
    CLOUD_PROVIDER_CONFIGS,
    COLLECTION_ID_FORMAT,
    ITEM_ID_FORMAT,
    PRODUCT_CONFIGS,
    REGION_CONFIGS,
    CloudProvider,
    ForecastCycleType,
    ForecastLayerType,
    ItemType,
    Product,
    Region,
)
from stactools.noaa_hrrr.inventory import NotFoundError, read_idx

GRIB2_MEDIA_TYPE = "application/wmo-GRIB2"
NDJSON_MEDIA_TYPE = "application/x-ndjson"
INDEX_ASSET_DEFINITION = AssetDefinition(
    {
        "type": NDJSON_MEDIA_TYPE,
        "roles": ["index"],
        "title": "Index file",
        "description": (
            "The index file contains information on each message within "
            "the GRIB2 file."
        ),
    }
)

ITEM_BASE_ASSETS = {
    Product.sfc: {
        ItemType.GRIB: AssetDefinition(
            {
                "type": GRIB2_MEDIA_TYPE,
                "roles": ["data"],
                "title": "2D Surface Levels",
                "description": (
                    "2D Surface Level forecast data as a grib2 file. Subsets of the "
                    "data can be loaded using the provided byte range."
                ),
            }
        ),
        ItemType.INDEX: INDEX_ASSET_DEFINITION,
    },
    Product.subh: {
        ItemType.GRIB: AssetDefinition(
            {
                "type": GRIB2_MEDIA_TYPE,
                "roles": ["data"],
                "title": "2D Surface Levels - Sub Hourly",
                "description": (
                    "2D Surface Level forecast data (sub-hourly, 15 minute intervals) "
                    "as a grib2 file. Subsets of the data can be loaded using the "
                    "provided byte range."
                ),
            }
        ),
        ItemType.INDEX: INDEX_ASSET_DEFINITION,
    },
    Product.prs: {
        ItemType.GRIB: AssetDefinition(
            {
                "type": GRIB2_MEDIA_TYPE,
                "roles": ["data"],
                "title": "3D Pressure Levels",
                "description": (
                    "3D Pressure Level forecast data as a grib2 file. Subsets of the "
                    "data can be loaded using the provided byte range."
                ),
            }
        ),
        ItemType.INDEX: INDEX_ASSET_DEFINITION,
    },
    Product.nat: {
        ItemType.GRIB: AssetDefinition(
            {
                "type": GRIB2_MEDIA_TYPE,
                "roles": ["data"],
                "title": "Native Levels",
                "description": (
                    "Native Level forecast data as a grib2 file. Subsets of the data "
                    "can be loaded using the provided byte range."
                ),
            }
        ),
        ItemType.INDEX: INDEX_ASSET_DEFINITION,
    },
}


def create_collection(
    product: Product,
    cloud_provider: CloudProvider,
) -> Collection:
    """Creates a STAC Collection.

    Args:
        product (Product): The product for this collection, must be one of the members
            of the Product Enum.
        cloud_provider (CloudProvider): cloud provider for the assets. Must be a member
            of the CloudProvider Enum. Each cloud_provider has data available from a
            different start date.
    Returns:
        Collection: STAC Collection object
    """
    product_config = PRODUCT_CONFIGS[product]
    cloud_provider_config = CLOUD_PROVIDER_CONFIGS[cloud_provider]
    extent = Extent(
        SpatialExtent(
            [region_config.bbox_4326 for region_config in REGION_CONFIGS.values()]
        ),
        TemporalExtent([[cloud_provider_config.start_date, None]]),
    )

    providers = [
        Provider(
            name="NOAA",
            roles=[ProviderRole.PRODUCER],
            url="https://www.noaa.gov/",
        )
    ]

    links = [
        pystac.Link(
            rel=pystac.RelType.LICENSE,
            target="https://creativecommons.org/licenses/by/4.0/",
            media_type="text/html",
            title="CC-BY-4.0 license",
        ),
        pystac.Link(
            rel="documentation",
            target="https://rapidrefresh.noaa.gov/hrrr/",
            media_type="text/html",
            title="NOAA HRRR documentation",
        ),
    ]

    keywords = [
        "NOAA",
        "HRRR",
        "forecast",
        "atmospheric",
        "weather",
    ]

    collection = Collection(
        id=COLLECTION_ID_FORMAT.format(
            product=product.value,
        ),
        title=(
            "NOAA High Resolution Rapid Refresh (HRRR) - "
            f"{product_config.description}"
        ),
        description=(
            "The NOAA HRRR is a real-time 3km resolution, hourly updated, "
            "cloud-resolving, convection-allowing atmospheric model, "
            "initialized by 3km grids with 3km radar assimilation. Radar data is "
            "assimilated in the HRRR every 15 min over a 1-hour period adding further "
            "detail to that provided by the hourly data assimilation from the 13km "
            "radar-enhanced Rapid Refresh (RAP) system. "
            f"This specific collection represents {product_config.description}."
        ),
        extent=extent,
        license="CC-BY-4.0",
        providers=providers,
        catalog_type=CatalogType.RELATIVE_PUBLISHED,
        keywords=keywords,
    )

    collection.add_links(links)

    return collection


def create_item(
    region: Region,
    product: Product,
    cloud_provider: CloudProvider,
    reference_datetime: datetime,
    forecast_hour: int,
) -> Item:
    """Creates a STAC item for a region x product x cloud provider x reference_datetime
    (cycle run hour) combination.

    Args:
        region (Region): Either Region.conus or Region.Alaska
        product (Product): The product for this collection, must be one of the members
            of the Product Enum.
        cloud_provider (CloudProvider): cloud provider for the assets. Must be a member
            of the CloudProvider Enum. Each cloud_provider has data available from a
            different start date.
        reference_datetime (datetime): The reference datetime for the forecast data,
            corresponds to 'date' + 'cycle run hour'
        forecast_hour (int): The forecast hour (FH) for the item.
            This will set the item's datetime property ('date' + 'cycle run hour' +
            'forecast hour')

    Returns:
        Item: STAC Item object
    """
    region_config = REGION_CONFIGS[region]
    cloud_provider_config = CLOUD_PROVIDER_CONFIGS[cloud_provider]

    # make sure there is data for the reference_datetime
    # (Alaska only runs the model every three hours)
    if cycle_run_hour := reference_datetime.hour not in region_config.cycle_run_hours:
        cycle_run_hours = [str(hour) for hour in region_config.cycle_run_hours]
        raise ValueError(
            f"{cycle_run_hour} is not a valid cycle run hour for {region.value}\n"
            f"Please select one of {' ,'.join(cycle_run_hours)}"
        )

    # set up item
    forecast_datetime = reference_datetime + timedelta(hours=forecast_hour)

    # the forecast_cycle_type defines the available forecast hours and products
    forecast_cycle_type = ForecastCycleType.from_timestamp(
        reference_datetime=reference_datetime
    )

    forecast_cycle_type.validate_forecast_hour(forecast_hour)

    item = Item(
        ITEM_ID_FORMAT.format(
            product=product.value,
            reference_datetime=reference_datetime.strftime("%Y-%m-%dT%H"),
            forecast_hour=forecast_hour,
            region=region.value,
        ),
        geometry=region_config.geometry_4326,
        bbox=region_config.bbox_4326,
        datetime=forecast_datetime,
        properties={
            "forecast:reference_time": reference_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
            "forecast:horizon": f"PT{forecast_hour}H",
            "noaa-hrrr:forecast_cycle_type": str(forecast_cycle_type),
            "noaa-hrrr:region": region.value,
        },
    )

    grib_url = cloud_provider_config.url_base + region_config.format_grib_url(
        product=product,
        reference_datetime=reference_datetime,
        forecast_hour=forecast_hour,
        idx=False,
    )
    idx_url = grib_url + ".idx"

    item.assets[ItemType.GRIB.value] = ITEM_BASE_ASSETS[product][
        ItemType.GRIB
    ].create_asset(grib_url)

    item.assets[ItemType.INDEX.value] = ITEM_BASE_ASSETS[product][
        ItemType.INDEX
    ].create_asset(idx_url)

    # create an asset for each row in the inventory dataframe
    idx_df = read_idx(
        region=region,
        product=product,
        cloud_provider=cloud_provider,
        reference_datetime=reference_datetime,
        forecast_hour=forecast_hour,
    )
    grib_asset = item.assets[ItemType.GRIB.value]
    grib_asset.extra_fields["grib:layers"] = {}
    for _, row in idx_df[
        [
            "grib_message",
            "start_byte",
            "byte_size",
            "variable",
            "level",
            "forecast_time",
        ]
    ].iterrows():
        forecast_layer_type = ForecastLayerType.from_str(row.forecast_time)

        layer_key = "__".join(
            [
                row.variable.replace(" ", "_"),
                row.level.replace(" ", "_"),
                str(forecast_layer_type),
            ]
        )

        if pd.isna(row.byte_size):
            row.byte_size = None

        grib_asset.extra_fields["grib:layers"][layer_key] = {
            **row,
            **forecast_layer_type.asset_properties(
                reference_datetime=reference_datetime
            ),
        }

    return item


def create_item_safe(
    region: Region,
    product: Product,
    cloud_provider: CloudProvider,
    reference_datetime: datetime,
    forecast_hour: int,
) -> Union[Item, None]:
    try:
        return create_item(
            region, product, cloud_provider, reference_datetime, forecast_hour
        )
    except NotFoundError as e:
        logging.warning(e)
        return None


def create_item_collection(
    region: Region,
    product: Product,
    cloud_provider: CloudProvider,
    start_date: datetime,
    end_date: datetime,
) -> pystac.ItemCollection:
    """Create an item collection containing all items for a date range"""

    region_config = REGION_CONFIGS[region]

    one_day = timedelta(days=1)
    tasks = []
    reference_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    while reference_date <= end_date:
        for cycle_run_hour in region_config.cycle_run_hours:
            reference_datetime = reference_date + timedelta(hours=cycle_run_hour)
            forecast_cycle_type = ForecastCycleType.from_timestamp(reference_datetime)
            for forecast_hour in forecast_cycle_type.generate_forecast_hours():
                tasks.append(
                    (region, product, cloud_provider, reference_datetime, forecast_hour)
                )

        reference_date += one_day

    print(f"creating {len(tasks)} items")
    with mp.Pool(8) as pool:
        items = pool.starmap(create_item_safe, tasks)

    return ItemCollection(item for item in items if item is not None)

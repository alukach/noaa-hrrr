from datetime import datetime, timedelta

import pystac
from herbie import Herbie
from pystac import (
    Collection,
    Extent,
    Item,
    SpatialExtent,
    TemporalExtent,
)
from pystac.catalog import CatalogType
from pystac.extensions.datacube import (
    DatacubeExtension,
    Dimension,
    DimensionType,
    Variable,
    VariableType,
)
from pystac.extensions.item_assets import AssetDefinition, ItemAssetsExtension
from pystac.provider import Provider, ProviderRole
from stactools.noaa_hrrr.constants import (
    CLOUD_PROVIDER_START_DATES,
    COLLECTION_ID_FORMAT,
    FORECAST_HOUR_SET_DESCRIPTIONS,
    ITEM_ID_FORMAT,
    PRODUCT_DESCRIPTIONS,
    REGION_CONFIGS,
    RESOLUTION_METERS,
    CloudProvider,
    ForecastCycleType,
    ForecastHourSet,
    ItemType,
    Product,
    Region,
)
from stactools.noaa_hrrr.inventory import load_inventory_df

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

ITEM_ASSETS = {
    Product.surface: {
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
    Product.sub_hourly: {
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
    Product.pressure: {
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
    Product.native: {
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
    region: Region,
    product: Product,
    forecast_hour_set: ForecastHourSet,
    cloud_provider: CloudProvider,
) -> Collection:
    """Creates a STAC Collection.

    Args:
        region (Region): Either Region.conus or Region.Alaska
        product (Product): The product for this collection, must be one of the members
            of the Product Enum.
        forecast_hour_set (ForecastHourSet): The forecast hour set (e.g. FH00-01,
            FH02-48) for this collection. Must be a member of the ForecastHourSet Enum.
        cloud_provider (CloudProvider): cloud provider for the assets. Must be a member
            of the CloudProvider Enum. Each cloud_provider has data available from a
            different start date.
    Returns:
        Collection: STAC Collection object
    """
    region_config = REGION_CONFIGS[region]
    extent = Extent(
        SpatialExtent([region_config.bbox_4326]),
        TemporalExtent([[CLOUD_PROVIDER_START_DATES[cloud_provider], None]]),
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
            region=region.value,
            product=product.value,
            forecast_hour_set=forecast_hour_set.value,
        ),
        title="NOAA High Resolution Rapid Refresh (HRRR) collection",
        description=(
            "The NOAA HRRR is a real-time 3km resolution, hourly updated, "
            "cloud-resolving, convection-allowing atmospheric model, "
            "initialized by 3km grids with 3km radar assimilation. Radar data is "
            "assimilated in the HRRR every 15 min over a 1-hour period adding further "
            "detail to that provided by the hourly data assimilation from the 13km "
            "radar-enhanced Rapid Refresh (RAP) system. "
            f"This specific collection represents {PRODUCT_DESCRIPTIONS[product]} for "
            f"{FORECAST_HOUR_SET_DESCRIPTIONS[forecast_hour_set]} in the {region.value}"
            " region."
        ),
        extent=extent,
        license="CC-BY-4.0",
        providers=providers,
        catalog_type=CatalogType.RELATIVE_PUBLISHED,
        keywords=keywords,
    )

    collection.add_links(links)

    item_assets_ext = ItemAssetsExtension.ext(collection, add_if_missing=True)
    item_assets_ext.item_assets = {
        item_type.value: item_asset
        for item_type, item_asset in ITEM_ASSETS[product].items()
    }
    inventory_df = load_inventory_df(
        region=region,
        product=product,
        forecast_hour_set=forecast_hour_set,
        forecast_cycle_type=ForecastCycleType("extended"),
    )

    variable_df = inventory_df.set_index(
        keys=["variable", "description", "unit"]
    ).sort_index(level="variable")

    # define the datacube metadata using the inventory files for this
    # region x product x forecast hour set
    datacube_ext = DatacubeExtension.ext(collection, add_if_missing=True)
    datacube_ext.apply(
        dimensions={
            "x": Dimension(
                properties={
                    "type": DimensionType.SPATIAL,
                    "reference_system": region_config.item_crs.to_wkt(),
                    "extent": [
                        region_config.item_bbox_proj[0] + RESOLUTION_METERS / 2,
                        region_config.item_bbox_proj[2] - RESOLUTION_METERS / 2,
                    ],
                    "axis": "x",
                }
            ),
            "y": Dimension(
                properties={
                    "type": DimensionType.SPATIAL,
                    "reference_system": region_config.item_crs.to_wkt(),
                    "extent": [
                        region_config.item_bbox_proj[1] + RESOLUTION_METERS / 2,
                        region_config.item_bbox_proj[3] - RESOLUTION_METERS / 2,
                    ],
                    "axis": "y",
                }
            ),
            # these match the information in the inventory files
            "level": Dimension(
                properties={
                    "type": "atmospheric level",
                    "description": (
                        "The atmospheric level for which the forecast is applicable, "
                        "e.g. surface, top of atmosphere, 100 m above ground, etc."
                    ),
                    "values": list(sorted(set(inventory_df["level"].unique()))),
                }
            ),
            "forecast_time": Dimension(
                properties={
                    "type": DimensionType.TEMPORAL,
                    "description": (
                        "The time horizon for which the forecast is applicable."
                    ),
                    "values": list(sorted(set(inventory_df["forecast_time"].unique()))),
                }
            ),
        },
        variables={
            variable: Variable(
                properties=dict(
                    dimensions=["x", "y", "level", "forecast_time"],
                    type=VariableType.DATA,
                    description=description,
                    unit=unit,
                    # experimental new field for defining the specific values of each
                    # domain where this variable has data
                    dimension_domains={
                        "level": list(group["level"].unique()),
                        "forecast_time": list(group["forecast_time"].unique()),
                    },
                )
            )
            for (variable, description, unit), group in variable_df.groupby(
                level=["variable", "description", "unit"]
            )
        },
    )

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

    herbie_metadata = Herbie(
        reference_datetime,
        model=region_config.herbie_model_id,
        fxx=forecast_hour,
        priority=[cloud_provider.value],
        product=product.value,
        verbose=False,
    )

    assert isinstance(herbie_metadata.grib, str)
    item.assets[ItemType.GRIB.value] = ITEM_ASSETS[product][ItemType.GRIB].create_asset(
        herbie_metadata.grib
    )

    assert isinstance(herbie_metadata.idx, str)
    item.assets[ItemType.INDEX.value] = ITEM_ASSETS[product][
        ItemType.INDEX
    ].create_asset(herbie_metadata.idx)

    return item

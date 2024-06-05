from datetime import datetime, timedelta

# from pystac.extensions.datacube import DatacubeExtension
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
from pystac.extensions.item_assets import AssetDefinition, ItemAssetsExtension
from pystac.provider import Provider, ProviderRole
from stactools.noaa_hrrr.constants import (
    CLOUD_PROVIDER_START_DATES,
    ITEM_ID_FORMAT,
    REGION_CONFIGS,
    CloudProvider,
    ForecastCycleType,
    Product,
    Region,
)

GRIB2_MEDIA_TYPE = "application/wmo-GRIB2"

ITEM_ASSETS = {
    Product.surface: AssetDefinition(
        {
            "type": GRIB2_MEDIA_TYPE,
            "roles": ["data"],
            "title": "2D Surface Levels",
            "description": (
                "2D Surface Level forecast data as a grib2 file. Subsets of the data "
                "can be loaded using the provided byte range."
            ),
        }
    ),
    Product.sub_hourly: AssetDefinition(
        {
            "type": GRIB2_MEDIA_TYPE,
            "roles": ["data"],
            "title": "2D Surface Levels - Sub Hourly",
            "description": (
                "2D Surface Level forecast data (sub-hourly, 15 minute intervals) as a "
                "grib2 file. Subsets of the data can be loaded using the provided byte "
                "range."
            ),
        }
    ),
    Product.pressure: AssetDefinition(
        {
            "type": GRIB2_MEDIA_TYPE,
            "roles": ["data"],
            "title": "3D Pressure Levels",
            "description": (
                "3D Pressure Level forecast data as a grib2 file. Subsets of the data "
                "can be loaded using the provided byte range."
            ),
        }
    ),
    Product.native: AssetDefinition(
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
}


def create_collection(cloud_provider: CloudProvider) -> Collection:
    """Creates a STAC Collection.

    Args:
        cloud_provider: cloud provider cloud_provider from which items will be generated
            Each cloud_provider has data available from a different start date.
    Returns:
        Collection: STAC Collection object
    """
    extent = Extent(
        SpatialExtent(
            [region_config.bbox_4326 for region_config in REGION_CONFIGS.values()]
        ),
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
        id="noaa-hrrr",
        title="NOAA High Resolution Rapid Refresh (HRRR) collection",
        description=(
            "The NOAA HRRR is a real-time 3km resolution, hourly updated, "
            "cloud-resolving, convection-allowing atmospheric model, "
            "initialized by 3km grids with 3km radar assimilation. Radar data is "
            "assimilated in the HRRR every 15 min over a 1-hour period adding further "
            "detail to that provided by the hourly data assimilation from the 13km "
            "radar-enhanced Rapid Refresh (RAP) system."
        ),
        extent=extent,
        license="CC-BY-4.0",
        providers=providers,
        catalog_type=CatalogType.RELATIVE_PUBLISHED,
        keywords=keywords,
    )

    collection.add_links(links)

    item_assets_attrs = ItemAssetsExtension.ext(collection, add_if_missing=True)
    item_assets_attrs.item_assets = {
        product.value: item_asset for product, item_asset in ITEM_ASSETS.items()
    }

    return collection


def create_item(
    reference_datetime: datetime,
    forecast_hour: int,
    region: Region,
    cloud_provider: CloudProvider,
) -> Item:
    """Creates a STAC item from a raster asset.

    This example function uses :py:func:`stactools.core.utils.create_item` to
    generate an example item.  Datasets should customize the item with
    dataset-specific information, e.g.  extracted from metadata files.

    See `the STAC specification
    <https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md>`_
    for information about an item's fields, and
    `Item<https://pystac.readthedocs.io/en/latest/api/pystac.html#pystac.Item>`_ for
    information on the PySTAC class.

    This function should be updated to take all hrefs needed to build the item.
    It is an anti-pattern to assume that related files (e.g. metadata) are in
    the same directory as the primary file.

    Args:
        asset_href (str): The HREF pointing to an asset associated with the item

    Returns:
        Item: STAC Item object
    """
    config = REGION_CONFIGS[region]

    # make sure there is data for the reference_datetime
    # (Alaska only runs the model every three hours)
    if cycle_run_hour := reference_datetime.hour not in config.cycle_run_hours:
        cycle_run_hours = [str(hour) for hour in config.cycle_run_hours]
        raise ValueError(
            f"{cycle_run_hour} is not a valid cycle run hour for {region.value}\n"
            f"Please select one of {' ,'.join(cycle_run_hours)}"
        )

    # set up item
    forecast_datetime = reference_datetime + timedelta(hours=forecast_hour)

    # the forecast_cycle_type defines the available forecast hours and products
    forecast_cycle_type = ForecastCycleType.from_timestamp_and_region(
        reference_datetime=reference_datetime, region=region
    )

    forecast_cycle_type.validate_forecast_hour(forecast_hour)

    item = Item(
        ITEM_ID_FORMAT.format(
            reference_datetime=reference_datetime.strftime("%Y-%m-%dT%H"),
            forecast_hour=forecast_hour,
            region=region.value,
        ),
        geometry=config.geometry_4326,
        bbox=config.bbox_4326,
        datetime=forecast_datetime,
        properties={
            "forecast:reference_time": reference_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
            "forecast:horizon": f"PT{forecast_hour}H",
            "noaa-hrrr:forecast_cycle_type": str(forecast_cycle_type),
            "noaa-hrrr:region": region.value,
        },
    )

    # loop through products and add assets
    for product in forecast_cycle_type.products:
        herbie_metadata = Herbie(
            reference_datetime,
            model=config.herbie_model_id,
            fxx=forecast_hour,
            priority=[cloud_provider.value],
            product=product.value,
            verbose=False,
        )
        assert isinstance(herbie_metadata.grib, str)
        item.assets[product.value] = ITEM_ASSETS[product].create_asset(
            herbie_metadata.grib
        )
        # datacube = DatacubeExtension.ext(
        #     item.assets[product.value],  # add_if_missing=True
        # )

    return item

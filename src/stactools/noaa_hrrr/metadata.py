import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Generator, List, Optional, Type, TypedDict, TypeVar, Union

from parse import Result, parse
from rasterio.crs import CRS
from rasterio.warp import transform_bounds
from stactools.noaa_hrrr.constants import (
    EXTENDED_FORECAST_MAX_HOUR,
    STANDARD_FORECAST_MAX_HOUR,
)

DATA_DIR = Path(__file__).parent / "data"

T = TypeVar("T", bound="StrEnum")


class StrEnum(str, Enum):
    """A string-based enum, that can lookup an enum value from a string.

    This is built-in in Python 3.11 but if you're not there yet...
    """

    @classmethod
    def from_str(cls: Type[T], s: str) -> T:
        """Look up an enum value by string."""
        for value in cls:
            if value == s:
                return value
        raise ValueError(f"Could not parse value from string: {s}")


class CloudProvider(StrEnum):
    """Cloud storage provider sources"""

    azure = "azure"
    aws = "aws"
    google = "google"


class Region(StrEnum):
    """Values for the 'region' parameter in the HRRR hrefs"""

    conus = "conus"
    alaska = "alaska"


class Product(StrEnum):
    """Values for the 'product' parameter in the HRRR hrefs"""

    prs = "prs"
    nat = "nat"
    sfc = "sfc"
    subh = "subh"


class ForecastHourSet(StrEnum):
    """Forecast hour sets

    Either FH00-01 or FH02-48, or FH00 or FH01-18 for sub-hourly.
    The inventory of layers within a GRIB file depends on which set it is in
    """

    # for subhourly
    FH00 = "fh00"
    FH01_18 = "fh01-18"

    # everything else
    FH00_01 = "fh00-01"
    FH02_48 = "fh02-48"

    @classmethod
    def from_forecast_hour_and_product(
        cls, forecast_hour: int, product: Product
    ) -> "ForecastHourSet":
        """Pick the enum value given a forecast hour as an integer"""
        if not 0 <= forecast_hour <= 48:
            raise ValueError("integer must within 0-48")
        if product == Product.subh:
            return cls.FH00 if forecast_hour == 0 else cls.FH01_18
        else:
            return cls.FH00_01 if forecast_hour < 2 else cls.FH02_48

    def generate_forecast_hours(self) -> Generator[int, None, None]:
        forecast_hour_range = [int(i) for i in self.value.replace("fh", "").split("-")]

        if len(forecast_hour_range) == 1:
            yield forecast_hour_range[0]
        else:
            assert len(forecast_hour_range) == 2
            for i in range(forecast_hour_range[0], forecast_hour_range[1] + 1):
                yield i


@dataclass
class ForecastCycleType:
    """Forecast cycle types

    Standard forecasts are generated every hour in CONUS and every three hours in
    Alaska, extended (48 hour) forecasts are generated every six hours.
    """

    type: str

    def __post_init__(self) -> None:
        if self.type not in ["standard", "extended"]:
            raise ValueError("Invalid forecast cycle type")

        self.max_forecast_hour = (
            STANDARD_FORECAST_MAX_HOUR
            if self.type == "standard"
            else EXTENDED_FORECAST_MAX_HOUR
        )

    @classmethod
    def from_timestamp(cls, reference_datetime: datetime) -> "ForecastCycleType":
        """Determine the forecast cycle type based on the timestamp of the cycle run
        hour

        Extended forecasts are generated every six hours starting at hour 00
        """

        extended = reference_datetime.hour % 6 == 0
        return cls("extended" if extended else "standard")

    def generate_forecast_hours(self) -> Generator[int, None, None]:
        """Generate a list of forecast hours for the given forecast cycle type"""

        for i in range(0, self.max_forecast_hour + 1):
            yield i

    def validate_forecast_hour(self, forecast_hour: int) -> None:
        """Check if forecast hour is valid for the forecast type.

        Standard forecast cycles allow 0-18
        Extended forecast cycles allow 0-48
        """
        valid = 0 <= forecast_hour <= self.max_forecast_hour
        if not valid:
            raise ValueError(
                (
                    f"The provided forecast_hour ({forecast_hour}) is not compatible "
                    f"with the forecast cycle type ({str(self)})"
                )
            )

    def __str__(self) -> str:
        return self.type


@dataclass
class ForecastLayerType:
    """Each GRIB file has many forecast layers. Each one represents either a
    real-time forecast (analysis), a point in time forecast, or a summary
    statistic of the forecast for a period of time.
    """

    forecast_layer_type: str
    start_timedelta: Optional[timedelta] = None
    end_timedelta: Optional[timedelta] = None
    statistic_type: Optional[str] = None

    @classmethod
    def from_str(cls, forecast_str: str) -> "ForecastLayerType":
        unit_lookup = {
            "min": "minutes",
            "hour": "hours",
            "day": "days",
        }

        if forecast_str == "anl":
            return cls(
                forecast_layer_type="point_in_time",
                end_timedelta=timedelta(hours=0),
            )

        point_in_time_match = re.match(r"(\d+)\s(hour|min) fcst", forecast_str)
        if point_in_time_match:
            unit = point_in_time_match.group(2)
            end = point_in_time_match.group(1)

            return cls(
                forecast_layer_type="point_in_time",
                end_timedelta=timedelta(**{unit_lookup[unit]: float(end)}),
            )

        summary_match = re.match(
            r"(\d+)-(\d+)\s(hour|min|day)\s(max|ave|min|acc) fcst", forecast_str
        )
        if summary_match:
            start = int(summary_match.group(1))
            end = int(summary_match.group(2))
            unit = summary_match.group(3)
            statistic_type = summary_match.group(4)

            if start == end:
                # special case for FH0, e.g. 0-0 day max
                forecast_layer_type = "periodic_summary"
            elif (start == 0) & (start < end):
                forecast_layer_type = (
                    "periodic_summary"
                    if ((end == 1) & (unit == "hour"))
                    else "cumulative_summary"
                )
            elif (start > 0) & (start < end):
                forecast_layer_type = "periodic_summary"
            else:
                raise ValueError(
                    f"could not parse the forecast_layer_type from '{forecast_str}'"
                )

            return cls(
                forecast_layer_type=forecast_layer_type,
                start_timedelta=timedelta(**{unit_lookup[unit]: start}),
                end_timedelta=timedelta(**{unit_lookup[unit]: end}),
                statistic_type=statistic_type,
            )

        else:
            raise ValueError(
                f"{forecast_str} cannot be parsed into a ForecastLayerType"
            )

    def asset_properties(self) -> dict[str, Union[str, float]]:
        """Write the specific HRRR attributes out in a dictionary to be added to
        asset metadata
        """
        return {
            attr: float(val.total_seconds()) if isinstance(val, timedelta) else val
            for attr, val in self.__dict__.items()
            if val is not None
        }

    def __str__(self) -> str:
        out = self.forecast_layer_type
        if self.statistic_type:
            out = out.replace("summary", self.statistic_type)

        return out


@dataclass
class ProductConfig:
    description: str
    forecast_hour_sets: List[ForecastHourSet]


PRODUCT_CONFIGS = {
    Product.sfc: ProductConfig(
        description="2D surface levels",
        forecast_hour_sets=[ForecastHourSet.FH00_01, ForecastHourSet.FH02_48],
    ),
    Product.prs: ProductConfig(
        description="3D pressure levels",
        forecast_hour_sets=[ForecastHourSet.FH00_01, ForecastHourSet.FH02_48],
    ),
    Product.nat: ProductConfig(
        description="native levels",
        forecast_hour_sets=[ForecastHourSet.FH00_01, ForecastHourSet.FH02_48],
    ),
    Product.subh: ProductConfig(
        description="sub-hourly 2D surface levels",
        forecast_hour_sets=[ForecastHourSet.FH00, ForecastHourSet.FH01_18],
    ),
}


@dataclass
class RegionConfig:
    """Since all items within a single region share the same exact extent and a few
    other properties, store that information as a constant that can be used during STAC
    metadata creation
    """

    item_bbox_proj: tuple[float, float, float, float]
    item_crs: CRS
    cycle_run_hours: List[int]
    grib_url_format: str

    def __post_init__(self) -> None:
        """Get bounding box and geometry in EPSG:4326"""
        self.bbox_4326 = transform_bounds(
            self.item_crs,
            CRS.from_epsg(4326),
            *self.item_bbox_proj,
            densify_pts=3,
        )

    @property
    def geometry_4326(self) -> dict[str, Any]:
        return {
            "type": "Polygon",
            "coordinates": (
                (
                    (self.bbox_4326[2], self.bbox_4326[1]),
                    (self.bbox_4326[2], self.bbox_4326[3]),
                    (self.bbox_4326[0], self.bbox_4326[3]),
                    (self.bbox_4326[0], self.bbox_4326[1]),
                    (self.bbox_4326[2], self.bbox_4326[1]),
                ),
            ),
        }

    def format_grib_url(
        self,
        product: Product,
        reference_datetime: datetime,
        forecast_hour: int,
        idx: bool = False,
    ) -> str:
        url = self.grib_url_format.format(
            product=product.value,
            date=reference_datetime,
            hour=reference_datetime,
            fxx=forecast_hour,
        )

        if idx:
            url += ".idx"

        return url


REGION_CONFIGS = {
    Region.conus: RegionConfig(
        item_bbox_proj=(
            -2699020.142521929,
            -1588806.152556665,
            2697979.857478071,
            1588193.847443335,
        ),
        item_crs=CRS.from_dict(
            {
                "proj": "lcc",
                "lat_0": 38.5,
                "lon_0": -97.5,
                "lat_1": 38.5,
                "lat_2": 38.5,
                "x_0": 0,
                "y_0": 0,
                "R": 6371229,
                "units": "m",
                "no_defs": True,
            }
        ),
        cycle_run_hours=[i for i in range(0, 24)],
        grib_url_format="hrrr.{date:%Y%m%d}/conus/hrrr.t{hour:%H}z.wrf{product}f{fxx:02d}.grib2",
    ),
    Region.alaska: RegionConfig(
        item_bbox_proj=(
            -3426551.0294707343,
            -4100304.1031459086,
            470448.9705292657,
            -1343304.1031459086,
        ),
        item_crs=CRS.from_dict(
            {
                "proj": "stere",
                "lat_0": 90,
                "lat_ts": 60,
                "lon_0": 225,
                "x_0": 0,
                "y_0": 0,
                "R": 6371229,
                "units": "m",
                "no_defs": True,
            }
        ),
        cycle_run_hours=[i for i in range(0, 24, 3)],
        grib_url_format="hrrr.{date:%Y%m%d}/alaska/hrrr.t{hour:%H}z.wrf{product}f{fxx:02d}.ak.grib2",
    ),
}

# override bbox for alaska since rasterio can't handle it (sets xmin to +156)
REGION_CONFIGS[Region.alaska].bbox_4326 = (-174.8849, 41.5960, -115.6988, 76.3464)


@dataclass
class CloudProviderConfig:
    start_date: datetime
    url_base: str


CLOUD_PROVIDER_CONFIGS = {
    CloudProvider.aws: CloudProviderConfig(
        start_date=datetime(year=2014, month=7, day=30),
        url_base="https://noaa-hrrr-bdp-pds.s3.amazonaws.com/",
    ),
    CloudProvider.azure: CloudProviderConfig(
        start_date=datetime(year=2021, month=3, day=21),
        url_base="https://noaahrrr.blob.core.windows.net/hrrr/",
    ),
    CloudProvider.google: CloudProviderConfig(
        start_date=datetime(year=2014, month=7, day=30),
        url_base="https://storage.googleapis.com/high-resolution-rapid-refresh/",
    ),
}


class ItemType(StrEnum):
    """STAC item types"""

    GRIB = "grib"
    INDEX = "index"


class ParsedHref(TypedDict):
    region: Region
    product: Product
    cloud_provider: CloudProvider
    reference_datetime: datetime
    forecast_hour: int


def parse_href(
    href: str,
) -> Union[ParsedHref, None]:
    """Parse an href to get region, product, cloud_provider, product,
    reference_datetime, and forecast hour
    """
    for cloud_provider, cloud_provider_config in CLOUD_PROVIDER_CONFIGS.items():
        if not href.startswith(cloud_provider_config.url_base):
            continue

        # parse the rest of the components from the rest of the href
        key = href.replace(cloud_provider_config.url_base, "")

        for region, region_config in REGION_CONFIGS.items():
            href_key_parsed = parse(region_config.grib_url_format, key)
            if not href_key_parsed:
                continue
            assert isinstance(href_key_parsed, Result)

            url_params = href_key_parsed.named
            reference_datetime = datetime.combine(
                url_params["date"], url_params["hour"]
            )

            return {
                "region": region,
                "product": Product(url_params["product"]),
                "cloud_provider": cloud_provider,
                "reference_datetime": reference_datetime,
                "forecast_hour": url_params["fxx"],
            }

    return None

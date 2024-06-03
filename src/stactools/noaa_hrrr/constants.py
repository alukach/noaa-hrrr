from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, List, Type, TypeVar

from rasterio.crs import CRS
from rasterio.warp import transform_bounds

T = TypeVar("T", bound="StrEnum")

ITEM_ID_FORMAT = "hrrr-{region}-{reference_datetime}-FH{forecast_hour}"
COLLECTION_ID = "noaa-hrrr"

EXTENDED_FORECAST_MAX_HOUR = 48
STANDARD_FORECAST_MAX_HOUR = 18


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


class Variable(StrEnum):
    """Values for the 'variable' parameter in the HRRR hrefs"""

    pressure = "prs"
    native = "nat"
    surface = "sfc"
    sub_hourly = "subh"


@dataclass
class ForecastCycleType:
    """Forecast cycle types"""

    type: str

    def __post_init__(self) -> None:
        if self.type not in ["standard", "extended"]:
            raise ValueError("Invalid forecast cycle type")

        self.max_forecast_hour = (
            STANDARD_FORECAST_MAX_HOUR
            if self.type == "standard"
            else EXTENDED_FORECAST_MAX_HOUR
        )

        # the available variables vary by forecast cycle type
        self.variables = [
            Variable.pressure,
            Variable.native,
            Variable.surface,
        ]

        if self.type == "standard":
            self.variables.append(Variable.sub_hourly)

    @classmethod
    def from_timestamp_and_region(
        cls, reference_datetime: datetime, region: Region
    ) -> "ForecastCycleType":
        """Determine the forecast cycle type based on the timestamp of the cycle run
        hour

        Extended forecasts are generated every six hours starting at hour 00
        """

        extended = reference_datetime.hour % 6 == 0
        return cls("extended" if extended else "standard")

    def generate_forecast_hours(self) -> List[int]:
        """Generate a list of forecast hours for the given forecast cycle type"""
        return list(range(1, self.max_forecast_hour + 1))

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


class ItemType(StrEnum):
    """STAC item types"""

    grib = "grib"
    # datacube = "datacube"


@dataclass
class RegionConfig:
    item_bbox_proj: tuple[float, float, float, float]
    item_crs: CRS
    herbie_model_id: str
    cycle_run_hours: List[int]

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
        herbie_model_id="hrrr",
        cycle_run_hours=[i for i in range(0, 24)],
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
        herbie_model_id="hrrrak",
        cycle_run_hours=[i for i in range(0, 24, 3)],
    ),
}

# override bbox for alaska since rasterio can't handle it (sets xmin to +156)
REGION_CONFIGS[Region.alaska].bbox_4326 = (-174.8849, 41.5960, -115.6988, 76.3464)


# each cloud provider has data starting from a different date
CLOUD_PROVIDER_START_DATES = {
    CloudProvider.azure: datetime(year=2021, month=3, day=21),
    CloudProvider.aws: datetime(year=2014, month=7, day=30),
    CloudProvider.google: datetime(year=2014, month=7, day=30),
}

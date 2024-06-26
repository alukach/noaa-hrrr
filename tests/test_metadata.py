from datetime import datetime

from stactools.noaa_hrrr import metadata
from stactools.noaa_hrrr.stac import create_item


def test_parse_href() -> None:
    # try an AWS href
    parsed_result = metadata.parse_href(
        "https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.20220615/conus/hrrr.t12z.wrfprsf06.grib2"
    )
    assert parsed_result
    assert parsed_result["cloud_provider"] == metadata.CloudProvider.aws
    assert parsed_result["region"] == metadata.Region.conus
    assert parsed_result["product"] == metadata.Product.prs
    assert parsed_result["reference_datetime"] == datetime(
        year=2022, month=6, day=15, hour=12
    )
    assert parsed_result["forecast_hour"] == 6

    # create an item
    _ = create_item(**parsed_result)

    # azure
    parsed_result = metadata.parse_href(
        "https://noaahrrr.blob.core.windows.net/hrrr/hrrr.20240510/conus/hrrr.t12z.wrfsfcf00.grib2"
    )
    assert parsed_result
    assert parsed_result["cloud_provider"] == metadata.CloudProvider.azure
    assert parsed_result["region"] == metadata.Region.conus
    assert parsed_result["product"] == metadata.Product.sfc
    assert parsed_result["reference_datetime"] == datetime(
        year=2024, month=5, day=10, hour=12
    )
    assert parsed_result["forecast_hour"] == 0

    # create an item
    _ = create_item(**parsed_result)

    # try a bad url
    assert not metadata.parse_href(
        "https://noaa-hrrrrrrrr.amazonaws.com/hrrr.20220615/conus/hrrr.t12z.wrfprsf06.grib2"
    )

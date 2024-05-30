import logging
from datetime import datetime

import click
from click import Command, Group
from stactools.noaa_hrrr import stac
from stactools.noaa_hrrr.constants import (
    EXTENDED_FORECAST_MAX_HOUR,
    CloudProvider,
    Region,
)

logger = logging.getLogger(__name__)


def create_noaahrrr_command(cli: Group) -> Command:
    """Creates the stactools-noaa-hrrr command line utility."""

    @cli.group(
        "noaahrrr",
        short_help=("Commands for working with stactools-noaa-hrrr"),
    )
    def noaahrrr() -> None:
        pass

    @noaahrrr.command(
        "create-collection",
        short_help="Creates a STAC collection",
    )
    @click.argument("cloud_provider", type=click.STRING)
    @click.argument("destination", type=click.STRING)
    def create_collection_command(cloud_provider: str, destination: str) -> None:
        """Creates a STAC Collection

        Args:
            destination: An HREF for the Collection JSON
        """
        collection = stac.create_collection(
            cloud_provider=CloudProvider.from_str(cloud_provider)
        )
        collection.set_self_href(destination)
        collection.save_object()

    @noaahrrr.command("create-item", short_help="Create a STAC item")
    @click.argument("reference_datetime", type=click.DateTime(formats=["%Y-%m-%dT%H"]))
    @click.argument("forecast_hour", type=click.IntRange(0, EXTENDED_FORECAST_MAX_HOUR))
    @click.argument("region", type=click.STRING)
    @click.argument("cloud_provider", type=click.STRING)
    @click.argument("destination", type=click.STRING)
    def create_item_command(
        reference_datetime: datetime,
        forecast_hour: int,
        region: str,
        cloud_provider: str,
        destination: str,
    ) -> None:
        """Creates a STAC Item

        Args:
            reference_datetime (datetime): datetime with year, month, day, and hour that
                represents when the forecast was generated (cycle run hour)
            forecast_hour (int): number of hours out from the reference_datetime for the
                forecast
            region (str): either 'conus' or 'alaska'
            cloud_provider (str): one of 'azure', 'aws', or 'google'
        """
        item = stac.create_item(
            reference_datetime=reference_datetime,
            forecast_hour=forecast_hour,
            region=Region.from_str(region),
            cloud_provider=CloudProvider.from_str(cloud_provider),
        )
        item.save_object(dest_href=destination)

    # @noaahrrr.command(
    #     "create-item-collection",
    #     short_help="Create a set of STAC items for a reference datetime",
    # )
    # @click.argument("start_reference_date", type=click.DateTime(formats=["%Y-%m-%d"]))
    # @click.argument("end_reference_date", type=click.DateTime(formats=["%Y-%m-%d"]))
    # @click.argument("region", type=click.STRING)
    # @click.argument("cloud_provider", type=click.STRING)
    # @click.argument("destination", type=click.STRING)
    # def create_item_collection_command(
    #     start_reference_date: datetime,
    #     end_reference_date: datetime,
    #     region: str,
    #     cloud_provider: str,
    #     destination: str,
    # ):
    #     """Create collection of STAC items for a date range"""
    #
    #     return

    return noaahrrr

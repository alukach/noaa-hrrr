import stactools.core
from stactools.cli.registry import Registry
from stactools.noaa_hrrr.inventory import load_idx, read_idx
from stactools.noaa_hrrr.metadata import CloudProvider, Product, Region, parse_href
from stactools.noaa_hrrr.stac import create_collection, create_item

__all__ = [
    "CloudProvider",
    "Product",
    "Region",
    "create_collection",
    "create_item",
    "load_idx",
    "parse_href",
    "read_idx",
]

stactools.core.use_fsspec()


def register_plugin(registry: Registry) -> None:
    from stactools.noaa_hrrr import commands

    registry.register_subcommand(commands.create_noaahrrr_command)

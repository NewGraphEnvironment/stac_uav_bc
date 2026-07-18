#!/usr/bin/env python
# Create STAC items for new COGs and append them to the prod collection.json.
# Additive-only: tifs whose item id already exists in the collection are skipped,
# so re-running is safe and existing collection links are never duplicated.
# Scriptable replacement for the per-run chunks in stac_create_item.qmd.
#
# Run inside the titiler conda env (has pystac + rio_stac):
#   conda run -n titiler python scripts/stac_create_item.py \
#     mackenzie/pine/2026/6971_pine_oxbox_hwy97S/odm_orthophoto/odm_orthophoto.tif \
#     mackenzie/pine/2026/6971_pine_oxbox_hwy97S/odm_dem/dtm.tif
#
# Positional args are tif paths relative to --base (the local prod stac tree).
# After creating items, upload to S3 (scripts/s3_sync.R) then register into the
# API database with scripts/config/stac_register_item.sh (it prints the command).
import argparse
import datetime
import pathlib
import sys

import pystac
import rasterio
import rio_stac

def flight_datetime(path):
    # ODM propagates the capture time from the image EXIF into TIFFTAG_DATETIME,
    # but in EXIF colon format (2026:07:14 14:49:57+00:00) which rio_stac cannot
    # parse — it warns and falls back to processing time (issue #9).
    with rasterio.open(path) as src:
        tag = src.tags().get("TIFFTAG_DATETIME")
    if not tag:
        return None
    date, _, time = tag.partition(" ")
    return datetime.datetime.fromisoformat(f"{date.replace(':', '-')}T{time}")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("tifs", nargs="+", help="tif paths relative to --base")
    p.add_argument("--base", default="/Users/airvine/Projects/gis/uav_imagery/stac/prod/imagery_uav_bc")
    p.add_argument("--s3-url", default="https://imagery-uav-bc.s3.amazonaws.com/")
    args = p.parse_args()

    base = pathlib.Path(args.base)
    path_collection = base / "collection.json"
    collection = pystac.Collection.from_file(str(path_collection))
    collection.set_self_href(f"{args.s3_url}collection.json")

    existing = {l.href.rsplit("/", 1)[-1].removesuffix(".json") for l in collection.get_links("item")}

    made = []
    for rel in args.tifs:
        path_item = base / rel
        if not path_item.exists():
            sys.exit(f"missing: {path_item}")
        href_item = path_item.relative_to(base)
        item_id = "-".join(href_item.parts[:-1] + (path_item.stem,))
        if item_id in existing:
            print(f"SKIP (already in collection): {item_id}")
            continue

        dt = flight_datetime(path_item)
        if dt is None:
            print(f"WARNING: no TIFFTAG_DATETIME in {rel}; item will get processing time")
        item = rio_stac.stac.create_stac_item(
            str(path_item),
            id=item_id,
            input_datetime=dt,
            asset_media_type="image/tiff; application=geotiff; profile=cloud-optimized",
            asset_name="image",
            asset_href=f"{args.s3_url}{href_item}",
            with_proj=True,
            collection=collection.id,
            collection_url=collection.get_self_href(),
            asset_roles=["data"],
        )
        collection.add_item(item)
        item.set_self_href(f"{args.s3_url}{href_item.parent}/{item_id}.json")
        item.validate()
        path_json = path_item.parent / f"{item_id}.json"
        item.save_object(dest_href=str(path_json))
        made.append(str(path_json))
        print(f"CREATED: {item_id}")

    collection.save_object(dest_href=str(path_collection))
    print(f"collection saved ({len(collection.get_links('item'))} item links): {path_collection}")
    if made:
        print("\nafter uploading to S3, register with:")
        print("  scripts/config/stac_register_item.sh \\\n    " + " \\\n    ".join(made))

if __name__ == "__main__":
    main()

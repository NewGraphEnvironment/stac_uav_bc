#!/usr/bin/env python
# Create or rebuild STAC items for the imagery-uav-bc-prod catalog.
#
# Registry-driven: data/sites.csv is the source of truth for stream names,
# watershed groups, site ids, aliases (#16). Item geometry is the true
# valid-data outline from gdal_footprint (bbox remains the raster extent).
#
# Modes:
#   item_create.py <tifs relative to base>   additive — skip ids already in the collection
#   item_create.py --rebuild                 regenerate EVERY item from the prod tree +
#                                            sites.csv, rebuild collection links, stamp
#                                            the version (from git tag or --version)
#
# Run inside the titiler conda env (pystac + rio_stac + rasterio):
#   conda run -n titiler python scripts/item_create.py --rebuild
#
# After building: item_validate.py → S3 sync → config/item_register.sh →
# config/collection_register.sh (or just scripts/catalogue_release.sh).
import argparse
import csv
import datetime
import json
import pathlib
import subprocess
import sys
import tempfile

import pystac
import rasterio
import rio_stac

REPO = pathlib.Path(__file__).resolve().parent.parent
VERSION_EXT = "https://stac-extensions.github.io/version/v1.2.0/schema.json"
PRODUCT_LABEL = {"odm_orthophoto": "orthophoto", "dtm": "DTM", "dsm": "DSM", "ortho": "orthophoto"}

def flight_datetime(path, path_year):
    # ODM propagates capture time from image EXIF into TIFFTAG_DATETIME but in
    # EXIF colon format (2026:07:14 14:49:57+00:00), which rio_stac cannot
    # parse (#9). Fallback for tag-less legacy tifs: Jan 1 of the path year.
    with rasterio.open(path) as src:
        tag = src.tags().get("TIFFTAG_DATETIME")
    if not tag:
        return datetime.datetime(int(path_year), 1, 1, tzinfo=datetime.timezone.utc)
    date, _, time = tag.partition(" ")
    return datetime.datetime.fromisoformat(f"{date.replace(':', '-')}T{time}")

def footprint(path):
    # True valid-data outline; -ovr 2 reads only overviews (<1 s/COG).
    # Trace + simplify in the native CRS (metre tolerance — passing -t_srs
    # EPSG:4326 here would make -simplify operate in degrees and empty the
    # geometry), then reproject to WGS84 for the item.
    import rasterio.warp
    with tempfile.TemporaryDirectory() as td:
        out = pathlib.Path(td) / "fp.geojson"
        cmd = ["gdal_footprint", "-ovr", "2", "-simplify", "10",
               "-max_points", "unlimited", str(path), str(out)]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            # inputs without overviews (not expected in the prod tree)
            subprocess.run([c for c in cmd if c not in ("-ovr", "2")], check=True, capture_output=True)
        geom = json.loads(out.read_text())["features"][0]["geometry"]
    with rasterio.open(path) as src:
        return rasterio.warp.transform_geom(src.crs, "EPSG:4326", geom)

def load_registry(path):
    reg = {}
    for r in csv.DictReader(open(path)):
        reg[(r["region"], r["watershed"], r["year"], r["item"])] = r
    return reg

def registry_props(row):
    mapping = [
        ("nge:region", "region"), ("nge:watershed_group", "watershed"),
        ("nge:wsg_code", "watershed_group_code"), ("nge:site_id", "aggregated_crossings_id"),
        ("nge:stream_name", "stream_name"), ("nge:stream_name_02", "stream_name_02"),
        ("nge:stream_name_03", "stream_name_03"), ("nge:alias", "alias"),
        ("nge:project", "project"),
    ]
    return {k: row[col].strip() for k, col in mapping if row.get(col, "").strip()}

def build_item(path_item, base, s3_url, collection, registry):
    href_item = path_item.relative_to(base)
    parts = href_item.parts
    item_id = "-".join(parts[:-1] + (path_item.stem,))
    row = registry.get(parts[:4])
    if row and row.get("published", "true").strip().lower() == "false":
        print(f"SKIP (published=false in sites.csv): {item_id}")
        return None

    props = registry_props(row) if row else {}
    stream = props.get("nge:stream_name", parts[3])
    product = PRODUCT_LABEL.get(path_item.stem, path_item.stem)
    props["title"] = f"{stream} — {parts[2]} {product}"

    item = rio_stac.stac.create_stac_item(
        str(path_item),
        id=item_id,
        input_datetime=flight_datetime(path_item, parts[2]),
        properties=props,
        asset_media_type="image/tiff; application=geotiff; profile=cloud-optimized",
        asset_name="image",
        asset_href=f"{s3_url}{href_item}",
        with_proj=True,
        collection=collection.id,
        collection_url=collection.get_self_href(),
        asset_roles=["data"],
    )
    item.geometry = footprint(path_item)
    item.set_self_href(f"{s3_url}{href_item.parent}/{item_id}.json")
    item.validate()
    return item

def stamp_version(collection, version):
    if VERSION_EXT not in collection.stac_extensions:
        collection.stac_extensions.append(VERSION_EXT)
    collection.extra_fields["version"] = version

def git_version():
    try:
        return subprocess.check_output(
            ["git", "-C", str(REPO), "describe", "--tags", "--abbrev=0"], text=True
        ).strip().lstrip("v")
    except subprocess.CalledProcessError:
        return "0.0.0"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("tifs", nargs="*", help="tif paths relative to --base (additive mode)")
    p.add_argument("--rebuild", action="store_true", help="regenerate every item from the prod tree")
    p.add_argument("--base", default="/Users/airvine/Projects/gis/uav_imagery/stac/prod/imagery_uav_bc")
    p.add_argument("--s3-url", default="https://imagery-uav-bc.s3.amazonaws.com/")
    p.add_argument("--sites", default=str(REPO / "data" / "sites.csv"))
    p.add_argument("--version", default=None, help="override version stamp (default: latest git tag)")
    args = p.parse_args()
    if bool(args.tifs) == args.rebuild:
        sys.exit("pass tif paths OR --rebuild")

    base = pathlib.Path(args.base)
    registry = load_registry(args.sites)
    collection = pystac.Collection.from_file(str(base / "collection.json"))
    collection.set_self_href(f"{args.s3_url}collection.json")

    if args.rebuild:
        tifs = sorted(t for t in base.rglob("*.tif") if not t.name.endswith(".original.tif"))
        collection.clear_items()
        built = 0
        for t in tifs:
            item = build_item(t, base, args.s3_url, collection, registry)
            if item:
                collection.add_item(item)
                item.save_object(dest_href=str(t.parent / f"{item.id}.json"))
                built += 1
        stamp_version(collection, args.version or git_version())
        collection.save_object(dest_href=str(base / "collection.json"))
        print(f"REBUILD: {built} items from {len(tifs)} tifs; collection v{collection.extra_fields['version']}, "
              f"{len(collection.get_links('item'))} links")
        return

    existing = {l.href.rsplit("/", 1)[-1].removesuffix(".json") for l in collection.get_links("item")}
    made = []
    for rel in args.tifs:
        path_item = base / rel
        if not path_item.exists():
            sys.exit(f"missing: {path_item}")
        item_id = "-".join(path_item.relative_to(base).parts[:-1] + (path_item.stem,))
        if item_id in existing:
            print(f"SKIP (already in collection): {item_id}")
            continue
        item = build_item(path_item, base, args.s3_url, collection, registry)
        if item:
            collection.add_item(item)
            item.save_object(dest_href=str(path_item.parent / f"{item_id}.json"))
            made.append(str(path_item.parent / f"{item_id}.json"))
            print(f"CREATED: {item_id}")
    collection.save_object(dest_href=str(base / "collection.json"))
    print(f"collection saved ({len(collection.get_links('item'))} item links)")
    if made:
        print("\nafter uploading to S3, register with:")
        print("  scripts/config/item_register.sh \\\n    " + " \\\n    ".join(made))

if __name__ == "__main__":
    main()

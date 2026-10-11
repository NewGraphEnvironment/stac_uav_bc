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
#   item_create.py --selftest                the gate: registry mapping, title, prefix
#                                            guards (no network, no tifs; non-zero on failure)
#
# Run inside the titiler conda env (pystac + rio_stac + rasterio):
#   conda run -n titiler python scripts/item_create.py --rebuild
#
# After building: stacs validate/audit → S3 sync → stacs register → stacs verify,
# via scripts/stacs.sh with stacs.toml (or just scripts/catalogue_release.sh).
import argparse
import csv
import datetime
import json
import pathlib
import subprocess
import sys
import tempfile
from urllib.parse import unquote

import pystac
import rasterio
import rio_stac

REPO = pathlib.Path(__file__).resolve().parent.parent
VERSION_EXT = "https://stac-extensions.github.io/version/v1.2.0/schema.json"
PRODUCT_LABEL = {"odm_orthophoto": "orthophoto", "dtm": "DTM", "dsm": "DSM", "ortho": "orthophoto"}
# Every field prefix an item may carry (#38). Each names what its fields describe:
# proj: from rio_stac; fwa: the BC Freshwater Atlas; bcfishpass: its crossing ids;
# uav: this catalogue's registry judgment; newgraph: New Graph's own regions, aliases
# and projects. None has a published schema yet: crate publishes one only once a
# second catalogue writes the prefix. Anything else (an old nge: key) is refused.
FIELD_PREFIXES = {"proj", "fwa", "bcfishpass", "uav", "newgraph"}

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

# (item property, sites.csv column). The registry's `watershed` column is the tree's
# directory slug, already in the item id, so it is not carried; the atlas's name for
# the group is `watershed_group_name` (scripts/sites_fill-wsg_name.py, #38).
REGISTRY_FIELDS = [
    ("newgraph:region", "region"),
    ("fwa:watershed_group_code", "watershed_group_code"),
    ("fwa:watershed_group_name", "watershed_group_name"),
    ("bcfishpass:aggregated_crossings_id", "aggregated_crossings_id"),
    ("uav:stream_name", "stream_name"), ("uav:stream_name_02", "stream_name_02"),
    ("uav:stream_name_03", "stream_name_03"),
    ("newgraph:alias", "alias"), ("newgraph:project", "project"),
]

def registry_props(row):
    return {k: row[col].strip() for k, col in REGISTRY_FIELDS if (row.get(col) or "").strip()}

def registry_problems(row):
    # The group name is filled from the code by a separate step; a row whose code
    # was added without it would publish fwa:watershed_group_code with no name.
    # A name left after its code was cleared would publish a name a filter on the
    # code cannot find. A stale name beside a changed code is registry_conflicts' job.
    code = (row.get("watershed_group_code") or "").strip()
    name = (row.get("watershed_group_name") or "").strip()
    if code and not name:
        return ["watershed_group_code set but watershed_group_name blank: "
                "run scripts/sites_fill-wsg_name.py --write"]
    if name and not code:
        return ["watershed_group_name set but watershed_group_code blank: "
                "run scripts/sites_fill-wsg_name.py --write"]
    return []

def registry_conflicts(registry):
    # An atlas code has one name, so a code carrying two names across the registry
    # is a row whose code changed without the fill script being re-run. Caught when
    # the new code is shared with another row; otherwise the fill script's report
    # finds it. Not checked the other way: a name is NOT unique in the atlas
    # (SALM and SALR are both "Salmon River", measured 2026-10-10).
    by_code = {}
    for r in registry.values():
        code = (r.get("watershed_group_code") or "").strip()
        name = (r.get("watershed_group_name") or "").strip()
        if code and name:
            by_code.setdefault(code, set()).add(name)
    return [f"code {c} has names {sorted(n)}" for c, n in sorted(by_code.items()) if len(n) > 1]

def item_title(props, dir_name, year, stem):
    stream = props.get("uav:stream_name", dir_name)
    product = PRODUCT_LABEL.get(stem, stem)
    # Repeat flights of one site (e.g. a before/after culvert replacement) share
    # stream name and year, so the alias is what separates their titles (#22).
    alias = props.get("newgraph:alias", "")
    return f"{stream} ({alias}) — {year} {product}" if alias else f"{stream} — {year} {product}"

def fields_undeclared(doc):
    # Property and asset field keys whose prefix is not in FIELD_PREFIXES. Keys with
    # no prefix are core STAC (datetime, title, href, ...).
    keys = list(doc.get("properties", {}))
    for asset in doc.get("assets", {}).values():
        keys += list(asset)
    return sorted({k for k in keys if ":" in k and k.split(":", 1)[0] not in FIELD_PREFIXES})

def tree_undeclared(base):
    # Item JSONs already in the prod tree that carry a field outside FIELD_PREFIXES.
    # Items built before #38 carry nge: keys; only a full rebuild replaces them.
    out = {}
    for f in sorted(base.rglob("*.json")):
        if f.name == "collection.json":
            continue
        bad = fields_undeclared(json.loads(f.read_text()))
        if bad:
            out[str(f.relative_to(base))] = bad
    return out

def build_item(path_item, base, s3_url, collection, registry):
    href_item = path_item.relative_to(base)
    parts = href_item.parts
    item_id = "-".join(parts[:-1] + (path_item.stem,))
    row = registry.get(parts[:4])
    if row and row.get("published", "true").strip().lower() == "false":
        print(f"SKIP (published=false in sites.csv): {item_id}")
        return None

    problems = registry_problems(row) if row else []
    if problems:
        sys.exit(f"REFUSED: sites.csv row for {item_id}: {'; '.join(problems)}")
    props = registry_props(row) if row else {}
    props["title"] = item_title(props, parts[3], parts[2], path_item.stem)

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
    bad = fields_undeclared(item.to_dict())
    if bad:
        sys.exit(f"REFUSED: {item_id} carries field(s) outside FIELD_PREFIXES: {bad}")
    item.validate()
    return item

def collection_add(collection, item):
    # Collection.add_item() re-homes the item under pystac's best-practice layout,
    # <collection dir>/<id>/<id>.json, overwriting the self href build_item set. Those
    # keys never exist on S3 (the sync mirrors the tree), so every collection item link
    # and item self link was a 403 until this restored the tree path (#35).
    href = item.get_self_href()
    collection.add_item(item)
    item.set_self_href(href)

def links_check(base, s3_url):
    # Gate: every item link in the saved collection.json must name a file under the
    # prod tree, so the S3 sync publishes something at exactly that URL. stacs fetches
    # item bodies through these links; a broken one fails registration far from here.
    c = json.loads((base / "collection.json").read_text())
    hrefs = [l["href"] for l in c.get("links", []) if l.get("rel") == "item"]
    broken = [h for h in hrefs
              if not h.startswith(s3_url) or not (base / unquote(h[len(s3_url):])).is_file()]
    if not hrefs:
        sys.exit("LINKS FAILED: collection.json has no item links")
    # stacs refuses an id linked twice, but only after the sync has published it,
    # and additive mode never rewrites an existing link: refuse it here instead.
    ids = [unquote(h.rsplit("/", 1)[-1]).removesuffix(".json") for h in hrefs]
    repeated = sorted({i for i in ids if ids.count(i) > 1})
    if repeated:
        sys.exit(f"LINKS FAILED: {len(repeated)} id(s) linked more than once, e.g. {repeated[:3]}")
    if broken:
        print(f"LINKS FAILED: {len(broken)}/{len(hrefs)} item link(s) name no file under {base}:",
              file=sys.stderr)
        for h in broken[:5]:
            print(f"    {h}", file=sys.stderr)
        sys.exit("links written before #35 are only rewritten by a full rebuild: "
                 "run item_create.py --rebuild (or scripts/catalogue_release.sh)")
    print(f"links OK: {len(hrefs)} item links resolve under {base}")

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

def _selftest():
    fails = []
    def check(ok, what):
        if not ok:
            fails.append(what)

    row = {"region": "skeena", "watershed": "peace_arm", "watershed_group_code": "BULK",
           "watershed_group_name": "Bulkley River", "aggregated_crossings_id": "198285",
           "stream_name": "Pedley Creek", "stream_name_02": "Byman Creek",
           "stream_name_03": " Gosnell Creek ", "alias": "moose pre-replacement",
           "project": "", "published": "true", "name_source": "pscis", "notes": "x"}
    want = {"newgraph:region": "skeena", "fwa:watershed_group_code": "BULK",
            "fwa:watershed_group_name": "Bulkley River",
            "bcfishpass:aggregated_crossings_id": "198285",
            "uav:stream_name": "Pedley Creek", "uav:stream_name_02": "Byman Creek",
            "uav:stream_name_03": "Gosnell Creek", "newgraph:alias": "moose pre-replacement"}
    got = registry_props(row)
    check(got == want, f"registry_props: got {got}, want {want}")
    check(not any(k.startswith("nge:") for k in got), "registry_props still writes nge:")
    check("newgraph:project" not in got, "a blank cell was carried")
    check(registry_props({**row, "project": "p1"}).get("newgraph:project") == "p1",
          "project not carried as newgraph:project")
    # A row read before the column existed has no watershed_group_name key at all.
    check("fwa:watershed_group_name" not in registry_props(
        {k: v for k, v in row.items() if k != "watershed_group_name"}),
        "a missing column was carried")
    check(registry_problems(row) == [], f"registry_problems on a full row: {registry_problems(row)}")
    check(registry_problems({**row, "watershed_group_name": ""}) != [],
          "a code without its name passes")
    check(registry_problems({**row, "watershed_group_code": "", "watershed_group_name": ""}) == [],
          "a row with no code is refused")
    check(registry_problems({**row, "watershed_group_code": ""}) != [],
          "a name without its code passes")
    other = {**row, "item": "other"}
    morr = {**row, "item": "morr", "watershed_group_code": "MORR", "watershed_group_name": "Morice River"}
    check(registry_conflicts({1: row, 2: other, 3: morr}) == [], "conflict on a consistent registry")
    check(registry_conflicts({1: row, 2: {**other, "watershed_group_code": "MORR"}, 3: morr}) != [],
          "a changed code beside its stale name passes")
    salmon = [{**row, "item": c, "watershed_group_code": c, "watershed_group_name": "Salmon River"}
              for c in ("SALM", "SALR")]
    check(registry_conflicts(dict(enumerate(salmon))) == [],
          "two atlas groups sharing a name are refused")
    check(not fields_undeclared({"properties": got}),
          f"registry_props writes undeclared prefixes: {fields_undeclared({'properties': got})}")

    t = item_title(got, "198285_pedley", "2026", "odm_orthophoto")
    check(t == "Pedley Creek (moose pre-replacement) — 2026 orthophoto", f"title: {t!r}")
    t = item_title({}, "198285_pedley", "2026", "dtm")
    check(t == "198285_pedley — 2026 DTM", f"title without registry: {t!r}")

    ok = {"properties": {"datetime": "x", "title": "x", "proj:epsg": 1, **want},
          "assets": {"image": {"href": "x", "type": "x", "roles": ["data"]}}}
    check(fields_undeclared(ok) == [], f"guard refuses a valid item: {fields_undeclared(ok)}")
    check(fields_undeclared({"properties": {"nge:region": "x"}}) == ["nge:region"],
          "guard passes nge:region")
    check(fields_undeclared({"assets": {"image": {"raster:bands": []}}}) == ["raster:bands"],
          "guard passes an undeclared asset field")

    with tempfile.TemporaryDirectory() as td:
        base = pathlib.Path(td)
        (base / "a" / "b").mkdir(parents=True)
        (base / "collection.json").write_text(json.dumps({"properties": {"nge:x": 1}}))
        (base / "a" / "b" / "new.json").write_text(json.dumps(ok))
        check(tree_undeclared(base) == {}, f"tree guard refuses a clean tree: {tree_undeclared(base)}")
        (base / "a" / "old.json").write_text(json.dumps({"properties": {"nge:stream_name": "x"}}))
        check(tree_undeclared(base) == {"a/old.json": ["nge:stream_name"]},
              f"tree guard misses a pre-#38 item: {tree_undeclared(base)}")

    if fails:
        print(f"ITEM SELFTEST FAILED: {len(fails)} check(s)", file=sys.stderr)
        for f in fails:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("ITEM SELFTEST PASS: registry mapping, title and prefix guards")
    return 0

def main():
    p = argparse.ArgumentParser()
    p.add_argument("tifs", nargs="*", help="tif paths relative to --base (additive mode)")
    p.add_argument("--rebuild", action="store_true", help="regenerate every item from the prod tree")
    p.add_argument("--selftest", action="store_true", help="run the gate and exit")
    p.add_argument("--base", default="/Users/airvine/Projects/gis/uav_imagery/stac/prod/imagery_uav_bc")
    p.add_argument("--s3-url", default="https://imagery-uav-bc.s3.amazonaws.com/")
    p.add_argument("--sites", default=str(REPO / "data" / "sites.csv"))
    p.add_argument("--version", default=None, help="override version stamp (default: latest git tag)")
    args = p.parse_args()
    if args.selftest:
        sys.exit(_selftest())
    if bool(args.tifs) == args.rebuild:
        sys.exit("pass tif paths OR --rebuild")

    base = pathlib.Path(args.base)
    registry = load_registry(args.sites)
    conflicts = registry_conflicts(registry)
    if conflicts:
        sys.exit(f"REFUSED: {args.sites} watershed group code/name pairs disagree: {conflicts}; "
                 "run scripts/sites_fill-wsg_name.py --write")
    collection = pystac.Collection.from_file(str(base / "collection.json"))
    collection.set_self_href(f"{args.s3_url}collection.json")
    # The file's root link is the published S3 URL, so without this add_item()
    # downloads the bucket's collection.json and makes THAT the root of the
    # collection and every item: a network dependency, and the published copy's
    # fields in place of the one being built (#35).
    collection.set_root(collection)

    if args.rebuild:
        tifs = sorted(t for t in base.rglob("*.tif") if not t.name.endswith(".original.tif"))
        collection.clear_items()
        built = 0
        for t in tifs:
            item = build_item(t, base, args.s3_url, collection, registry)
            if item:
                collection_add(collection, item)
                item.save_object(dest_href=str(t.parent / f"{item.id}.json"))
                built += 1
        # A full rebuild is the one place that holds every item, so recompute the
        # extent here — nothing else did, and a collection can otherwise advertise
        # an extent that excludes its own items (#22).
        collection.update_extent_from_items()
        stamp_version(collection, args.version or git_version())
        collection.save_object(dest_href=str(base / "collection.json"))
        bbox = collection.extent.spatial.bboxes[0]
        print(f"REBUILD: {built} items from {len(tifs)} tifs; collection v{collection.extra_fields['version']}, "
              f"{len(collection.get_links('item'))} links; bbox {[round(v, 5) for v in bbox]}")
        links_check(base, args.s3_url)
        return

    # Refuse before writing anything: the links already in collection.json have to
    # resolve too, and only a rebuild rewrites them.
    links_check(base, args.s3_url)
    # Likewise items built under the old field names (#38): an additive run would
    # publish renamed items beside them, and a filter on either name would find half.
    stale = tree_undeclared(base)
    if stale:
        f, keys = next(iter(stale.items()))
        sys.exit(f"REFUSED: {len(stale)} item JSON(s) in {base} carry fields outside "
                 f"FIELD_PREFIXES (e.g. {f}: {keys[:3]}); only a full rebuild replaces them. "
                 "Release first: NEWS entry naming the renamed fields, git tag vX.Y.Z, then "
                 "scripts/catalogue_release.sh. That release also publishes any tif already "
                 "copied into the prod tree (by the run that hit this), so its sites.csv row "
                 "must exist first.")
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
            collection_add(collection, item)
            item.save_object(dest_href=str(path_item.parent / f"{item_id}.json"))
            made.append(str(path_item.parent / f"{item_id}.json"))
            # The same tif given twice (`dir` and `dir/`, an overlapping glob) would
            # otherwise be built and linked twice.
            existing.add(item_id)
            print(f"CREATED: {item_id}")
    collection.save_object(dest_href=str(base / "collection.json"))
    print(f"collection saved ({len(collection.get_links('item'))} item links)")
    links_check(base, args.s3_url)
    if made:
        print("\nafter syncing the prod tree to S3, register with:")
        print("  scripts/stacs.sh register --config stacs.toml --mode drift")

if __name__ == "__main__":
    main()

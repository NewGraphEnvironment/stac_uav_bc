#!/usr/bin/env python
# Validate every STAC item JSON + the collection in the prod tree (pystac
# schema validation). Nonzero exit on any failure — the QA gate before S3
# sync/registration, adopted from the stac_dem_bc pattern.
#
#   conda run -n titiler python scripts/item_validate.py [--base DIR]
import argparse
import json
import pathlib
import sys

import pystac

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="/Users/airvine/Projects/gis/uav_imagery/stac/prod/imagery_uav_bc")
    args = p.parse_args()
    base = pathlib.Path(args.base)

    ok, failed = 0, []
    for path in sorted(base.rglob("*.json")):
        d = json.loads(path.read_text())
        try:
            if path.name == "collection.json":
                pystac.Collection.from_dict(d).validate()
            elif d.get("type") == "Feature":
                pystac.Item.from_dict(d).validate()
            else:
                continue
            ok += 1
        except Exception as e:
            failed.append((path.relative_to(base), str(e).splitlines()[0][:100]))

    print(f"valid: {ok}")
    if failed:
        print(f"FAILED: {len(failed)}", file=sys.stderr)
        for rel, err in failed:
            print(f"  {rel}: {err}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# Fill data/sites.csv `watershed_group_name` from `watershed_group_code`, using the
# BC Freshwater Atlas's own names (#38). Items carry the pair as
# fwa:watershed_group_code + fwa:watershed_group_name. The registry's `watershed`
# column is the S3 tree's directory slug (`peace_arm`), not the atlas name, which is
# why the name is looked up rather than derived from it.
#
# Asks the public fwapg REST API (features.hillcrestgeo.ca, as stream_resolve.py
# does) once per distinct code. Prints what it would change; writes only with
# --write. A code the atlas does not know stops the run before anything is written.
# A filled cell that disagrees with the atlas is reported and overwritten on --write.
#
# Usage:
#   python3 scripts/sites_fill-wsg_name.py            # report
#   python3 scripts/sites_fill-wsg_name.py --write    # fill the column in place
import argparse
import csv
import io
import json
import pathlib
import sys
import urllib.parse
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
API = ("https://features.hillcrestgeo.ca/fwa/collections/"
       "whse_basemapping.fwa_watershed_groups_poly/items.json")
TIMEOUT = 30  # a hung fetch must fail loud rather than stall the run
COL, AFTER = "watershed_group_name", "watershed_group_code"


def atlas_name(code):
    q = urllib.parse.urlencode({"watershed_group_code": code,
                                "properties": "watershed_group_code,watershed_group_name"})
    with urllib.request.urlopen(f"{API}?{q}", timeout=TIMEOUT) as r:
        feats = json.load(r)["features"]
    names = {f["properties"]["watershed_group_name"] for f in feats
             if f["properties"]["watershed_group_code"] == code}
    return names.pop() if len(names) == 1 else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sites", default=str(REPO / "data" / "sites.csv"))
    p.add_argument("--write", action="store_true", help="fill the column in place")
    args = p.parse_args()

    raw = pathlib.Path(args.sites).read_bytes()
    # The registry is written CRLF, unquoted; write back in that shape or the
    # diff becomes every line.
    newline = "\r\n" if b"\r\n" in raw else "\n"
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""))
    fields = list(reader.fieldnames)
    rows = list(reader)
    if COL not in fields:
        fields.insert(fields.index(AFTER) + 1, COL)

    codes = sorted({r[AFTER].strip() for r in rows if r[AFTER].strip()})
    names = {c: atlas_name(c) for c in codes}
    unknown = [c for c, n in names.items() if n is None]
    if unknown:
        sys.exit(f"REFUSED: the atlas has no single watershed group for {unknown}; nothing written")

    changed = 0
    for r in rows:
        code = r[AFTER].strip()
        want = names.get(code, "")
        have = (r.get(COL) or "").strip()
        if have != want:
            print(f"{r['region']}/{r['watershed']}/{r['year']}/{r['item']}: "
                  f"{code or '(no code)'} {have!r} -> {want!r}")
            changed += 1
        r[COL] = want
    blank = [r["item"] for r in rows if not r[AFTER].strip()]
    if blank:
        print(f"no watershed_group_code, so no name: {blank}")
    print(f"{len(codes)} codes, {changed} row(s) to change")

    if args.write and (changed or COL not in reader.fieldnames):
        out = io.StringIO(newline="")
        w = csv.DictWriter(out, fieldnames=fields, lineterminator=newline)
        w.writeheader()
        w.writerows(rows)
        pathlib.Path(args.sites).write_bytes(out.getvalue().encode("utf-8"))
        print(f"written: {args.sites}")


if __name__ == "__main__":
    main()

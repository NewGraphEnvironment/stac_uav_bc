# /// script
# requires-python = ">=3.11"
# dependencies = ["laspy[lazrs]>=2.5", "pyproj>=3.6", "numpy"]
# ///
"""Header + first-chunk read of UAV point clouds. Paths on stdin, JSON lines out."""
import json, sys
import numpy as np
import laspy
from pyproj import CRS, Transformer

for line in sys.stdin:
    p = line.strip()
    if not p:
        continue
    rec = {"path": p}
    try:
        with laspy.open(p) as f:
            h = f.header
            rec.update(
                n=int(h.point_count), fmt=int(h.point_format.id),
                version=str(h.version), mins=list(map(float, h.mins)),
                maxs=list(map(float, h.maxs)),
                software=h.generating_software.strip("\x00 "),
                date=str(h.creation_date) if h.creation_date else None,
                dims=list(h.point_format.dimension_names),
            )
            crs = None
            try:
                crs = h.parse_crs()
            except Exception as e:
                rec["crs_err"] = str(e)[:200]
            if crs is not None:
                rec["crs"] = crs.to_string()
                rec["crs_name"] = crs.name
                rec["epsg"] = crs.to_epsg()
                rec["vert"] = [c.name for c in crs.sub_crs_list] if crs.is_compound else None
                t = Transformer.from_crs(crs.to_2d() if crs.is_compound else crs, 4326, always_xy=True)
                xs = [h.mins[0], h.maxs[0], h.mins[0], h.maxs[0]]
                ys = [h.mins[1], h.mins[1], h.maxs[1], h.maxs[1]]
                lon, lat = t.transform(xs, ys)
                rec["bbox_ll"] = [min(lon), min(lat), max(lon), max(lat)]
            # classes and returns from the first chunk only (cheap)
            for pts in f.chunk_iterator(2_000_000):
                c = np.asarray(pts.classification)
                u, k = np.unique(c, return_counts=True)
                rec["cls_first2M"] = {int(a): int(b) for a, b in zip(u, k)}
                rn = np.asarray(pts.number_of_returns)
                rec["multi_return_frac"] = float((rn > 1).mean())
                break
    except Exception as e:
        rec["err"] = f"{type(e).__name__}: {e}"[:300]
    print(json.dumps(rec), flush=True)

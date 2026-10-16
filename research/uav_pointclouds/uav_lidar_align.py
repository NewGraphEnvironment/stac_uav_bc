# /// script
# requires-python = ">=3.11"
# dependencies = ["laspy[lazrs]>=2.5", "pyproj>=3.6", "numpy", "rasterio>=1.3"]
# ///
"""Shift + tilt of each UAV cloud's ground against the LidarBC 1 m DEM.

argv: headers.jsonl overlap.json out.jsonl
Model: z_uav - z_dem(X + dx, Y + dy) = a + b*(X - Xm) + c*(Y - Ym) + residual.
(dx, dy) searched coarse (+-20 m, 1 m) then fine (+-1 m, 0.25 m); for each, the
plane is fitted robustly (least squares, trim |r| > 3 NMAD, refit) and the score is
the residual NMAD. Ground = class 2 (ODM); MME files are unclassified, so all points.
"""
import json, os, sys
import numpy as np
import pyproj.network
pyproj.network.set_network_enabled(True)
import laspy, rasterio
from rasterio.windows import from_bounds
from pyproj import CRS, Transformer

rng = np.random.default_rng(1)
H = {json.loads(l)["path"]: json.loads(l) for l in open(sys.argv[1])}
O = json.load(open(sys.argv[2]))
out = open(sys.argv[3], "w")
geoid = Transformer.from_crs("EPSG:4979", "EPSG:4326+6647", always_xy=True)
PAD = 25


def nmad(a):
    return float(1.4826 * np.median(np.abs(a - np.median(a))))


def plane_fit(xc, yc, dz):
    A = np.c_[np.ones_like(xc), xc, yc]
    coef, *_ = np.linalg.lstsq(A, dz, rcond=None)
    r = dz - A @ coef
    k = np.abs(r - np.median(r)) < 3 * max(nmad(r), 0.05)
    coef, *_ = np.linalg.lstsq(A[k], dz[k], rcond=None)
    r = dz - A @ coef
    return coef, r


for o in O:
    dems = [d for d in o["dem"] if d["dem"] and "albers10k2m" not in d["dem"]]
    if not dems:
        continue
    h = H[o["path"]]
    rec = {"path": o["path"]}
    try:
        yr = max(d["dt"][:4] for d in dems)
        dems = [d for d in dems if d["dt"][:4] == yr]
        rec["dem_year"] = yr
        las = laspy.read(o["path"])
        cls = np.asarray(las.classification)
        g = cls == 2
        rec["ground_kind"] = "class2" if g.any() else "all_points"
        idx = np.flatnonzero(g if g.any() else np.ones(len(cls), bool))
        idx = rng.choice(idx, min(len(idx), 200_000), replace=False)
        x, y, z = np.asarray(las.x)[idx], np.asarray(las.y)[idx], np.asarray(las.z)[idx]
        src = CRS.from_user_input(h["crs"])
        lon0, lat0 = Transformer.from_crs(src, 4326, always_xy=True).transform(x.mean(), y.mean())
        rec["lonlat"] = [lon0, lat0]
        _, _, Hg = geoid.transform(lon0, lat0, 0.0)
        rec["geoid_N"] = float(-Hg)
        tiles = []
        for d in dems:
            with rasterio.open(d["dem"]) as r:
                dst = CRS.from_user_input(r.crs.to_wkt())
                t = Transformer.from_crs(src, dst.to_2d() if dst.is_compound else dst, always_xy=True)
                X, Y = t.transform(x, y)
                inb = (X > r.bounds.left) & (X < r.bounds.right) & (Y > r.bounds.bottom) & (Y < r.bounds.top)
                if not inb.any():
                    continue
                w = from_bounds(X[inb].min() - PAD, Y[inb].min() - PAD, X[inb].max() + PAD, Y[inb].max() + PAD,
                                r.transform).round_offsets().round_lengths()
                a = r.read(1, window=w, boundless=True, fill_value=np.nan).astype("float64")
                a[(a < -100) | (a > 5000)] = np.nan
                tiles.append((a, r.window_transform(w), X, Y))
                rec["dem_crs"] = r.crs.to_string()
        Xm, Ym = x.mean(), y.mean()

        def sample(dx, dy, sel=slice(None)):
            zz = np.full(len(x), np.nan)[sel]
            for a, wt, X, Y in tiles:
                c = np.floor((X[sel] + dx - wt.c) / wt.a).astype(int)
                rr = np.floor((Y[sel] + dy - wt.f) / wt.e).astype(int)
                ok = (c >= 0) & (c < a.shape[1]) & (rr >= 0) & (rr < a.shape[0]) & np.isnan(zz)
                zz[ok] = a[rr[ok], c[ok]]
            return zz

        z0 = sample(0, 0)
        ok0 = np.isfinite(z0)
        rec["n_compared"] = int(ok0.sum())
        if ok0.sum() < 2000:
            raise ValueError("too few overlapping points")
        dz0 = z[ok0] - z0[ok0]
        rec["dz_median_raw"] = float(np.median(dz0)); rec["dz_nmad_raw"] = nmad(dz0)
        sub = rng.choice(np.flatnonzero(ok0), min(int(ok0.sum()), 40_000), replace=False)
        xc, yc = (x - Xm) / 100.0, (y - Ym) / 100.0  # per 100 m

        def score(dx, dy, sel):
            zz = sample(dx, dy, sel)
            m = np.isfinite(zz)
            if m.sum() < 0.8 * len(zz):
                return np.inf, None, None
            coef, r = plane_fit(xc[sel][m], yc[sel][m], z[sel][m] - zz[m])
            return nmad(r), coef, r

        best = (np.inf, 0.0, 0.0)
        for dx in np.arange(-20, 20.01, 1.0):
            for dy in np.arange(-20, 20.01, 1.0):
                s, _, _ = score(dx, dy, sub)
                if s < best[0]:
                    best = (s, dx, dy)
        b0 = best
        for dx in np.arange(b0[1] - 1, b0[1] + 1.01, 0.25):
            for dy in np.arange(b0[2] - 1, b0[2] + 1.01, 0.25):
                s, _, _ = score(dx, dy, sub)
                if s < best[0]:
                    best = (s, float(dx), float(dy))
        s, coef, r = score(best[1], best[2], np.flatnonzero(ok0))
        # shift-only residual at the same (dx, dy), for comparison
        zz = sample(best[1], best[2]); m = np.isfinite(zz)
        rec.update(shift_dx=best[1], shift_dy=best[2], at_bound=bool(max(abs(best[1]), abs(best[2])) >= 19.9),
                   plane_a=float(coef[0]), tilt_x_m_per_100m=float(coef[1]), tilt_y_m_per_100m=float(coef[2]),
                   tilt_m_per_100m=float(np.hypot(coef[1], coef[2])), centre=[float(Xm), float(Ym)],
                   nmad_shift_only=nmad(z[m] - zz[m]), nmad_shift_tilt=float(s),
                   abs_res_p90=float(np.percentile(np.abs(r - np.median(r)), 90)),
                   extent_m=[float(np.ptp(x)), float(np.ptp(y))])
    except Exception as e:
        rec["err"] = f"{type(e).__name__}: {e}"[:300]
    out.write(json.dumps(rec) + "\n"); out.flush()
    print(o["path"][-60:], {k: (round(v, 2) if isinstance(v, float) else v) for k, v in rec.items()
                             if k in ("dz_median_raw", "shift_dx", "shift_dy", "tilt_m_per_100m", "nmad_shift_only", "nmad_shift_tilt", "err")},
          file=sys.stderr, flush=True)

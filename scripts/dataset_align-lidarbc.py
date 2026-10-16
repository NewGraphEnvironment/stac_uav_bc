#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["laspy[lazrs]>=2.5", "pyproj>=3.6", "numpy>=1.24", "rasterio>=1.3"]
# ///
# Fit each dataset to the LidarBC 1 m DEM: horizontal shift, vertical offset,
# tilt, and the misfit left (#41). No flight used ground control, so every
# dataset sits where the drone's GPS put it: a median of 9 m from LidarBC
# vertically and 3.5 m horizontally (research/uav_pointclouds.md). The fit is
# recorded, not applied: the rasters stay as published, and item_create.py
# carries the row on the dataset's items as alignment: fields.
#
# Model, as the research probe fitted it (research/uav_pointclouds/uav_lidar_align.py):
#   z_uav(x, y) - z_dem(x + dx, y + dy) = surface(x - centre_x, y - centre_y)
# surface is a plane a + b*u + c*v (u, v in units of 100 m) or a quadratic with
# u*u, u*v, v*v added. So, in the dataset's own CRS:
#   corrected (x, y) = published (x, y) + (shift_x, shift_y)
#   corrected z      = published z - surface(x - centre_x, y - centre_y)
# The DEM tiles are NAD83(CSRS) UTM and the clouds WGS 84 UTM; the fit goes
# through PROJ's default operation between them (about 1 m here), and the shift
# is carried back into the dataset's CRS, so it is consistent with how QGIS,
# GDAL and R reproject the raster onto LidarBC.
#
# ODM ground points (class 2) are compared with the newest LidarBC delivery that
# covers at least half of them, sampled bilinearly. The shift is searched on a
# grid (+-20 m by 1 m, then +-1 m by 0.25 m), the surface at each shift fitted
# by Huber least squares, the score the NMAD of the residual. The search runs
# on two disjoint random samples of the points and the two must agree: a flat
# site has no horizontal signal and would otherwise return a guess. The misfit
# is the NMAD over every ground point compared. (A held-out split was tried and
# dropped: with 10^5 points and 3 or 6 parameters it cannot catch overfitting,
# and a spatial split biased the search, because both samples then came from
# the same half of the ground.)
#
# A mask limits which points the fit uses: `slope` drops ground steeper than
# SLOPE_MAX_DEG on the LidarBC DEM (where a horizontal error reads as a vertical
# one); `open` drops points under canopy, read off the dataset's own DSM - DTM.
# The misfit is always scored on every point, so masks are judged on the same
# points as no mask; misfit_masked_m is the score on the masked points alone.
# --trial fits every model x mask on each dataset in one pass and writes the
# grid; the settled defaults are --model and --mask.
#
# Output: one row per dataset in data/alignment_lidarbc.csv, keyed like
# data/sites.csv. `status` is fitted, no_cloud, no_reference or
# refused:<reason>; a row that is not fitted carries no numbers, so nothing
# downstream can read a guess. A run merges its rows into the table by key and
# writes after every dataset, so an interrupted run keeps what it did. Rows
# record the cloud's point count and date; --check reports rows whose cloud has
# since changed and published datasets with no row.
#
# uv resolves the dependencies from the header above (no conda env has laspy):
#   uv run scripts/dataset_align-lidarbc.py --selftest         # the gate: no network, no laz
#   uv run scripts/dataset_align-lidarbc.py <project-dir>...   # these datasets (raw-tree dirs, as dataset_publish.sh takes them)
#   uv run scripts/dataset_align-lidarbc.py                    # every published dataset
#   uv run scripts/dataset_align-lidarbc.py --check            # table against the trees; non-zero on drift
#   uv run scripts/dataset_align-lidarbc.py --trial grid.csv   # every model x mask per dataset
import argparse
import csv
import datetime
import json
import math
import pathlib
import sys
import tempfile
import urllib.request
import zlib

import numpy as np

REPO = pathlib.Path(__file__).resolve().parent.parent
ROOT = pathlib.Path("/Users/airvine/Projects/gis/uav_imagery")  # raw tree (dataset_publish.sh's ROOT)
PROD = ROOT / "stac" / "prod" / "imagery_uav_bc"  # published tree (item_create.py's --base)
TABLE = REPO / "data" / "alignment_lidarbc.csv"
API = "https://images.a11s.one/search"
COLLECTION = "stac-elevation-bc"
SEARCH_LIMIT = 200  # the API pages past this; a flight under more tiles than this is not expected
LAZ = pathlib.Path("odm_georeferencing") / "odm_georeferenced_model.laz"
DTM = pathlib.Path("odm_dem") / "dtm.tif"
DSM = pathlib.Path("odm_dem") / "dsm.tif"
TIMEOUT = 60  # s, on every fetch: a hung read must fail loud, not stall the run
KEY = ["region", "watershed", "year", "item"]
COLUMNS = KEY + ["status", "reference", "reference_crs", "dem_ids", "model", "mask", "shift_x_m",
                 "shift_y_m", "shift_spread_m", "offset_m", "tilt_m_per_100m", "surface", "centre_x",
                 "centre_y", "dz_raw_m", "misfit_m", "misfit_masked_m", "points", "coverage",
                 "outlier_frac", "cloud_points", "cloud_date", "run_date"]
TRIAL_COLUMNS = KEY + ["model", "mask", "status", "reference", "shift_x_m", "shift_y_m", "shift_spread_m",
                       "offset_m", "tilt_m_per_100m", "misfit_m", "misfit_masked_m", "points", "outlier_frac"]
MODELS = ("plane", "quadratic")
MASKS = ("none", "slope", "open", "slope+open")
SLOPE_MAX_DEG = 15.0  # LidarBC ground steeper than this is left out of a `slope` fit
OPEN_MAX_M = 0.5  # DSM - DTM above this is canopy, left out of an `open` fit
SEARCH_M, COARSE_STEP, FINE_M, FINE_STEP = 20.0, 1.0, 1.0, 0.25
# m between the two samples' shifts; beyond it the shift is not determined. Measured
# over the 47 datasets that fit (2026-10-16): 41 agree within 1.0 m, four between 1.0
# and 1.3 m, then nothing until 5.5 m and 8.5 m, which the research also called
# undetermined (2.6 m apart on the moose post flight). 2 m sits in that gap.
MAX_SHIFT_SPREAD = 2.0
MIN_POINTS = 2000  # fewer ground points over the DEM than this is no fit
MIN_COVERAGE = 0.5  # share of the ground points the DEM must cover, or the tilt is extrapolated
SAMPLE, SEARCH_SAMPLE = 200_000, 20_000  # points read per cloud; points per sample scoring each shift
PAD = 25  # m of DEM read beyond the points: room for the shift search
DTM_SAMPLE, DTM_TOL = 2000, 0.1  # the dataset's own DTM must sit on its cloud's ground


class Refused(Exception):
    """A dataset the table must not describe with numbers; str(e) is the reason."""


def nmad(a):
    return float(1.4826 * np.median(np.abs(a - np.median(a))))


def design(u, v, model):
    cols = [np.ones_like(u), u, v]
    if model == "quadratic":
        cols += [u * u, u * v, v * v]
    return np.column_stack(cols)


def surface_fit(u, v, dz, model):
    """Huber least squares (k = 1.345 robust scales), so what ODM classed as
    ground under vegetation, and real change since the LiDAR, weigh little.
    Returns the coefficients and the share of points past 3 scales."""
    A = design(u, v, model)
    coef, *_ = np.linalg.lstsq(A, dz, rcond=None)
    for _ in range(5):
        r = dz - A @ coef
        dev = np.abs(r - np.median(r))
        s = max(nmad(r), 0.05)
        w = np.sqrt(np.minimum(1.0, 1.345 * s / np.maximum(dev, 1e-9)))
        coef, *_ = np.linalg.lstsq(A * w[:, None], dz * w, rcond=None)
    r = dz - A @ coef
    return coef, float(np.mean(np.abs(r - np.median(r)) > 3 * max(nmad(r), 0.05)))


def surface_at(coef, u, v, model):
    return design(u, v, model) @ coef


def sample_tiles(tiles, X, Y):
    """Bilinear DEM value at (X, Y), cell values at cell centres; NaN off the
    tiles or beside nodata. The first tile holding a value wins."""
    z = np.full(len(X), np.nan)
    for a, t in tiles:
        fc, fr = (X - t.c) / t.a - 0.5, (Y - t.f) / t.e - 0.5
        c0, r0 = np.floor(fc).astype(int), np.floor(fr).astype(int)
        ok = (c0 >= 0) & (c0 + 1 < a.shape[1]) & (r0 >= 0) & (r0 + 1 < a.shape[0]) & np.isnan(z)
        c0, r0, wc, wr = c0[ok], r0[ok], (fc - np.floor(fc))[ok], (fr - np.floor(fr))[ok]
        z[ok] = (a[r0, c0] * (1 - wc) * (1 - wr) + a[r0, c0 + 1] * wc * (1 - wr)
                 + a[r0 + 1, c0] * (1 - wc) * wr + a[r0 + 1, c0 + 1] * wc * wr)
    return z


def fit_alignment(x, y, z, X, Y, tiles, model, rng, keep=None):
    """x, y, z: ground points in the cloud's CRS; X, Y: the same points in the tiles'
    CRS (the same arrays when the two agree); tiles: [(array, affine)]; keep: the
    points a mask lets the fit use (every point when None). The shift comes back
    in the tiles' CRS, the surface in the cloud's. Raises Refused."""
    z0 = sample_tiles(tiles, X, Y)
    over = np.flatnonzero(np.isfinite(z0))
    coverage = len(over) / len(x)
    if len(over) < MIN_POINTS:
        raise Refused(f"too_few_points:{len(over)}")
    if coverage < MIN_COVERAGE:
        raise Refused(f"low_coverage:{coverage:.2f}")
    dz_raw = float(np.median(z[over] - z0[over]))
    xc, yc = float(np.mean(x[over])), float(np.mean(y[over]))
    u, v = (x - xc) / 100.0, (y - yc) / 100.0
    fit_i = over
    if keep is not None:
        fit_i = fit_i[keep[fit_i]]
        if len(fit_i) < MIN_POINTS // 2:
            raise Refused(f"mask_too_few:{len(fit_i)}")

    def score(dx, dy, sel):
        zz = sample_tiles(tiles, X[sel] + dx, Y[sel] + dy)
        m = np.isfinite(zz)
        if m.sum() < 0.8 * len(sel):
            return np.inf, None, None
        s = sel[m]
        coef, outliers = surface_fit(u[s], v[s], z[s] - zz[m], model)
        return nmad(z[s] - zz[m] - surface_at(coef, u[s], v[s], model)), coef, outliers

    def search(sel):
        best = (np.inf, 0.0, 0.0)
        steps = np.arange(-SEARCH_M, SEARCH_M + COARSE_STEP / 2, COARSE_STEP)
        for dx in steps:
            for dy in steps:
                s, _, _ = score(dx, dy, sel)
                if s < best[0]:
                    best = (s, float(dx), float(dy))
        cx, cy = best[1], best[2]
        fine = np.arange(-FINE_M, FINE_M + FINE_STEP / 2, FINE_STEP)
        for dx in np.clip(cx + fine, -SEARCH_M, SEARCH_M):
            for dy in np.clip(cy + fine, -SEARCH_M, SEARCH_M):
                s, _, _ = score(dx, dy, sel)
                if s < best[0]:
                    best = (s, float(dx), float(dy))
        return best[1], best[2]

    # Two disjoint samples search independently. A flat site scores every shift
    # alike, and the two then land apart: that is no measurement.
    perm = rng.permutation(fit_i)
    n = min(SEARCH_SAMPLE, len(perm) // 2)
    (ax, ay), (bx, by) = search(perm[:n]), search(perm[n:2 * n])
    dx, dy = (ax + bx) / 2, (ay + by) / 2
    # Both samples on the edge of the window: the shift lies beyond it, and that
    # is the diagnosis even though along the edge the two drift apart. One on
    # the edge and the other not, or the two apart anywhere: no measurement.
    edge = SEARCH_M - FINE_STEP
    if max(abs(ax), abs(ay)) > edge and max(abs(bx), abs(by)) > edge:
        raise Refused(f"shift_at_bound:{dx},{dy}")
    spread = math.hypot(ax - bx, ay - by)
    if spread > MAX_SHIFT_SPREAD:
        raise Refused(f"shift_unstable:{spread:.1f}")
    if max(abs(ax), abs(ay), abs(bx), abs(by)) > edge:
        raise Refused(f"shift_at_bound:{dx},{dy}")
    _, coef, outliers = score(dx, dy, fit_i)
    if coef is None:
        raise Refused("fit_points_off_dem")
    # Scored over every point compared, masked or not, so every model and mask
    # is judged on the same ground.
    zz = sample_tiles(tiles, X[over] + dx, Y[over] + dy)
    m = np.isfinite(zz)
    s = over[m]
    res = z[s] - zz[m] - surface_at(coef, u[s], v[s], model)
    masked = None if keep is None else (nmad(res[keep[s]]) if keep[s].sum() >= MIN_POINTS // 4 else math.nan)
    return {"shift_x": dx, "shift_y": dy, "shift_spread": spread, "surface": [float(c) for c in coef],
            "centre": (xc, yc), "dz_raw": dz_raw, "misfit": nmad(res), "misfit_masked": masked,
            "coverage": coverage, "outliers": outliers, "points": int(len(s))}


def describe_fit(row, fit, shift_x, shift_y):
    coef = fit["surface"]
    row.update(status="fitted", shift_x_m=round(shift_x, 2), shift_y_m=round(shift_y, 2),
               shift_spread_m=round(fit["shift_spread"], 2), offset_m=round(coef[0], 3),
               tilt_m_per_100m=round(math.hypot(coef[1], coef[2]), 3),
               surface=json.dumps([round(c, 4) for c in coef]),
               centre_x=round(fit["centre"][0], 2), centre_y=round(fit["centre"][1], 2),
               dz_raw_m=round(fit["dz_raw"], 2), misfit_m=round(fit["misfit"], 3),
               misfit_masked_m="" if fit["misfit_masked"] is None else round(fit["misfit_masked"], 3),
               points=fit["points"], coverage=round(fit["coverage"], 2), outlier_frac=round(fit["outliers"], 3))
    return row


def shift_back(fit, t):
    """The shift was found in the tiles' CRS (NAD83(CSRS), maybe the next UTM zone):
    carry it back into the cloud's through the centre, exact for a translation."""
    xc, yc = fit["centre"]
    Xc, Yc = t.transform(xc, yc)
    xs, ys = t.transform(Xc + fit["shift_x"], Yc + fit["shift_y"], direction="INVERSE")
    return float(xs - xc), float(ys - yc)


# --- masks --------------------------------------------------------------------

def slope_tiles(tiles):
    out = []
    for a, t in tiles:
        gy, gx = np.gradient(a, abs(t.e), t.a)
        out.append((np.degrees(np.arctan(np.hypot(gx, gy))), t))
    return out


def canopy_height(proj_raw, proj_prod, x, y):
    """DSM - DTM of the dataset at (x, y), read at about 1 m: the published COGs
    when they exist (their overviews make this cheap), else the raw ODM rasters."""
    import rasterio
    from rasterio.enums import Resampling
    d = proj_prod if (proj_prod / DSM).is_file() and (proj_prod / DTM).is_file() else proj_raw
    arrs = []
    for name in (DSM, DTM):
        with rasterio.open(str(d / name)) as r:
            f = max(1, round(1.0 / r.res[0]))
            shape = (max(1, r.height // f), max(1, r.width // f))
            a = r.read(1, out_shape=shape, resampling=Resampling.average, masked=True)
            arrs.append((a.filled(np.nan).astype("float64"),
                         r.transform * r.transform.scale(r.width / shape[1], r.height / shape[0])))
    (dsm, t), (dtm, t2) = arrs
    if dsm.shape != dtm.shape or t != t2:
        raise Refused("dsm_dtm_grids_differ")
    return sample_tiles([(dsm - dtm, t)], x, y)


def mask_points(mask, x, y, X, Y, tiles, proj_raw, proj_prod):
    """True for the points a fit under `mask` may use."""
    keep = np.ones(len(x), bool)
    if "slope" in mask:
        s = sample_tiles(slope_tiles(tiles), X, Y)
        keep &= np.isfinite(s) & (s <= SLOPE_MAX_DEG)
    if "open" in mask:
        h = canopy_height(proj_raw, proj_prod, x, y)
        keep &= np.isfinite(h) & (h <= OPEN_MAX_M)
    return None if mask == "none" else keep


# --- IO: the cloud, its DTM, the reference, the table ------------------------

def cloud_header(path):
    import laspy
    with laspy.open(path) as f:
        return int(f.header.point_count), str(f.header.creation_date or "")


def load_cloud(path, rng):
    """ODM ground points (class 2), at most SAMPLE of them, and the cloud's CRS.
    A cloud with no ground class is refused: fitting every point fits canopy
    (the research's unclassified clouds misfit by 3.3 m)."""
    import laspy
    las = laspy.read(path)
    g = np.flatnonzero(np.asarray(las.classification) == 2)
    if len(g) == 0:
        raise Refused("no_ground_class")
    if len(g) > SAMPLE:
        g = rng.choice(g, SAMPLE, replace=False)
    crs = las.header.parse_crs()
    if crs is None:
        raise Refused("cloud_has_no_crs")
    return np.asarray(las.x)[g], np.asarray(las.y)[g], np.asarray(las.z)[g], crs


def check_dtm(path, x, y, z, crs, rng):
    """The items carry the fit, the cloud is what was fitted: the dataset's DTM must
    be the same placement (the research measured 0.00 m at two flights)."""
    import rasterio
    with rasterio.open(path) as r:
        if r.crs.to_epsg() != crs.to_epsg():
            raise Refused(f"dtm_crs_differs:{r.crs.to_epsg()}!={crs.to_epsg()}")
        i = rng.choice(len(x), min(len(x), DTM_SAMPLE), replace=False)
        v = np.array([s[0] for s in r.sample(zip(x[i], y[i]))], float)
        ok = np.isfinite(v) & (v > -1000)
        if r.nodata is not None:
            ok &= v != r.nodata
    if ok.sum() < DTM_SAMPLE // 4:
        raise Refused(f"dtm_off_cloud:{int(ok.sum())}")
    d = float(np.median(v[ok] - z[i][ok]))
    if abs(d) > DTM_TOL:
        raise Refused(f"dtm_cloud_disagree:{d:.2f}")


def bbox_ll(x, y, crs):
    from pyproj import Transformer
    t = Transformer.from_crs(crs, 4326, always_xy=True)
    lon, lat = t.transform([x.min(), x.max(), x.min(), x.max()], [y.min(), y.min(), y.max(), y.max()])
    return [float(min(lon)), float(min(lat)), float(max(lon)), float(max(lat))]


def search_dems(bbox):
    """LidarBC DEM tiles over bbox as [(year, [(delivery, id, href), ...])], newest year first."""
    body = json.dumps({"collections": [COLLECTION], "bbox": bbox, "limit": SEARCH_LIMIT}).encode()
    req = urllib.request.Request(API, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        feats = json.load(r)["features"]
    if len(feats) >= SEARCH_LIMIT:
        raise RuntimeError(f"{len(feats)} items over {bbox}: past the search page, tiles would be missed")
    # Only LidarBC deliveries: the same collection holds the provincial 10 km
    # Albers mosaics, which are undated, far coarser, and carry no delivery.
    years = {}
    for f in feats:
        d = f["properties"].get("lidarbc:delivery")
        if d and "dem" in f["assets"]:
            years.setdefault(d.rsplit("/", 1)[-1], []).append((d, f["id"], f["assets"]["dem"]["href"]))
    return [(y, sorted(years[y])) for y in sorted(years, reverse=True)]


def load_tiles(hrefs, x, y, crs):
    """Windowed reads of the DEM tiles under the points. Returns tiles [(array,
    affine)], the points in the tiles' CRS, that transformer, and the CRS."""
    import rasterio
    from pyproj import CRS, Transformer
    from rasterio.windows import from_bounds
    tiles, X, Y, t, tile_crs = [], None, None, None, None
    with rasterio.Env(GDAL_HTTP_TIMEOUT=TIMEOUT, GDAL_HTTP_CONNECTTIMEOUT=30, GDAL_HTTP_MAX_RETRY=3,
                      GDAL_HTTP_RETRY_DELAY=2, GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        for href in hrefs:
            with rasterio.open(href) as r:
                dst = CRS.from_user_input(r.crs.to_wkt())
                if dst.is_compound:
                    dst = dst.to_2d()
                if t is None:
                    t, tile_crs = Transformer.from_crs(crs, dst, always_xy=True), dst
                    X, Y = t.transform(x, y)
                elif dst != tile_crs:
                    raise Refused("dem_tiles_mixed_crs")
                inb = (X > r.bounds.left) & (X < r.bounds.right) & (Y > r.bounds.bottom) & (Y < r.bounds.top)
                if not inb.any():
                    continue
                w = from_bounds(X[inb].min() - PAD, Y[inb].min() - PAD, X[inb].max() + PAD,
                                Y[inb].max() + PAD, r.transform).round_offsets().round_lengths()
                a = r.read(1, window=w, boundless=True, fill_value=np.nan).astype("float64")
                if r.nodata is not None:
                    a[a == r.nodata] = np.nan
                a[(a < -100) | (a > 5000)] = np.nan  # LidarBC's undeclared -3.4e38 nodata
                tiles.append((a, r.window_transform(w)))
    return tiles, X, Y, t, tile_crs


def reference_for(years, x, y, crs):
    """The newest delivery that covers the flight; an older one when the newest ends
    partway across it. Returns (dems, tiles, X, Y, transformer, tile crs)."""
    short = None
    for _, dems in years:
        tiles, X, Y, t, tile_crs = load_tiles([h for _, _, h in dems], x, y, crs)
        over = int(np.isfinite(sample_tiles(tiles, X, Y)).sum())
        if over >= MIN_POINTS and over / len(x) >= MIN_COVERAGE:
            return dems, tiles, X, Y, t, tile_crs
        short = short or Refused(f"low_coverage:{over / len(x):.2f}" if over >= MIN_POINTS
                                 else f"too_few_points:{over}")
    raise short


def prepare(key, root, rng):
    """The cloud, checked against its DTM, and its reference. Returns (ctx, status):
    ctx is None when the status is final (no_cloud, no_reference, refused:*)."""
    proj = root.joinpath(*key)
    if not (proj / LAZ).is_file():
        return None, "no_cloud", {}
    header = dict(zip(("cloud_points", "cloud_date"), cloud_header(proj / LAZ)))
    try:
        x, y, z, crs = load_cloud(proj / LAZ, rng)
        check_dtm(proj / DTM, x, y, z, crs, rng)
        years = search_dems(bbox_ll(x, y, crs))
        if not years:
            return None, "no_reference", header
        dems, tiles, X, Y, t, tile_crs = reference_for(years, x, y, crs)
    except Refused as e:
        return None, f"refused:{e}", header
    ref = {"reference": ";".join(sorted({d for d, _, _ in dems})),
           "reference_crs": f"EPSG:{tile_crs.to_epsg()}" if tile_crs.to_epsg() else tile_crs.name,
           "dem_ids": ";".join(i for _, i, _ in dems)}
    return {"x": x, "y": y, "z": z, "X": X, "Y": Y, "tiles": tiles, "t": t, "proj": proj}, ref, header


def dataset_rng(key):
    return np.random.default_rng(zlib.crc32("/".join(key).encode()))  # per dataset, so order does not matter


def dataset_row(key, root, prod, model, mask):
    rng = dataset_rng(key)
    row = dict(zip(KEY, key), status="", reference="", reference_crs="", dem_ids="", model=model, mask=mask,
               run_date=datetime.date.today().isoformat())
    ctx, status, header = prepare(key, root, rng)
    row.update(header)
    if ctx is None:
        row["status"] = status
        return row
    row.update(status)
    try:
        keep = mask_points(mask, ctx["x"], ctx["y"], ctx["X"], ctx["Y"], ctx["tiles"], ctx["proj"], prod.joinpath(*key))
        fit = fit_alignment(ctx["x"], ctx["y"], ctx["z"], ctx["X"], ctx["Y"], ctx["tiles"], model, rng, keep)
    except Refused as e:
        row["status"] = f"refused:{e}"
        return row
    return describe_fit(row, fit, *shift_back(fit, ctx["t"]))


def trial_rows(key, root, prod):
    """One row per model x mask for the dataset, every arm on the same cloud,
    reference, search samples and scored points. Each arm starts from the random
    state a production fit would, so the plane/none arm is the table's row."""
    rng = dataset_rng(key)
    ctx, status, _ = prepare(key, root, rng)
    state = rng.bit_generator.state
    base = dict(zip(KEY, key))
    if ctx is None:
        return [dict(base, status=status)]
    base.update(reference=status["reference"])
    keeps = {}
    for mask in MASKS:
        try:
            keeps[mask] = mask_points(mask, ctx["x"], ctx["y"], ctx["X"], ctx["Y"], ctx["tiles"], ctx["proj"], prod.joinpath(*key))
        except Refused as e:
            keeps[mask] = e
    rows = []
    for model in MODELS:
        for mask in MASKS:
            r = dict(base, model=model, mask=mask)
            try:
                if isinstance(keeps[mask], Refused):
                    raise keeps[mask]
                arm_rng = np.random.default_rng()
                arm_rng.bit_generator.state = state
                fit = fit_alignment(ctx["x"], ctx["y"], ctx["z"], ctx["X"], ctx["Y"], ctx["tiles"], model,
                                    arm_rng, keeps[mask])
                describe_fit(r, fit, *shift_back(fit, ctx["t"]))
            except Refused as e:
                r["status"] = f"refused:{e}"
            rows.append(r)
    return rows


def read_table(path):
    if not path.is_file():
        return {}
    with open(path, newline="") as f:
        return {tuple(r[k] for k in KEY): r for r in csv.DictReader(f)}


def write_table(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        for k in sorted(rows):
            w.writerow({c: rows[k].get(c, "") for c in COLUMNS})


def write_trial(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TRIAL_COLUMNS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in TRIAL_COLUMNS})


def published_keys(prod):
    # Every dataset with a tif in the published tree, the two ortho-only ones included.
    return sorted({p.relative_to(prod).parts[:4] for p in prod.rglob("*.tif")
                   if not p.name.endswith(".original.tif")})


def project_key(arg, root):
    try:
        rel = pathlib.Path(arg).resolve().relative_to(root)
    except ValueError:
        sys.exit(f"ERROR: {arg} is not under {root}")
    if len(rel.parts) != 4:
        sys.exit(f"ERROR: {arg}: expected <region>/<watershed>/<year>/<item> under {root}")
    return rel.parts


def check_table(rows, root, prod):
    """Rows whose cloud changed since the fit, and published datasets with no row."""
    drift = [f"{'/'.join(k)}: published, no row" for k in published_keys(prod) if k not in rows]
    for k, r in rows.items():
        laz = root.joinpath(*k) / LAZ
        if not laz.is_file():
            if r["status"] != "no_cloud":
                drift.append(f"{'/'.join(k)}: cloud gone, row says {r['status']}")
            continue
        n, d = cloud_header(laz)
        if (str(n), d) != (r["cloud_points"], r["cloud_date"]):
            drift.append(f"{'/'.join(k)}: cloud is {n} points of {d}, row fitted {r['cloud_points']} of {r['cloud_date']}")
    return drift


def misfit_line(misfit):
    q = np.percentile(misfit, [25, 50, 75])
    return (f"median {q[1]:.2f} m (quartiles {q[0]:.2f}-{q[2]:.2f}), "
            f"{sum(m <= 1 for m in misfit)} within 1 m, {sum(m <= 0.5 for m in misfit)} within 0.5 m")


def summary(rows):
    counts = {}
    for r in rows.values():
        s = r["status"].split(":")[0]
        counts[s] = counts.get(s, 0) + 1
    misfit = [float(r["misfit_m"]) for r in rows.values() if r["status"] == "fitted"]
    print(f"{len(rows)} rows: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    if misfit:
        print(f"misfit of {len(misfit)} fitted: {misfit_line(misfit)}")


def trial_summary(rows):
    """Each arm on its own, then paired against plane/none on the datasets both fitted."""
    arms = {}
    for r in rows:
        if r.get("status") == "fitted":
            arms.setdefault((r["model"], r["mask"]), {})[tuple(r[k] for k in KEY)] = float(r["misfit_m"])
    base = arms.get(("plane", "none"), {})
    print(f"{'model':10s} {'mask':11s} {'n':>3s}  misfit over every point compared"
          f"{'':30s} paired with plane/none: median difference, arms lower")
    for (model, mask), m in sorted(arms.items(), key=lambda kv: (MODELS.index(kv[0][0]), MASKS.index(kv[0][1]))):
        both = [k for k in m if k in base]
        d = np.array([m[k] - base[k] for k in both])
        paired = (f"{np.median(d):+.3f} m, {int((d < 0).sum())}/{len(both)}" if len(both) else "-")
        print(f"{model:10s} {mask:11s} {len(m):3d}  {misfit_line(list(m.values())):62s} {paired}")


# --- the gate -----------------------------------------------------------------

def _selftest():
    from affine import Affine
    fails = []

    def check(ok, what):
        if not ok:
            fails.append(what)

    rng = np.random.default_rng(7)
    x0, y1, n = 1000.0, 2000.0, 600  # a 600 m square of 1 m cells, top-left (x0, y1)

    def ramp_bumps(X, Y):
        return (500 + 0.03 * (X - x0) + 0.01 * (y1 - Y) + 2 * np.sin((X - x0) / 37)
                + 1.5 * np.cos((y1 - Y) / 23) + 0.5 * np.sin((X - x0 + y1 - Y) / 11))

    def hill(X, Y):
        return 500 + 40 * np.exp(-((X - x0 - 300) ** 2 + (Y - y1 + 300) ** 2) / (2 * 100.0 ** 2))

    def ramp(X, Y):
        return 500 + 0.03 * (X - x0) + 0.01 * (y1 - Y)

    def tiles_of(fn):
        c, r = np.meshgrid(np.arange(n) + 0.5, np.arange(n) + 0.5)
        return [(fn(x0 + c, y1 - r), Affine(1.0, 0.0, x0, 0.0, -1.0, y1))]

    def cloud(fn, npts, dx, dy, a, b, c, x_lo=100, x_hi=500):
        # Points whose true place is (x + dx, y + dy) on the DEM, raised by a plane
        # about their centre, with 8 cm noise and a tenth of them 2-15 m high.
        x = rng.uniform(x0 + x_lo, x0 + x_hi, npts)
        y = rng.uniform(y1 - 500, y1 - 100, npts)
        z = fn(x + dx, y + dy) + a + b * (x - x.mean()) / 100 + c * (y - y.mean()) / 100 + rng.normal(0, 0.08, npts)
        k = rng.random(npts) < 0.1
        z[k] += rng.uniform(2, 15, k.sum())
        return x, y, z, k

    bumps = tiles_of(ramp_bumps)
    truth = dict(dx=3.5, dy=-2.25, a=12.3, b=0.8, c=-0.4)
    x, y, z, planted = cloud(ramp_bumps, 30_000, **truth)
    for model in MODELS:
        fit = fit_alignment(x, y, z, x, y, bumps, model, np.random.default_rng(1))
        s = fit["surface"]
        check(abs(fit["shift_x"] - truth["dx"]) <= 0.25 and abs(fit["shift_y"] - truth["dy"]) <= 0.25,
              f"{model}: shift ({fit['shift_x']}, {fit['shift_y']}), truth ({truth['dx']}, {truth['dy']})")
        check(abs(s[0] - truth["a"]) <= 0.05, f"{model}: offset {s[0]:.3f}, truth {truth['a']}")
        check(abs(s[1] - truth["b"]) <= 0.05 and abs(s[2] - truth["c"]) <= 0.05,
              f"{model}: tilt ({s[1]:.3f}, {s[2]:.3f}), truth ({truth['b']}, {truth['c']})")
        check(fit["misfit"] < 0.15, f"{model}: misfit {fit['misfit']:.3f} on 8 cm noise")
        check(0.08 <= fit["outliers"] <= 0.12, f"{model}: outlier share {fit['outliers']:.3f}, a tenth planted")
        check(fit["points"] >= 29_000 and fit["coverage"] == 1.0 and fit["misfit_masked"] is None,
              f"{model}: {fit['points']} points of 30000, coverage {fit['coverage']}, masked {fit['misfit_masked']}")
    check(all(abs(c) < 0.05 for c in fit["surface"][3:]),
          f"quadratic terms on a plane truth: {fit['surface'][3:]}")
    row = describe_fit(dict(zip(KEY, ("r", "w", "2026", "i"))), fit, fit["shift_x"], fit["shift_y"])
    check(row["status"] == "fitted" and row["surface"].startswith("[") and row["tilt_m_per_100m"] > 0
          and row["misfit_masked_m"] == "", f"describe_fit: {row}")

    # A mask: the fit uses only the kept points, the misfit is still scored on
    # every point, misfit_masked on the kept ones.
    fit = fit_alignment(x, y, z, x, y, bumps, "plane", np.random.default_rng(1), keep=~planted)
    check(fit["outliers"] < 0.01 and abs(fit["surface"][0] - truth["a"]) <= 0.03,
          f"masked fit: outliers {fit['outliers']:.3f}, offset {fit['surface'][0]:.3f}")
    check(fit["misfit_masked"] is not None and fit["misfit_masked"] < fit["misfit"],
          f"masked misfit {fit['misfit_masked']} against unmasked {fit['misfit']}")
    # A 60 m hill: its flanks between about 50 and 160 m from the top pass 15 degrees.
    def steep(X, Y):
        return 500 + 60 * np.exp(-((X - x0 - 300) ** 2 + (Y - y1 + 300) ** 2) / (2 * 100.0 ** 2))

    s = sample_tiles(slope_tiles(tiles_of(steep)), x, y)
    keep = mask_points("slope", x, y, x, y, tiles_of(steep), None, None)
    check(0.3 < keep.mean() < 0.8 and (s[keep] <= SLOPE_MAX_DEG).all() and (s[~keep] > SLOPE_MAX_DEG).all(),
          f"slope mask keeps {keep.mean():.2f} of the hill's points")
    check(mask_points("none", x, y, x, y, bumps, None, None) is None, "no mask is not None")

    # Refusals: too few points over the DEM; a flight half off it; a shift the
    # window does not contain; a flat site, where the shift is anyone's guess;
    # a mask that leaves nothing to fit.
    def refused(what, tiles, fn, cloud_kw, reason, keep=None):
        xx, yy, zz, _ = cloud(fn, **cloud_kw)
        try:
            fit_alignment(xx, yy, zz, xx, yy, tiles, "plane", np.random.default_rng(1), keep)
            check(False, f"{what} was fitted")
        except Refused as e:
            check(str(e).startswith(reason), f"{what} refused as {e}, not {reason}")

    refused("1500 points", bumps, ramp_bumps, dict(npts=1500, **truth), "too_few_points")
    refused("a flight half off the DEM", bumps, ramp_bumps, dict(npts=20_000, x_lo=-500, x_hi=300, **truth),
            "low_coverage")
    refused("a 30 m shift", tiles_of(hill), hill, dict(npts=20_000, dx=30.0, dy=0.0, a=5.0, b=0.0, c=0.0),
            "shift_at_bound")
    # A ramp with 5 cm of DEM noise: nothing in it tells one shift from another,
    # so the two samples' searches land wherever the noise says.
    flat = [(tiles_of(ramp)[0][0] + rng.normal(0, 0.05, (n, n)), tiles_of(ramp)[0][1])]
    refused("a flat site", flat, ramp, dict(npts=20_000, dx=2.0, dy=1.0, a=5.0, b=0.0, c=0.0), "shift_unstable")
    refused("a mask keeping 500 points", bumps, ramp_bumps, dict(npts=20_000, **truth), "mask_too_few",
            keep=np.arange(20_000) < 500)

    # The open mask reads the dataset's own DSM - DTM: trees east of x0 + 300.
    with tempfile.TemporaryDirectory() as td:
        import rasterio
        raw = pathlib.Path(td) / "raw"
        (raw / "odm_dem").mkdir(parents=True)
        dtm = tiles_of(ramp)[0][0].astype("float32")
        dsm = dtm.copy()
        dsm[:, 300:] += 3.0
        for name, a in ((DTM, dtm), (DSM, dsm)):
            with rasterio.open(str(raw / name), "w", driver="GTiff", height=n, width=n, count=1, dtype="float32",
                               crs="EPSG:32610", transform=Affine(1.0, 0.0, x0, 0.0, -1.0, y1), nodata=-9999.0) as w:
                w.write(a, 1)
        keep = mask_points("open", x, y, x, y, bumps, raw, pathlib.Path(td) / "none")
        check((keep == (x < x0 + 299)).mean() > 0.99, f"open mask: {keep.mean():.2f} kept, {(x < x0 + 300).mean():.2f} west of the trees")
        keep2 = mask_points("slope+open", x, y, x, y, bumps, raw, pathlib.Path(td) / "none")
        check((keep2 <= keep).all(), "slope+open keeps a point open alone drops")

    # The table: what a run writes is what the next run reads, and a merge keeps
    # the rows it did not touch.
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "t.csv"
        refused_row = dict(zip(KEY, ("r", "w", "2025", "h")), status="refused:too_few_points:12",
                           model="plane", mask="none", cloud_points=12, cloud_date="2025-06-01",
                           run_date="2026-10-15")
        rows = {tuple(row[k] for k in KEY): row, tuple(refused_row[k] for k in KEY): refused_row}
        write_table(p, rows)
        back = read_table(p)
        want = {k: {c: str(r.get(c, "")) for c in COLUMNS} for k, r in rows.items()}
        check(back == want, f"round trip: {back} != {want}")
        back[("a", "b", "2024", "c")] = dict(zip(KEY, ("a", "b", "2024", "c")), status="no_cloud")
        write_table(p, back)
        again = read_table(p)
        check(list(again) == sorted(back) and again[("r", "w", "2026", "i")] == want[("r", "w", "2026", "i")],
              f"merge: {list(again)}")
        check(p.read_bytes().count(b"\r") == 0, "table written with CR")
        # --check: a row whose cloud changed, and a published dataset with no row.
        root, prod = pathlib.Path(td) / "raw", pathlib.Path(td) / "prod"
        for k in (("a", "b", "2024", "c"), ("d", "e", "2024", "f")):
            (prod.joinpath(*k) / "odm_dem").mkdir(parents=True)
            (prod.joinpath(*k) / "odm_dem" / "dtm.tif").touch()
        import laspy
        las = laspy.LasData(laspy.LasHeader(point_format=3, version="1.2"))
        las.x, las.y, las.z = np.zeros(12), np.zeros(12), np.zeros(12)
        h = root.joinpath("r", "w", "2025", "h") / LAZ
        h.parent.mkdir(parents=True)
        las.write(str(h))
        # Three drifts: a published dataset with no row, a row whose cloud changed,
        # and a fitted row whose cloud is gone.
        drift = check_table(again, root, prod)
        check(len(drift) == 3 and drift[0].startswith("d/e/2024/f: published, no row")
              and "r/w/2025/h: cloud is 12 points of" in drift[1]
              and drift[2].startswith("r/w/2026/i: cloud gone"), f"--check: {drift}")
        again[("r", "w", "2025", "h")].update(zip(("cloud_points", "cloud_date"), map(str, cloud_header(h))))
        check(check_table(again, root, prod) == [d for d in drift if not d.startswith("r/w/2025/h")],
              "--check after the row was refreshed")

    if fails:
        print(f"ALIGN SELFTEST FAILED: {len(fails)} check(s)", file=sys.stderr)
        for f in fails:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("ALIGN SELFTEST PASS: shift, offset and tilt recovered; masks; refusals; table round trip; --check")
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("projects", nargs="*", help="dataset dirs under the raw tree (default: every published dataset)")
    p.add_argument("--selftest", action="store_true", help="run the gate and exit")
    p.add_argument("--check", action="store_true", help="report table drift against the trees and exit")
    p.add_argument("--trial", metavar="GRID.csv", help="fit every model x mask per dataset into this file")
    p.add_argument("--model", choices=MODELS, default="plane")
    p.add_argument("--mask", choices=MASKS, default="none")
    p.add_argument("--root", default=str(ROOT), help="raw imagery tree")
    p.add_argument("--base", default=str(PROD), help="published tree, enumerated when no project is given")
    p.add_argument("--out", default=str(TABLE), help="table to merge into")
    args = p.parse_args()
    if args.selftest:
        sys.exit(_selftest())
    root, prod, out = pathlib.Path(args.root), pathlib.Path(args.base), pathlib.Path(args.out)
    rows = read_table(out)
    if args.check:
        drift = check_table(rows, root, prod)
        for line in drift:
            print(line, file=sys.stderr)
        if drift:
            sys.exit(f"ALIGN CHECK FAILED: {len(drift)} row(s): re-run the script on them")
        print(f"ALIGN CHECK OK: {len(rows)} rows, every published dataset has one and no cloud changed")
        sys.exit(0)
    keys = [project_key(a, root) for a in args.projects] or published_keys(prod)
    if not keys:
        sys.exit(f"ERROR: no tif under {prod}")
    if args.trial:
        # Resumes: datasets already in the grid are kept, not refitted.
        path = pathlib.Path(args.trial)
        grid = list(csv.DictReader(open(path, newline=""))) if path.is_file() else []
        done = {tuple(r[k] for k in KEY) for r in grid}
        for i, key in enumerate(keys, 1):
            if key in done:
                continue
            rows = trial_rows(key, root, prod)
            grid += rows
            write_trial(path, grid)
            print(f"[{i}/{len(keys)}] {'/'.join(key)}: " + ", ".join(
                f"{r['model']}/{r['mask']} {r.get('misfit_m') or r['status']}" if "model" in r else r["status"]
                for r in rows), file=sys.stderr, flush=True)
        trial_summary(grid)
        return
    for i, key in enumerate(keys, 1):
        row = rows[key] = dataset_row(key, root, prod, args.model, args.mask)
        write_table(out, rows)
        line = f"[{i}/{len(keys)}] {'/'.join(key)}: {row['status']}"
        if row["status"] == "fitted":
            line += (f"  dz_raw {row['dz_raw_m']:+.2f}  shift ({row['shift_x_m']}, {row['shift_y_m']}) "
                     f"+-{row['shift_spread_m']}  tilt {row['tilt_m_per_100m']}  misfit {row['misfit_m']}  "
                     f"n {row['points']}  cov {row['coverage']}")
        print(line, file=sys.stderr, flush=True)
    summary(rows)


if __name__ == "__main__":
    main()

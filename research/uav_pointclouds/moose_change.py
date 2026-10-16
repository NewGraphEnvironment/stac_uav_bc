# /// script
# requires-python = ">=3.11"
# dependencies = ["laspy[lazrs]>=2.5", "pyproj>=3.6", "numpy", "rasterio>=1.3", "matplotlib"]
# ///
"""Pre/post replacement change at the moose crossing (199663), from the two ODM clouds.

argv: offsets.jsonl outdir
Grids each cloud to a 0.5 m DSM (max z) and ground surface (median z of class 2),
in the LidarBC DEM's CRS, then differences post - pre twice: as georeferenced
(raw GPS) and after each cloud is shifted onto LidarBC 2025 by the offset the probe
measured. Writes PNGs and a JSON of stable-area statistics.
"""
import json, os, sys
import numpy as np
import laspy, rasterio
from pyproj import CRS, Transformer
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = "/Users/airvine/Projects/gis/uav_imagery/mackenzie/parsnip/2026/"
PRE = ROOT + "199663_parsnip_trib_chco_11000/odm_georeferencing/odm_georeferenced_model.laz"
POST = ROOT + "199663_parsnip_trib_chco_11000_post_replacement/odm_georeferencing/odm_georeferenced_model.laz"
off = {json.loads(l)["path"]: json.loads(l) for l in open(sys.argv[1])}
for p in (PRE, POST):  # the cloud's own CRS, which the plane centre is in
    off[p]["src_crs"] = laspy.open(p).header.parse_crs().to_wkt()
out = sys.argv[2]
os.makedirs(out, exist_ok=True)
RES = 0.5
DST = CRS.from_epsg(3157)  # NAD83(CSRS) / UTM 10N, the LidarBC horizontal CRS here


def load(p):
    las = laspy.read(p)
    t = Transformer.from_crs(las.header.parse_crs(), DST, always_xy=True)
    X, Y = t.transform(np.asarray(las.x), np.asarray(las.y))
    return X, Y, np.asarray(las.z), np.asarray(las.classification)


def grid(X, Y, Z, x0, y1, nx, ny, how):
    c = ((X - x0) / RES).astype(int); r = ((y1 - Y) / RES).astype(int)
    ok = (c >= 0) & (c < nx) & (r >= 0) & (r < ny)
    k = r[ok] * nx + c[ok]; z = Z[ok]
    g = np.full(nx * ny, np.nan)
    if how == "max":
        g2 = np.full(nx * ny, -np.inf); np.maximum.at(g2, k, z); g = np.where(np.isfinite(g2), g2, np.nan)
    else:  # mean of class-2 ground (median is slow at this size)
        s = np.bincount(k, z, nx * ny); n = np.bincount(k, None, nx * ny)
        g = np.where(n > 0, s / np.maximum(n, 1), np.nan)
    return g.reshape(ny, nx)


A, B = load(PRE), load(POST)
oA, oB = off[PRE], off[POST]
KEYS = ("plane_a", "shift_dx", "shift_dy", "tilt_m_per_100m", "nmad_shift_tilt")
stats = {"pre": {k: oA.get(k) for k in KEYS}, "post": {k: oB.get(k) for k in KEYS}}
x0 = max(A[0].min(), B[0].min()); x1 = min(A[0].max(), B[0].max())
y0 = max(A[1].min(), B[1].min()); y1 = min(A[1].max(), B[1].max())
nx, ny = int((x1 - x0) / RES), int((y1 - y0) / RES)
ext = [0, nx * RES, 0, ny * RES]


def surfaces(C, o, aligned):
    X, Y, Z, cls = C
    if aligned:
        # the probe found UAV (X, Y) matches the DEM at (X + dx, Y + dy), so move the cloud by +shift
        # shift + tilt from uav_lidar_align.py; its plane is in the cloud's own CRS, per 100 m
        cX, cY = Transformer.from_crs(CRS.from_user_input(o["src_crs"]), DST, always_xy=True).transform(*o["centre"])
        Z = Z - (o["plane_a"] + o["tilt_x_m_per_100m"] * (X - cX) / 100 + o["tilt_y_m_per_100m"] * (Y - cY) / 100)
        X = X + o["shift_dx"]; Y = Y + o["shift_dy"]
    g = cls == 2
    return grid(X, Y, Z, x0, y1, nx, ny, "max"), grid(X[g], Y[g], Z[g], x0, y1, nx, ny, "mean")


res = {}
for aligned in (False, True):
    dA, gA = surfaces(A, oA, aligned); dB, gB = surfaces(B, oB, aligned)
    d = dB - dA
    dg = gB - gA
    key = "aligned" if aligned else "raw"
    v = d[np.isfinite(d)]
    vg = dg[np.isfinite(dg)]
    res[key] = {"dsm_diff_median": float(np.median(v)), "dsm_diff_p05": float(np.percentile(v, 5)),
                "dsm_diff_p95": float(np.percentile(v, 95)),
                "ground_diff_median": float(np.median(vg)),
                "ground_diff_nmad": float(1.4826 * np.median(np.abs(vg - np.median(vg)))),
                "frac_cells_abs_gt_0p5m": float((np.abs(v - np.median(v)) > 0.5).mean())}
    np.save(f"{out}/ddsm_{key}.npy", d.astype("float32"))
    lim = 2.0
    fig, ax = plt.subplots(figsize=(7, 6), dpi=130)
    im = ax.imshow(d if aligned else d - 0, extent=ext, cmap="RdBu_r",
                   vmin=(-lim if aligned else np.nanmedian(d) - lim), vmax=(lim if aligned else np.nanmedian(d) + lim))
    ax.set_title(f"post - pre DSM, {'shift + tilt onto LidarBC 2025' if aligned else 'as georeferenced (GPS only)'}")
    ax.set_xlabel("m"); ax.set_ylabel("m")
    plt.colorbar(im, ax=ax, label="m")
    fig.tight_layout(); fig.savefig(f"{out}/moose_ddsm_{key}.png"); plt.close(fig)
    if aligned:
        h = np.clip(v, -3, 3)
        fig, ax = plt.subplots(figsize=(6, 3), dpi=130)
        ax.hist(h, bins=120, color="#4a6fa5"); ax.set_yscale("log")
        ax.set_xlabel("post - pre DSM (m), aligned"); ax.set_ylabel("cells")
        fig.tight_layout(); fig.savefig(f"{out}/moose_ddsm_hist.png"); plt.close(fig)
stats.update(res); stats["grid"] = {"res_m": RES, "nx": nx, "ny": ny, "x0": x0, "y1": y1}
json.dump(stats, open(f"{out}/moose_stats.json", "w"), indent=1)
print(json.dumps(stats, indent=1))

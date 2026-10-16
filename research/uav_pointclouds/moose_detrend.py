# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "matplotlib"]
# ///
"""Robust quadratic detrend of the aligned post - pre DSM difference (relative alignment only)."""
import json, sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
d = np.load(sys.argv[1]); out = sys.argv[2]; RES = 0.5
ny, nx = d.shape
yy, xx = np.mgrid[0:ny, 0:nx]
xs = (xx * RES - nx * RES / 2) / 100; ys = (ny * RES / 2 - yy * RES) / 100
ok = np.flatnonzero(np.isfinite(d.ravel()))
rng = np.random.default_rng(1); s = rng.choice(ok, min(len(ok), 300_000), replace=False)
def design(i): x, y = xs.ravel()[i], ys.ravel()[i]; return np.c_[np.ones_like(x), x, y, x * x, x * y, y * y]
v = d.ravel()[s]; k = np.ones(len(s), bool)
for _ in range(4):
    c, *_ = np.linalg.lstsq(design(s[k]), v[k], rcond=None)
    r = v - design(s) @ c
    m = 1.4826 * np.median(np.abs(r[k] - np.median(r[k])))
    k = np.abs(r) < 2.5 * max(m, 0.05)
res = np.full(d.size, np.nan); res[ok] = d.ravel()[ok] - design(ok) @ c; res = res.reshape(d.shape)
rv = res[np.isfinite(res)]
st = {"quad_coef": c.tolist(), "nmad_after": float(1.4826 * np.median(np.abs(rv - np.median(rv)))),
      "frac_abs_gt_1m": float((np.abs(rv) > 1).mean()), "frac_abs_gt_2m": float((np.abs(rv) > 2).mean()),
      "trend_range_m": float(np.ptp(design(ok) @ c))}
json.dump(st, open(f"{out}/moose_detrend.json", "w"), indent=1); print(json.dumps(st))
np.save(f"{out}/ddsm_detrended.npy", res.astype("float32"))
fig, ax = plt.subplots(figsize=(7, 6), dpi=130)
im = ax.imshow(res, extent=[0, nx * RES, 0, ny * RES], cmap="RdBu_r", vmin=-2, vmax=2)
ax.set_title("post - pre DSM, after a quadratic detrend between flights"); ax.set_xlabel("m"); ax.set_ylabel("m")
plt.colorbar(im, ax=ax, label="m"); fig.tight_layout(); fig.savefig(f"{out}/moose_ddsm_detrended.png"); plt.close(fig)

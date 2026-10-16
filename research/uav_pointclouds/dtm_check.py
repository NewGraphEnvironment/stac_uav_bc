# /// script
# requires-python = ">=3.11"
# dependencies = ["laspy[lazrs]>=2.5", "numpy", "rasterio>=1.3", "pyproj"]
# ///
import sys, numpy as np, laspy, rasterio
from pyproj import Transformer
for laz, url in zip(sys.argv[1::2], sys.argv[2::2]):
    las = laspy.read(laz); g = np.asarray(las.classification) == 2
    i = np.random.default_rng(1).choice(np.flatnonzero(g), 20000, replace=False)
    with rasterio.open(url) as r:
        t = Transformer.from_crs(las.header.parse_crs(), r.crs, always_xy=True)
        X, Y = t.transform(np.asarray(las.x)[i], np.asarray(las.y)[i])
        v = np.array([s[0] for s in r.sample(zip(X, Y))], float)
        nd = r.nodata
    ok = np.isfinite(v) & (v != nd) & (v > -1000)
    print(url.split("/")[-4], "published DTM minus cloud ground: median %.2f m, n=%d" % (np.median(v[ok] - np.asarray(las.z)[i][ok]), ok.sum()))

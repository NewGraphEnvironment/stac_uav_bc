"""For each UAV cloud bbox, the LidarBC point cloud and DEM items it intersects (STAC API)."""
import json, sys, urllib.request

API = "https://images.a11s.one/search"


def search(coll, bbox):
    body = json.dumps({"collections": [coll], "bbox": bbox, "limit": 200}).encode()
    req = urllib.request.Request(API, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["features"]


out = []
for line in open(sys.argv[1]):
    r = json.loads(line)
    bb = r["bbox_ll"]
    pc = search("stac-pointcloud-bc", bb)
    dem = search("stac-elevation-bc", bb)
    out.append({
        "path": r["path"],
        "pc": [{"id": f["id"], "dt": f["properties"].get("datetime") or f["properties"].get("start_datetime"),
                "delivery": f["properties"].get("lidarbc:delivery"),
                "laz": f["assets"]["laz"]["href"], "copc": f["assets"].get("copc", {}).get("href")} for f in pc],
        "dem": [{"id": f["id"], "dt": f["properties"].get("datetime") or f["properties"].get("start_datetime"),
                 "assets": sorted(f["assets"]), "dem": f["assets"].get("dem", {}).get("href")} for f in dem],
    })
    print(len(out), r["path"][-60:], len(pc), len(dem), file=sys.stderr, flush=True)
json.dump(out, open(sys.argv[2], "w"), indent=1)

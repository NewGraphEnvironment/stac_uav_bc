# DigitalOcean Droplet Setup — STAC API Stack

STAC API for UAV imagery at [images.a11s.one](https://images.a11s.one).

> **The droplet is built from our internal infrastructure-as-code repo** (OpenTofu + cloud-init → `/opt/geoserv/docker-compose.yml`). Server build questions belong there; this directory documents the catalog-side workflow. Everything below the **Historical reference** heading describes the previous stack and is kept for context only.

## Current Stack (geoserv, 2026)

Containers on the droplet (`root@146.190.12.8`, hostname `geopro`):

| Container | Image | Port | Serves |
|---|---|---|---|
| `geoserv-stac` | `stac-fastapi-pgstac` | 8000 | `images.a11s.one` |
| `geoserv-stac-ortho` | `stac-fastapi-pgstac` | 8002 | ortho catalog (db `stac_ortho`) |
| `geoserv-db` | `pgstac:v0.9.8` | 5432 | postgres, user/db `stac` |
| `geoserv-titiler` | titiler | 8001 | `titiler.a11s.one` |
| `geoserv-caddy` | caddy | 80/443 | TLS + reverse proxy |

The public API is **read-only**: the transactions extension is off, so POST/PUT/DELETE return 405. That is deliberate — writes go through pypgstac on the droplet host (installed by the server build at `/opt/geoserv/scripts` via `uv`).

## Adding New Imagery — the Recipe

Two commands with a human QC gate between them:

1. Stitch — `caffeinate -s scripts/odm_process-batch.sh <project-dir>...` (skips already-processed dirs; resume-safe after interruption)
2. QC the ortho — check `odm_report/stats.json` (all images reconstructed? reprojection error ~1-2 px?) and eyeball a preview
3. Publish — `scripts/stac_publish.sh <project-dir>...` (COG convert + validate → prod tree → items with flight datetimes → durable S3 upload → register items + collection extent → verify via API; idempotent, safe to re-run)

The underlying single-purpose tools these orchestrate, for one-off use:

- `scripts/stac_create_item.py <tifs relative to prod tree>` — items + collection.json (conda env `titiler`)
- `scripts/config/stac_register_item.sh <item jsons>` — upsert items into the API db
- `scripts/config/stac_register_collection.sh <collection.json>` — upsert the collection doc
- `conda run -n dff rio cogeo create <in> <out>` — COG conversion (see `scripts/cog_convert.R` for the batch-log history)
- Dev tree/bucket retired 2026-07 — prod only

### Large datasets (>~300 images)

Single-pass ODM memory scales with the whole flight and the meshing stage can run 10+ hours or OOM (observed: 817 images → 20+ h, >70 GB RAM). Use split-merge instead:

```bash
caffeinate -s scripts/odm_process-batch.sh --split 250 <project-dir>
```

ODM carves the flight into ~250-image submodels (100 m overlap), processes each like a normal dataset, and merges orthos/DEMs at the end — memory bounded per submodel, progress checkpointed between them. Other escape hatches: `--fast-orthophoto` (skips dense reconstruction; ortho only, no usable DEMs) and, when a meshing-stage OOM needs rescue, rerun with a lower `--mesh-octree-depth` from `--rerun-from odm_meshing`. For routinely-large campaigns consider a NodeODM ephemeral droplet (tracked in the infrastructure repo).

### Gotchas

- **s3://imagery-uav-bc has ACLs disabled** — public read comes from the bucket policy. Never pass `--acl`; `put-object-acl` fails with `AccessControlListNotSupported`.
- **TiTiler caches failed lookups**: if a COG is probed before its upload finishes, GDAL caches the 403 and the URL stays broken. Fix: `ssh root@146.190.12.8 docker restart geoserv-titiler`.
- Full collection rebuild and collection deletion are **server-side operations** — that tooling lives with the server build in our internal infrastructure repo, not here.

---

## Historical reference (previous stack)

> **Note:** The numbered setup scripts (`01_server.sh`, `02_server.sh`, etc.) are `.gitignore`d — they contain credentials and server config.

## Infrastructure

- **Provider:** DigitalOcean (single droplet)
- **OS:** Ubuntu (18.04+ scripts, currently running 22.04)
- **Domain:** `a11s.one` with subdomains via Nginx reverse proxy (current), Caddy recommended for OpenTofu rebuild
- **SSL:** Let's Encrypt via Certbot (current), automatic via Caddy (recommended)

## Services

| Service | Runtime | Port | Subdomain | Image / Package |
|---|---|---|---|---|
| STAC FastAPI (pgstac) | Python venv | 8000 | `images.a11s.one` | `stac-fastapi.pgstac` (pip) |
| PostgreSQL + PostGIS + pgstac | Docker | 5432 | — | `postgis/postgis` |
| TiTiler | Docker | 8001 | `titiler.a11s.one` | `developmentseed/titiler:latest` |
| RStudio Server | System | 8787 | `rstudio.a11s.one` | (installed separately) |
| Static viewer | Nginx | 443 | `viewer.a11s.one` | Files at `/var/www/html/viewer` |

## Networking

- **Nginx** reverse-proxies all subdomains to localhost ports
- **UFW** firewall — allows OpenSSH, port 8001 (TiTiler)
- All HTTP traffic redirects to HTTPS
- CORS headers on `titiler.a11s.one` and `viewer.a11s.one` (GET, OPTIONS)
- ACME challenge passthrough on all port-80 server blocks

## Database

- **Container name:** `postgis`
- **Credentials:** user=`stac`, password=`stacpw`, db=`stac`
- **Extensions:** PostGIS
- **Schema:** `pgstac` (applied via `pypgstac migrate`)
- **Roles:** `pgstac_admin`, `pgstac_ingest`, `pgstac_read`
- Search path set to `pgstac, public` for the `stac` user

## Python Environment

- Virtual env at `/home/airvine/stac-env/`
- Key packages: `stac-fastapi.pgstac`, `pypgstac`, `psycopg`, `psycopg_pool`, `stac-validator`
- STAC API started via: `stac-fastapi-pgstac --host 0.0.0.0 --port 8000`
- Optional rate-limit middleware in `main.py` (caps `/search` POST to 1000 items)

## System Tuning

- 2GB swap file at `/swapfile` (persisted in `/etc/fstab`)
- `vm.swappiness=10`
- `vm.vfs_cache_pressure=50`

## Setup Order

1. `01_server.sh` — User creation, SSH hardening, UFW
2. `02_server.sh` — Docker, Python venv, PostgreSQL/pgstac, STAC FastAPI, swap
3. `02b_stac_fast_api.sh` — Alternative STAC API startup (from venv, no Docker)
4. `03_certbot.sh` — SSL certificates for all subdomains
5. `04_titiler.sh` — TiTiler Docker container on port 8001

Post-setup:
- Collection registration/unregistration scripts (since moved to the internal infrastructure repo)

## Data Flow

```
S3 buckets (COGs)                    Clients (rstac, QGIS)
  imagery-uav-bc.s3.amazonaws.com           │
        │                                   ▼
        │                          images.a11s.one (Nginx)
        │                                   │
        │                                   ▼
        │                          STAC FastAPI :8000
        │                                   │
        │                                   ▼
        │                          PostgreSQL/pgstac :5432
        │
        └──────────────────────► TiTiler :8001 (tile serving)
                                   titiler.a11s.one (Nginx)
```

## Migration Strategy

Use a **DigitalOcean reserved IP** for zero-downtime cutover between the current droplet and the new OpenTofu-managed one.

1. Assign a reserved IP to the **current** droplet, update DNS A records for `a11s.one` and all subdomains to point to it
2. Build new droplet with OpenTofu, test via its direct IP
3. Reassign the reserved IP to the new droplet (instant cutover)
4. Caddy auto-provisions SSL certs within seconds of receiving traffic
5. Keep old droplet around briefly as fallback, then destroy

DNS A records point to the reserved IP permanently — future rebuilds just reassign it.

```hcl
resource "digitalocean_reserved_ip" "main" {
  region = "sfo3"
}

resource "digitalocean_reserved_ip_assignment" "main" {
  ip_address = digitalocean_reserved_ip.main.ip_address
  droplet_id = digitalocean_droplet.stac.id
}
```

**Cert chicken-and-egg:** Caddy needs the domain pointing at it to get certs (HTTP-01 challenge). On the new server, test via IP first (Caddy serves self-signed), then reassign the reserved IP and real certs provision automatically. Alternatively, use DNS-01 challenges with Caddy's DigitalOcean plugin to provision certs before cutover.

## Notes for OpenTofu Translation

- **Replace Nginx + Certbot with Caddy** — eliminates `03_certbot.sh`, the 160-line nginx config, renewal timers, and ACME challenge blocks. Caddy handles HTTPS automatically. Target Caddyfile:

```caddyfile
images.a11s.one {
	reverse_proxy localhost:8000
}

rstudio.a11s.one {
	reverse_proxy localhost:8787
}

titiler.a11s.one {
	reverse_proxy localhost:8001
	header Access-Control-Allow-Methods "GET, OPTIONS"
	header Access-Control-Allow-Headers "Content-Type"
}

viewer.a11s.one {
	root * /var/www/html/viewer
	file_server
	header Access-Control-Allow-Methods "GET, OPTIONS"
	header Access-Control-Allow-Headers "Content-Type"
}
```

- PostgreSQL and TiTiler are Docker containers — could become managed services or remain containerized
- STAC FastAPI runs from a Python venv, not Docker — consider containerizing for consistency
- The `02_server.sh` script was assembled incrementally and may not run cleanly end-to-end
- Database credentials are hardcoded — use secrets management in IaC
- `.msmtprc` is a Gmail SMTP template (not currently active in the stack)

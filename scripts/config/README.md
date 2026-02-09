# DigitalOcean Droplet Setup — STAC API Stack

Reference architecture for a single Ubuntu droplet serving a STAC API for UAV imagery. Used at [images.a11s.one](https://images.a11s.one). This document is intended as a specification for reproducing the stack with OpenTofu/IaC.

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
- `stac_register.sh` — Register a collection + items from S3 into the API (chunked)
- `stac_unregister.sh` — Delete a collection and its items from the API

## Data Flow

```
S3 buckets (COGs)                    Clients (rstac, QGIS)
  stac-orthophoto-bc.s3.amazonaws.com       │
  stac-dem-bc.s3.amazonaws.com              │
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

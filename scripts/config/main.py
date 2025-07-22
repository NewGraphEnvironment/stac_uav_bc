# main.py - this is to set a rate limit for the fastAPI so big queries need to be paginated client side.

# we will run from home/airvine

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from stac_fastapi.pgstac.app import StacApi
from stac_fastapi.pgstac.core import CoreCrudClient
from pypgstac.db import Session

app = FastAPI()

# Enforce a limit cap on /search POST requests
@app.middleware("http")
async def enforce_limit(request: Request, call_next):
    if request.url.path.endswith("/search") and request.method == "POST":
        try:
            body = await request.json()
            if "limit" in body and int(body["limit"]) > 1000:
                return JSONResponse(status_code=400, content={"detail": "Max limit is 1000"})
        except Exception:
            pass  # fail open if request is malformed
    return await call_next(request)

# Mount the STAC API routes
stac_api = StacApi(client=CoreCrudClient.create(Session()))
app.include_router(stac_api.router, prefix="/")

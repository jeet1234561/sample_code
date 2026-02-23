"""EPIAP Backend — FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.ingestion.scheduler import scheduler, register_jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    register_jobs()
    scheduler.start()
    logging.getLogger("epiap").info(
        "Scheduler started with all connector jobs"
    )
    yield
    # Shutdown
    scheduler.shutdown(wait=False)
    logging.getLogger("epiap").info("Scheduler shut down")


app = FastAPI(
    title="EPIAP Backend",
    description="Employee Productivity Intelligence & Alerts Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "epiap-backend"}

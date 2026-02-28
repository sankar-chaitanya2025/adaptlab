# main.py
# AdaptLab — FastAPI application entry point.
# Registers all routers. Runs DB init + seed on startup.
# Imports from: api/routes_*.py, database/db.py, database/seed.py, utils/logger.py

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes_faculty import router as faculty_router
from api.routes_problems import router as problems_router
from api.routes_student import router as student_router
from api.routes_submit import router as submit_router
from database.db import create_tables
from database.seed import seed_problems
from utils.logger import get_logger

log = get_logger("main")


# ─────────────────────────────────────────────
# Lifespan — startup + shutdown
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup:
        1. Create all DB tables (idempotent — safe to run on every start)
        2. Seed 20 starter problems if problem bank is empty
    Shutdown:
        Nothing to clean up for SQLite prototype.
    """
    log.info("adaptlab_startup_begin")

    try:
        create_tables()
        log.info("db_tables_created")
    except Exception as exc:
        log.exception("db_init_failed", error=str(exc))
        raise

    try:
        seeded = seed_problems()
        if seeded:
            log.info("db_seed_complete")
        else:
            log.info("db_seed_skipped", reason="problem bank already populated")
    except Exception as exc:
        log.exception("db_seed_failed", error=str(exc))
        # Non-fatal — server can still run with existing data

    log.info("adaptlab_startup_complete")
    yield

    log.info("adaptlab_shutdown")


# ─────────────────────────────────────────────
# App factory
# ─────────────────────────────────────────────

app = FastAPI(
    title="AdaptLab",
    description=(
        "Adaptive coding lab platform for college students. "
        "Inspired by the Socratic-Zero framework (Wang et al., 2025). "
        "Runs on a single college server — 16GB RAM, no GPU."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────
# CORS — allow browser access from any origin (dev/college intranet)
# ─────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # tighten in production to specific college domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────

app.include_router(submit_router)       # POST /submit
app.include_router(problems_router)     # GET  /problems/next, GET /problems/{id}
app.include_router(student_router)      # GET  /student/{id}/profile, /student/{id}/history
app.include_router(faculty_router)      # GET  /faculty/dashboard, /faculty/class-overview
                                        # GET  /faculty/escalations
                                        # POST /faculty/escalations/{log_id}/resolve


# ─────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────

@app.get("/health", tags=["system"], summary="Health check")
def health_check() -> dict:
    """Returns service status. Used by load balancer / monitoring."""
    return {"status": "ok", "service": "AdaptLab", "version": "1.0.0"}


@app.get("/", tags=["system"], include_in_schema=False)
def root() -> dict:
    return {
        "service": "AdaptLab",
        "docs":    "/docs",
        "health":  "/health",
    }


# ─────────────────────────────────────────────
# Dev server entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    from utils.constants import SERVER_HOST, SERVER_PORT

    log.info("starting_dev_server", host=SERVER_HOST, port=SERVER_PORT)
    uvicorn.run(
        "main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=True,
        log_level="info",
    )

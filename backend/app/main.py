import sys
from pathlib import Path

# Ensure backend root is on sys.path for direct uvicorn execution
_backend_root = str(Path(__file__).resolve().parent.parent)
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.db.session import init_db, get_db, SessionLocal
from app.api.routes.meetings import router as meetings_router
from app.api.routes.trackers import router as trackers_router
from app.api.routes.review import router as review_router
from app.api.routes.audit import router as audit_router
from app.api.routes.decisions import router as decisions_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.proposals import router as proposals_router
from app.api.routes.reminders_digest import router as reminders_digest_router
from app.api.routes.evaluation import router as evaluation_router
from app.services.premise_watch import run_expiry
from app.services.reminders import run_reminders
from app.services.digest import generate_and_schedule_weekly_digests


scheduler = BackgroundScheduler()


def _scheduled_expiry_job():
    with SessionLocal() as db:
        run_expiry(db, actor="apscheduler_daily")


def _scheduled_reminders_job():
    with SessionLocal() as db:
        run_reminders(db)


def _scheduled_digest_job():
    with SessionLocal() as db:
        generate_and_schedule_weekly_digests(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    init_db()
    # Start APScheduler jobs
    scheduler.add_job(_scheduled_expiry_job, "cron", hour=0, minute=0, id="daily_premise_expiry", replace_existing=True)
    scheduler.add_job(_scheduled_reminders_job, "interval", minutes=15, id="interval_reminders_15m", replace_existing=True)
    scheduler.add_job(_scheduled_digest_job, "cron", day_of_week="mon", hour=9, minute=0, id="weekly_digest_mon_9am", replace_existing=True)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Decidr API",
    description="Meeting-to-Execution and Decision Impact Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(meetings_router)
app.include_router(trackers_router)
app.include_router(review_router)
app.include_router(audit_router)
app.include_router(decisions_router)
app.include_router(alerts_router)
app.include_router(proposals_router)
app.include_router(reminders_digest_router)
app.include_router(evaluation_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config")
def get_config():
    """Returns application configuration flags for frontend UI adaptivity."""
    return {
        "demo_mode": settings.DEMO_MODE,
        "llm_provider": settings.LLM_PROVIDER,
        "tracker": settings.TRACKER,
    }


@app.post("/demo/reset")
def reset_demo_database():
    """Resets and reseeds demo database (allowed only when DEMO_MODE=True)."""
    if not settings.DEMO_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Resetting demo data is disabled because DEMO_MODE is false.",
        )
    from scripts.demo_reset import run_demo_reset
    run_demo_reset()
    return {"status": "ok", "message": "Demo data reset successfully"}


@app.post("/admin/run-expiry")
def trigger_run_expiry(as_of: Optional[str] = None, db: SessionLocal = Depends(get_db)):
    """
    Simulates time progression and evaluates premise expiry rules as of a given date (default today).
    """
    target_date = date.fromisoformat(as_of) if as_of else None
    alerts = run_expiry(db, as_of=target_date, actor="admin_api")
    return {
        "status": "ok",
        "as_of": (target_date or datetime.now(timezone.utc).date()).isoformat(),
        "alerts_created": len(alerts),
    }

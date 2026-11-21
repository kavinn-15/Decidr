from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.session import init_db
from app.api.routes.meetings import router as meetings_router
from app.api.routes.trackers import router as trackers_router
from app.api.routes.review import router as review_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    init_db()
    yield


app = FastAPI(
    title="Decidr API",
    description="Meeting-to-Execution and Decision Impact Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(meetings_router)
app.include_router(trackers_router)
app.include_router(review_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

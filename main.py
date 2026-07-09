import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from core.limiter import limiter
from core.database import init_db, get_db_connection, get_connection_pool
from core.seeding import seed_database
from core.security import JWT_SECRET_KEY
from app.api.v1.router import api_router

logger = logging.getLogger("uvicorn.error")

try:
    init_db()
    logger.info("Running database seeding...")
    with get_db_connection() as conn:
        seed_database(conn)
except Exception as e:
    logger.error(f"Database initialization failed: {e}")

app = FastAPI(
    title="Teachee API",
    description="Backend API for Teachee Module enabling quiz generation, questions regeneration/management, publishing, and statistics reporting using Raw SQL PostgreSQL.",
    version="1.0.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.on_event("shutdown")
def shutdown():
    pool = get_connection_pool()
    if pool:
        pool.closeall()
        logger.info("Database connection pool closed.")

@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "Welcome to Teachee API (Raw SQL)!",
        "documentation": "/docs",
        "endpoints": {
            "generate_quiz": "POST /api/v1/quizzes/generate",
            "publish_quiz": "POST /api/v1/quizzes/{quiz_id}/publish",
            "quiz_reports": "GET /api/v1/quizzes/{quiz_id}/reports",
            "regenerate_question": "PUT /api/v1/questions/{question_id}/regenerate",
            "edit_question": "PATCH /api/v1/questions/{question_id}",
            "delete_question": "DELETE /api/v1/questions/{question_id}"
        }
    }

@app.get("/health")
async def health():
    status = {"database": "unhealthy", "ai_provider": "unknown"}
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        status["database"] = "healthy"
    except Exception as e:
        status["database"] = f"unhealthy: {e}"

    ai_provider = os.getenv("AI_PROVIDER", "vllm").lower()
    status["ai_provider"] = ai_provider

    if ai_provider == "vllm":
        try:
            import httpx
            VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8000/v1")
            with httpx.Client(timeout=2) as client:
                resp = client.get(f"{VLLM_URL}/models")
                status["vllm"] = "healthy" if resp.status_code == 200 else "unreachable"
        except Exception:
            status["vllm"] = "unreachable"

    overall = "healthy" if status["database"] == "healthy" else "degraded"
    return {"status": overall, "checks": status}

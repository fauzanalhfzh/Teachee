import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.database import init_db, get_db_connection
from core.seeding import seed_database
from app.api.v1.router import api_router

# Configure logger
logger = logging.getLogger("uvicorn.error")

# Run database setup (DDL query tables initialization)
try:
    init_db()
    
    # Perform database seeding
    logger.info("Running database seeding...")
    with get_db_connection() as conn:
        seed_database(conn)
except Exception as e:
    logger.error(f"Database initialization failed: {e}")

app = FastAPI(
    title="Teacher Quiz AI API",
    description="Backend API for Teacher Module enabling quiz generation, questions regeneration/management, publishing, and statistics reporting using Raw SQL PostgreSQL.",
    version="1.0.0"
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for easier frontend integration during testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(api_router, prefix="/api/v1")

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

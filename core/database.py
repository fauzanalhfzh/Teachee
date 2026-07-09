import os
import logging
import time
from contextlib import contextmanager
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger("uvicorn.error")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password123@localhost:5432/quiz_db")

if os.getenv("DB_HOST"):
    db_host = os.getenv("DB_HOST")
    DATABASE_URL = f"postgresql://postgres:password123@{db_host}:5432/quiz_db"

# Lazy pool initialization with retry logic
pool = None

def get_connection_pool():
    global pool
    if pool is not None and not pool.closed:
        return pool
    
    # Retry connection up to 10 times (waiting 2 seconds between attempts)
    max_retries = 10
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Connecting to database at {DATABASE_URL.split('@')[-1]} (Attempt {attempt}/{max_retries})...")
            pool = ThreadedConnectionPool(1, 20, DATABASE_URL)
            logger.info("PostgreSQL connection pool initialized successfully.")
            return pool
        except Exception as e:
            logger.warning(f"Database connection failed on attempt {attempt}: {e}")
            if attempt < max_retries:
                time.sleep(2)
            else:
                logger.error("Could not connect to PostgreSQL. Retries exhausted.")
                raise e

@contextmanager
def get_db_connection():
    connection_pool = get_connection_pool()
    conn = connection_pool.getconn()
    try:
        yield conn
    finally:
        connection_pool.putconn(conn)

def get_db():
    with get_db_connection() as conn:
        yield conn

def init_db():
    create_tables_sql = """
    CREATE TABLE IF NOT EXISTS users (
        id UUID PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        avatar VARCHAR(255),
        role VARCHAR(50) NOT NULL CHECK (role IN ('student', 'teacher')),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS classrooms (
        id UUID PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        teacher_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS classroom_student (
        classroom_id UUID NOT NULL REFERENCES classrooms(id) ON DELETE CASCADE,
        student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (classroom_id, student_id)
    );

    -- Migration guard: drop legacy columns from pre-existing quizzes tables.
    -- Skipped entirely when the table does not yet exist (fresh database).
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.tables WHERE table_name = 'quizzes'
        ) THEN
            ALTER TABLE quizzes DROP COLUMN IF EXISTS title;
            ALTER TABLE quizzes DROP COLUMN IF EXISTS subject;
        END IF;
    END $$;

    CREATE TABLE IF NOT EXISTS quizzes (
        id UUID PRIMARY KEY,
        classroom_id UUID NOT NULL REFERENCES classrooms(id) ON DELETE CASCADE,
        teacher_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        topic VARCHAR(255) NOT NULL,
        status VARCHAR(50) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS questions (
        id UUID PRIMARY KEY,
        quiz_id UUID NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
        question_text TEXT NOT NULL,
        options JSONB NOT NULL,
        correct_answer VARCHAR(255) NOT NULL,
        explanation TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS student_attempts (
        id UUID PRIMARY KEY,
        quiz_id UUID NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
        student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        score FLOAT NOT NULL,
        answers_snapshot JSONB NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """
    logger.info("Running database DDL migrations...")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(create_tables_sql)
        conn.commit()
    logger.info("Database tables initialized successfully.")

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

    CREATE TABLE IF NOT EXISTS learning_modules (
        id UUID PRIMARY KEY,
        classroom_id UUID NOT NULL REFERENCES classrooms(id) ON DELETE CASCADE,
        teacher_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title VARCHAR(255) NOT NULL,
        topic VARCHAR(255) NOT NULL,
        status VARCHAR(50) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS module_sections (
        id UUID PRIMARY KEY,
        module_id UUID NOT NULL REFERENCES learning_modules(id) ON DELETE CASCADE,
        section_order INT NOT NULL,
        title VARCHAR(255) NOT NULL,
        content TEXT NOT NULL,
        image_url VARCHAR(500),
        image_prompt TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS module_exercises (
        id UUID PRIMARY KEY,
        module_id UUID NOT NULL REFERENCES learning_modules(id) ON DELETE CASCADE,
        exercise_order INT NOT NULL,
        exercise_type VARCHAR(50) NOT NULL CHECK (exercise_type IN ('multiple_choice', 'fill_blank', 'true_false', 'matching', 'ordering')),
        question_text TEXT NOT NULL,
        options JSONB,
        correct_answer TEXT NOT NULL,
        explanation TEXT,
        points INT DEFAULT 10,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS student_module_progress (
        id UUID PRIMARY KEY,
        module_id UUID NOT NULL REFERENCES learning_modules(id) ON DELETE CASCADE,
        student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        content_completed BOOLEAN DEFAULT FALSE,
        content_completed_at TIMESTAMP WITH TIME ZONE,
        exercises_completed BOOLEAN DEFAULT FALSE,
        exercises_completed_at TIMESTAMP WITH TIME ZONE,
        exercise_answers JSONB,
        exercise_score FLOAT,
        quiz_unlocked BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (module_id, student_id)
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
            ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS start_time TIMESTAMP WITH TIME ZONE;
            ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS end_time TIMESTAMP WITH TIME ZONE;
            ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS duration_minutes INTEGER;
            ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS module_id UUID REFERENCES learning_modules(id) ON DELETE SET NULL;
        END IF;
    END $$;

    CREATE TABLE IF NOT EXISTS quizzes (
        id UUID PRIMARY KEY,
        classroom_id UUID NOT NULL REFERENCES classrooms(id) ON DELETE CASCADE,
        teacher_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        topic VARCHAR(255) NOT NULL,
        status VARCHAR(50) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
        start_time TIMESTAMP WITH TIME ZONE,
        end_time TIMESTAMP WITH TIME ZONE,
        duration_minutes INTEGER,
        module_id UUID REFERENCES learning_modules(id) ON DELETE SET NULL,
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

    -- Migration guard: add started_at column to student_attempts if table already exists
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.tables WHERE table_name = 'student_attempts'
        ) THEN
            ALTER TABLE student_attempts ADD COLUMN IF NOT EXISTS started_at TIMESTAMP WITH TIME ZONE;
        END IF;
    END $$;

    CREATE TABLE IF NOT EXISTS student_attempts (
        id UUID PRIMARY KEY,
        quiz_id UUID NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
        student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        score FLOAT,
        answers_snapshot JSONB,
        started_at TIMESTAMP WITH TIME ZONE,
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

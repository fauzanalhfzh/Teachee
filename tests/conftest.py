import os
import sys
import urllib.parse
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import pytest
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load .env file manually if it exists
def load_env():
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    if key not in os.environ:
                        os.environ[key] = val

load_env()

# Determine original DATABASE_URL
original_db_url = os.getenv("DATABASE_URL", "postgresql://postgres:password123@localhost:5432/quiz_db")


# Parse and construct the test database URL
parsed = urllib.parse.urlparse(original_db_url)

# If we are not running inside a Docker container (e.g. running directly on Windows or WSL host), swap 'db' to 'localhost'
if parsed.hostname == "db" and not os.path.exists("/.dockerenv"):
    netloc = parsed.netloc.replace("db:", "localhost:").replace("@db", "@localhost")
    parsed = parsed._replace(netloc=netloc)


test_db_url = urllib.parse.urlunparse(parsed._replace(path="/quiz_test_db"))
postgres_db_url = urllib.parse.urlunparse(parsed._replace(path="/postgres"))

# Set DATABASE_URL in environment BEFORE importing main or core.database
os.environ["DATABASE_URL"] = test_db_url


# Now we can import app and database modules safely
from main import app
from core.database import init_db, get_db_connection

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    # Connect to the default 'postgres' database to create the test database if it doesn't exist
    try:
        conn = psycopg2.connect(postgres_db_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'quiz_test_db';")
            exists = cur.fetchone()
            if not exists:
                cur.execute("CREATE DATABASE quiz_test_db;")
        conn.close()
    except Exception as e:
        pytest.fail(f"Failed to create test database 'quiz_test_db': {e}")

    # Run migrations / table creation
    try:
        init_db()
    except Exception as e:
        pytest.fail(f"Failed to initialize tables in test database: {e}")

    yield

@pytest.fixture(autouse=True)
def clean_database():
    # Truncate all tables to guarantee test isolation
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                TRUNCATE TABLE users, classrooms, classroom_student, quizzes, questions, student_attempts CASCADE;
            """)
        conn.commit()

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def create_user():
    from core.security import hash_password
    def _create_user(name, email, role, password="password123"):
        import uuid
        user_id = str(uuid.uuid4())
        hashed_pwd = hash_password(password)
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (id, name, email, password, role)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, name, email, role;
                    """,
                    (user_id, name, email, hashed_pwd, role)
                )
                user = cur.fetchone()
            conn.commit()
        return {
            "id": user_id,
            "name": name,
            "email": email,
            "role": role,
            "password": password
        }
    return _create_user

@pytest.fixture
def teacher_auth_headers(client, create_user):
    # Register/login a teacher and return auth header
    teacher = create_user("Test Teacher", "test_teacher@school.com", "teacher")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": teacher["email"], "password": teacher["password"]}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "user": teacher
    }

@pytest.fixture
def student_auth_headers(client, create_user):
    # Register/login a student and return auth header
    student = create_user("Test Student", "test_student@school.com", "student")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": student["email"], "password": student["password"]}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "user": student
    }

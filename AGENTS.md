# Teachee API — AGENTS.md

## Stack
- **FastAPI** (no ORM — raw SQL via psycopg2 `ThreadedConnectionPool`)
- **PostgreSQL** with `RealDictCursor`, UUID PKs, JSONB columns (options, answers_snapshot)
- **JWT auth** (bcrypt + pyjwt, `HTTPBearer` dependency)
- **Ollama** for AI quiz gen (falls back to hardcoded question banks if unavailable)

## Project layout
```
main.py                 # FastAPI app entrypoint
core/
  database.py           # DDL, connection pool (retry up to 10×, 2s apart)
  security.py           # hash/verify password, create/decode JWT
  seeding.py            # seeds default teacher/classroom/students
app/api/v1/
  router.py             # mounts /auth, /quizzes, /questions, /classrooms, /student
  dependencies.py       # get_current_user (Bearer token → user row)
  endpoints/            # one file per module, raw SQL in handlers
services/
  ai_client.py          # Ollama HTTP client (httpx, timeout 120s)
  ai_service.py         # tries Ollama → falls back to MATH_BANK/HISTORY_BANK/DEFAULT_BANK
schemas/                # Pydantic request/response models
tests/                  # pytest + TestClient, separate test DB
```

## Commands
```bash
# Run locally (requires PostgreSQL on localhost)
uvicorn main:app --reload

# Docker (recommended)
docker compose up --build
docker compose up -d --build    # detached
docker compose down -v          # full reset (drops volumes)

# Tests
pytest                          # uses quiz_test_db, auto-creates it
pytest -v -x                    # verbose, stop on first fail
pytest tests/test_auth.py       # single file

# Pull Ollama model (one-time after docker compose up -d)
bash scripts/setup-ollama.sh
```

## Testing quirks
- **Separate test database** (`quiz_test_db`), created automatically in `conftest.py`
- **Every test**: tables truncated via `TRUNCATE ... CASCADE` (clean slate)
- **Conftest** auto-detects Docker vs host: swaps `db` → `localhost` if `/.dockerenv` missing
- Fixtures: `client`, `create_user`, `teacher_auth_headers`, `student_auth_headers`
- Tests register/login fresh users each run (no seed dependency)
- No linter/typechecker config in repo

## Key conventions
- **Raw SQL everywhere**: no ORM, no query builder
- `json.dumps(...)` for JSONB writes; `RealDictCursor` for reads
- Dynamic SQL builders in update endpoints (PATCH classroom, PATCH question)
- UUIDs generated in Python (`str(uuid.uuid4())`)
- Auth gates: `get_current_user` dependency + manual `verify_student_role()`
- CORS: `allow_origins=["*"]`

## Seed data (auto-seeded on first startup)
| Role    | Email              | Password    |
|---------|--------------------|-------------|
| teacher | teacher@school.com | password123 |
| student | adit@school.com    | password123 |
| student | bambang@school.com | password123 |

Classroom: `Kelas 10A` (teacher_id and classroom_id printed to container logs at startup).

## API prefixes
- All routes under `/api/v1/`
- Auth: `/auth/register`, `/auth/login`, `/auth/me`
- Quizzes: `/quizzes/generate`, `/quizzes/{id}/publish`, `/quizzes/{id}/reports`
- Questions: `/questions/{id}/regenerate`, `/questions/{id}` (PATCH/DELETE)
- Classrooms: standard CRUD at `/classrooms`
- Student: `/student/quizzes`, `/student/quizzes/{id}/take`, `/student/quizzes/{id}/submit`

## AI details
- Ollama endpoint: `http://ollama:11434` (container) or `OLLAMA_URL` env var
- Default model: `qwen2.5:7b`
- Falls back to hardcoded banks (`MATH_BANK`, `HISTORY_BANK`, `DEFAULT_BANK` in `services/ai_service.py`)
- Report endpoint auto-seeds mock student attempts if none exist (for testing convenience)
- Manual testing: use `.http` files in repo root (VS Code REST Client)

## Gotchas
- `.env` is gitignored but `requirements.txt` and config are minimal — pip install is enough
- No pyproject.toml — `requirements.txt` is single source of deps
- `EmailStr` intentionally NOT used (comment in `schemas/auth.py` avoids `email-validator` dep)

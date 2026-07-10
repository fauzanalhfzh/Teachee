# Teachee API — AGENTS.md

## Stack
- **FastAPI** (no ORM — raw SQL via psycopg2 `ThreadedConnectionPool`)
- **PostgreSQL** with `RealDictCursor`, UUID PKs, JSONB columns (options, answers_snapshot)
- **JWT auth** (bcrypt + pyjwt, `HTTPBearer` dependency)
- **vLLM** for AI quiz gen (OpenAI-compatible; falls back to hardcoded question banks if unavailable)

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
  vllm_client.py        # vLLM OpenAI-compatible HTTP client (httpx)
  ai_service.py         # calls vLLM → falls back to MATH_BANK/HISTORY_BANK/DEFAULT_BANK
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

# Services connect to a vLLM OpenAI-compatible server (e.g. DigitalOcean vLLM 1-Click
# droplet). The vLLM container must share the `teachee-vllm` docker network with `web`.
# Start the server inside the vLLM container, e.g.:
#   docker exec -d rocm vllm serve <model> --host 0.0.0.0 --port 8000
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
- Quizzes: `/quizzes/generate`, `/quizzes/{id}/publish`, `/quizzes/{id}/reports`, `/quizzes` (GET list), `/quizzes/{id}` (GET detail), `/quizzes/{id}` (PATCH update)
- Questions: `/questions/{id}/regenerate`, `/questions/{id}` (PATCH/DELETE)
- Classrooms: standard CRUD at `/classrooms`
- Student: `/student/quizzes`, `/student/quizzes/{id}/take`, `/student/quizzes/{id}/submit`

## Quiz time window & one-time attempt
- Quizzes have optional `start_time` / `end_time` (ISO 8601 timestamps) and `duration_minutes` (integer)
- Students can only view/take a quiz within its time window; 403 otherwise
- Active quiz list filters out ended quizzes (`end_time > CURRENT_TIMESTAMP`)
- **One-time rule**: `student_attempts.score IS NOT NULL` check prevents re-submission; `started_at` tracks when student began
- Set `start_time`/`end_time`/`duration_minutes` on generation or via PATCH `/quizzes/{id}`

## AI details
- Single AI provider: **vLLM** (OpenAI-compatible). `AI_PROVIDER` is fixed to `vllm`.
- vLLM endpoint: `http://rocm:8000/v1` (container) or `VLLM_URL` env var; model set via `VLLM_MODEL`.
- `services/vllm_client.py` POSTs to `{VLLM_URL}/chat/completions` and strips Qwen3 `<think>` reasoning blocks before JSON parsing.
- Falls back to hardcoded banks (`MATH_BANK`, `HISTORY_BANK`, `DEFAULT_BANK` in `services/ai_service.py`) when vLLM is unreachable / returns no questions.
- Gemini and Ollama clients were removed; vLLM is the only provider.
- Report endpoint auto-seeds mock student attempts if none exist (for testing convenience)
- Manual testing: use `.http` files in repo root (VS Code REST Client)

## Gotchas
- `.env` is gitignored but `requirements.txt` and config are minimal — pip install is enough
- No pyproject.toml — `requirements.txt` is single source of deps
- `EmailStr` intentionally NOT used (comment in `schemas/auth.py` avoids `email-validator` dep)

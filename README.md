# LMS API (FastAPI + SQLAlchemy 2.0 + Alembic)

A production-ready **Learning Management System (LMS) REST API** built with **FastAPI**, **Pydantic v2**, **SQLAlchemy 2.0 (async)**, **PostgreSQL**, and **Alembic**.

---

## 1. Architecture & Layering

```
HTTP Request
   │
   ▼
Middleware (SecurityHeaders, RequestID + Structured JSON Access Logs, CORS)
   │
   ▼
API Routers  (app/api/v1/)       ── Thin HTTP parsing, JWT auth & RBAC dependencies
   │
   ▼
Schemas      (app/schemas/)      ── Strict Pydantic v2 input validation & output shaping
   │
   ▼
Services     (app/services/)     ── Business rules, ownership checks, transaction commits
   │
   ▼
Models       (app/models/)       ── SQLAlchemy 2.0 ORM tables, FK constraints & indexes
   │
   ▼
PostgreSQL   (asyncpg / Alembic)
```

### Data Model

```
User ──< Enrollment >── Course ──< Module ──< Lesson
  │                        │          │
  ├──< LessonProgress >────┘          └──< Quiz ──< QuizQuestion ──< QuestionOption
  ├──< Review >────────────┘                 │
  ├──< Certificate >───────┘                 └──< QuizSubmission ──< QuizAnswer
  └──< RevokedToken >
```

- **User**: `id`, `email` (unique), `hashed_password` (Argon2), `full_name`, `role` (`student` | `instructor` | `admin`), `is_active`, `created_at`, `updated_at`.
- **Course**: `id`, `title`, `slug` (unique), `description`, `instructor_id`, `status` (`draft` | `published` | `archived`), timestamps.
- **Module**: `id`, `course_id`, `title`, `position`, timestamps.
- **Lesson**: `id`, `module_id`, `title`, `content_type` (`text` | `video` | `link`), `content`, `content_url`, `position`, `duration_minutes`, timestamps.
- **Enrollment**: `id`, `user_id`, `course_id`, `status` (`active` | `dropped`), `enrolled_at`, timestamps — unique `(user_id, course_id)`.
- **LessonProgress**: `id`, `user_id`, `lesson_id`, `completed_at` — unique `(user_id, lesson_id)`.
- **Review**: `id`, `user_id`, `course_id`, `rating` (1-5), `comment`, timestamps — unique `(user_id, course_id)`.
- **Certificate**: `id`, `certificate_code` (unique), `user_id`, `course_id`, `issued_at` — unique `(user_id, course_id)`.
- **RevokedToken**: `id`, `jti` (unique), `token_type`, `user_id`, `expires_at`, `created_at`.
- **Quiz**: `id`, `module_id`, `title`, `description`, `passing_score` (default 70), `max_attempts`, `position`, `is_published`, timestamps.
- **QuizQuestion**: `id`, `quiz_id`, `question_text`, `question_type` (`multiple_choice` | `multi_select` | `true_false`), `points`, `position`, `explanation`, timestamps.
- **QuestionOption**: `id`, `question_id`, `option_text`, `is_correct`, `position`.
- **QuizSubmission**: `id`, `quiz_id`, `user_id`, `score`, `points_scored`, `total_points`, `passed`, `attempt_number`, `submitted_at`.
- **QuizAnswer**: `id`, `submission_id`, `question_id`, `selected_option_ids`, `is_correct`, `points_awarded`.

---

## 2. Tech Stack

| Concern | Choice |
|---|---|
| Framework | FastAPI (async application factory in `app/main.py`) |
| Database | PostgreSQL (`asyncpg` driver; `aiosqlite` for fast local tests) |
| ORM | SQLAlchemy 2.0 async (`Mapped`, `mapped_column`, `selectinload`/`joinedload`) |
| Migrations | Alembic (async) |
| Validation & OpenAPI | Pydantic v2 + FastAPI built-in Swagger UI (`/docs`) & ReDoc (`/redoc`) |
| Auth | PyJWT (short-lived access tokens + refresh tokens) & `pwdlib[argon2]` |
| Testing | `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx` |
| Lint & Format | `ruff` (`check` + `format`) & `pre-commit` |
| Production Server | Gunicorn with `uvicorn.workers.UvicornWorker` |
| Containers & CI | Docker, Docker Compose, GitHub Actions |

---

## 3. Project Structure

```
.
├── app/
│   ├── main.py                 # create_app() factory + ASGI app entrypoint
│   ├── core/
│   │   ├── config.py           # Typed pydantic-settings with production guards
│   │   ├── logging.py          # Structured JSON logging with request_id
│   │   └── security.py         # Argon2 hashing + JWT access/refresh tokens
│   ├── db/
│   │   ├── base.py             # SQLAlchemy Base + constraint naming convention
│   │   └── session.py          # Async engine & session factory
│   ├── common/
│   │   ├── errors.py           # Domain exception hierarchy + JSON error envelope
│   │   ├── middleware.py       # RequestID + SecurityHeaders middleware
│   │   ├── pagination.py       # Capped page/per_page params & PaginatedResponse
│   │   ├── rate_limit.py       # Sliding-window rate limiter for auth routes
│   │   └── utils.py            # Pure helpers (slugify, progress %, password rules)
│   ├── models/                 # SQLAlchemy ORM models & enums
│   ├── schemas/                # Separate Create / Update / Read Pydantic models
│   ├── services/               # Pure business logic & ownership/RBAC enforcement
│   └── api/
│       ├── deps.py             # DB session, JWT auth, optional auth, require_roles
│       └── v1/                 # health, auth, users, courses, enrollments, progress, reviews, certificates, quizzes
├── alembic/                    # Async Alembic migrations
├── docs/
│   └── API_CONVENTIONS.md      # Error envelope, pagination, auth & RBAC matrix
├── tests/
│   ├── conftest.py             # Isolated DB & role auth fixtures
│   ├── factories.py            # Async test record builders
│   ├── unit/                   # Pure unit tests (security, utils, schemas)
│   └── integration/            # End-to-end API & permission matrix tests
├── Dockerfile                  # Non-root slim Python 3.12 + Gunicorn image
├── docker-compose.yaml         # Postgres + one-shot migrate + API stack
└── .github/workflows/ci.yml    # Lint, format, migration & coverage CI
```

---

## 4. Local Setup

### Prerequisites
- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)
- Docker & Docker Compose (for local PostgreSQL)

### Steps

1. **Install dependencies into `.venv`:**
   ```bash
   uv sync --python 3.12
   ```

2. **Create `.env` from `.env.example`:**
   ```bash
   cp .env.example .env
   ```
   Update `SECRET_KEY` and `JWT_SECRET_KEY` with strong random secrets (e.g. `openssl rand -hex 32`).

3. **Start PostgreSQL:**
   ```bash
   docker compose up -d db
   ```

4. **Run database migrations:**
   ```bash
   uv run alembic upgrade head
   ```

5. **Run the development server:**
   ```bash
   uv run fastapi dev app/main.py
   ```

6. **Explore OpenAPI / Swagger UI:**
   - Swagger UI: `http://127.0.0.1:8000/docs`
   - ReDoc: `http://127.0.0.1:8000/redoc`
   - Health check: `http://127.0.0.1:8000/api/v1/health`

---

## 5. Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `PROJECT_NAME` | No | `LMS API` | API title shown in OpenAPI docs |
| `ENVIRONMENT` | No | `development` | `local`, `development`, `testing`, or `production` |
| `DEBUG` | No | `false` | Must be `false` in `production` |
| `LOG_LEVEL` | No | `INFO` | Root logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `DATABASE_URL` | **Yes** | — | Async SQLAlchemy URL (`postgresql+asyncpg://...`); URL-encode special characters in credentials (for example, `@` as `%40`) |
| `SECRET_KEY` | **Yes** | — | App secret (>= 32 chars required in `production`) |
| `JWT_SECRET_KEY` | **Yes** | — | JWT signing key (>= 32 chars required in `production`) |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `15` | Short-lived access token lifetime (minutes) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | Refresh token lifetime (days) |
| `CORS_ORIGINS` | No | `["http://localhost:3000"]` | JSON array of explicit allowed CORS origins |
| `RATE_LIMIT_ENABLED` | No | `true` | Enable sliding-window rate limiting on auth routes |
| `AUTH_RATE_LIMIT_REQUESTS` | No | `10` | Max requests per window per IP on register/login |
| `AUTH_RATE_LIMIT_WINDOW_SECONDS` | No | `60` | Rate limit window in seconds |
| `SENTRY_DSN` | No | `""` | Optional Sentry DSN for error tracking; SDK stays disabled when empty |
| `SENTRY_TRACES_SAMPLE_RATE` | No | `0.1` | Fraction of traces sent to Sentry (`0.0`-`1.0`); `0.0` disables new traces |
| `SENTRY_CAPTURE_LOGS` | No | `true` | Forward standard-library `logging` records to Sentry Logs |
| `SENTRY_AI_CAPTURE_INPUTS` | No | `true` | Send GenAI prompts/input messages to Sentry Agent Tracing |
| `SENTRY_AI_CAPTURE_OUTPUTS` | No | `true` | Send GenAI responses/output messages to Sentry Agent Tracing |

### Sentry Agent Tracing and conversations

With `SENTRY_DSN` set, the SDK enables tracing and GenAI input/output capture. Supported AI libraries are instrumented automatically when installed, so their model and tool calls appear as `gen_ai` spans on the surrounding request trace. The app has no AI calls of its own yet; adding a supported library (OpenAI, Anthropic, LangChain, and others) is all that is needed to start producing spans.

Send `X-Sentry-Conversation-ID: conv_<stable-session-id>` on every request of a chat session to group its spans into one Sentry conversation. Use a short opaque ID (letters, digits, `-`, `_`) and reuse it across turns and traces. Authenticated users are attached to the Sentry scope automatically so the Conversations view shows who started each chat. See the [Python Agent Tracing guide](https://docs.sentry.io/platforms/python/agent-tracing/) for details.

---

## 6. Key API Endpoints (`/api/v1`)

See [`docs/API_CONVENTIONS.md`](docs/API_CONVENTIONS.md) for error format, pagination, auth headers, and the full RBAC matrix.

- **Health**: `GET /health`, `GET /api/v1/health`
- **Auth**: `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`
- **Users**: `GET /users/me`, `PATCH /users/me`, `GET /users/me/enrollments`, plus Admin routes `GET/PATCH/DELETE /users/{id}`, `POST /users/{id}/deactivate`, `POST /users/{id}/activate`
- **Courses**: `GET /courses` (published, paginated, searchable), `GET /courses/manage`, `POST /courses`, `GET|PATCH|DELETE /courses/{id}`, `POST /courses/{id}/publish|unpublish|archive`, `GET /courses/{id}/roster`
- **Modules**: `GET|POST /courses/{id}/modules`, `PUT /courses/{id}/modules/reorder`, `PATCH|DELETE /modules/{id}`
- **Lessons**: `POST /modules/{id}/lessons`, `PUT /modules/{id}/lessons/reorder`, `GET|PATCH|DELETE /lessons/{id}` (full content gated to enrolled users, instructor, and admin)
- **Enrollments**: `POST|DELETE /courses/{id}/enroll`
- **Progress**: `POST|DELETE /lessons/{id}/complete`, `GET /courses/{id}/progress`

---

## 7. Migrations, Testing & Quality

```bash
# Create a new migration after model edits
uv run alembic revision --autogenerate -m "describe change"

# Apply / rollback migrations
uv run alembic upgrade head
uv run alembic downgrade -1

# Run full test suite with coverage
uv run pytest --cov=app --cov-report=term-missing

# Lint and format
uv run ruff check .
uv run ruff format --check .
```

To run integration tests against PostgreSQL instead of in-memory SQLite:

```bash
TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/lms_test" uv run pytest
```

---

## 8. Production & Containers

Run the full containerized stack (Postgres, one-shot `migrate` release job, and Gunicorn API):

```bash
docker compose up --build -d
```

Migrations run as a dedicated release step (`migrate` service / release command `alembic upgrade head`) rather than inside application worker boot.
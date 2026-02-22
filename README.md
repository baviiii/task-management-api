# Task Management API

A robust Task Management API built with **FastAPI** and **PostgreSQL**, supporting advanced filtering, tagging, and deadlines.

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)

### Run with Docker (recommended)

```bash
git clone <repo-url>
cd task-management-api
docker compose up --build
```

The API will be available at **http://localhost:8000**.

Interactive Swagger docs: **http://localhost:8000/docs**

### Run locally (without Docker)

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set the database URL (requires a running PostgreSQL instance)
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/taskdb

uvicorn app.main:app --reload
```

---

## API Endpoints

| Method   | Endpoint         | Description                          |
|----------|------------------|--------------------------------------|
| `GET`    | `/`              | Health check                         |
| `POST`   | `/tasks`         | Create a new task                    |
| `GET`    | `/tasks`         | List tasks (filter, paginate)        |
| `GET`    | `/tasks/{id}`    | Get a single task                    |
| `PATCH`  | `/tasks/{id}`    | Partially update a task              |
| `DELETE` | `/tasks/{id}`    | Soft-delete a task                   |

### POST /tasks

**Request body:**

```json
{
  "title": "Finish report",
  "description": "Q4 financial report",
  "priority": 4,
  "due_date": "2026-03-15",
  "tags": ["work", "urgent"]
}
```

- `title` — Required, 1–200 characters.
- `description` — Optional.
- `priority` — Required, integer 1–5 (5 = highest).
- `due_date` — Required, ISO format `YYYY-MM-DD`, must not be in the past.
- `tags` — Optional list of strings.

### GET /tasks

**Query parameters:**

| Param       | Type    | Description                                       |
|-------------|---------|---------------------------------------------------|
| `completed` | bool    | Filter by completion status                       |
| `priority`  | int     | Filter by exact priority level (1–5)              |
| `tags`      | string  | Comma-separated tag names (matches **any**)       |
| `limit`     | int     | Page size (default 20, max 100)                   |
| `offset`    | int     | Number of items to skip (default 0)               |

**Example:** `GET /tasks?priority=5&tags=work,urgent&limit=10&offset=0`

### PATCH /tasks/{id}

Only fields included in the request body are modified. Omitted fields remain unchanged.

```json
{
  "completed": true,
  "tags": ["done"]
}
```

### DELETE /tasks/{id}

Returns `204 No Content` on success.

---

## Design Decisions

### Database: PostgreSQL

PostgreSQL is the preferred choice for production workloads. It provides robust indexing, ACID compliance, and excellent support for concurrent access. The app connects via `asyncpg` for fully async I/O.

### Tagging: Join Table (many-to-many)

The tagging system uses a **normalized join table** approach:

- `tags` table — stores unique tag names.
- `task_tags` association table — links tasks to tags.

**Why not PostgreSQL ARRAY or JSONB?**

| Approach    | Pros                              | Cons                                          |
|-------------|-----------------------------------|-----------------------------------------------|
| Join Table  | Normalized, indexable, no duplication, easy to query with JOINs | Slightly more complex queries |
| ARRAY       | Simple schema, easy writes        | Hard to index for containment queries, duplication risk |
| JSONB       | Flexible schema                   | Overkill for simple string tags, harder to enforce constraints |

The join table approach was chosen because it:
- Avoids tag name duplication across tasks.
- Allows efficient filtering using standard SQL JOINs and `IN` clauses.
- Scales well as the number of tags grows.
- Makes it easy to extend tags with additional attributes (e.g., color, category) in the future.

### Deletion: Soft Delete

Tasks are **soft-deleted** by setting `is_deleted = True` and recording `deleted_at`. They are excluded from all list and get queries.

**Justification:**
- Preserves data for audit trails and analytics.
- Allows easy "undo" functionality in the future.
- No risk of accidental permanent data loss.
- Minimal performance impact with proper indexing.

### Indexing Strategy

The following indexes are applied for efficient filtering:

- `ix_task_priority` — on `priority` column.
- `ix_task_completed` — on `completed` column.
- `ix_task_is_deleted` — on `is_deleted` column.
- `ix_task_composite_filter` — composite index on `(is_deleted, completed, priority)` for the most common filter combination.
- Unique index on `tags.name` — for fast tag lookups and deduplication.

### Why I built it this way

I chose the **join table** for tasks and tags because I wanted tag names stored once and filterable with plain SQL—no duplication, and easy to add more tag metadata later. **Soft delete** felt right for anything that might need audit or undo; I’d rather hide rows than lose them. For **PATCH**, I used Pydantic’s `exclude_unset=True` so only the fields sent in the body are updated; that keeps partial updates predictable and avoids overwriting with `null` by mistake.

**Validation** lives in the Pydantic schemas (including a custom validator for “due_date not in the past”) so invalid input is rejected before we touch the database, and we always return the same error shape. **Tests** override the DB dependency to use SQLite by default, so the suite runs with zero setup, but I added `TEST_DATABASE_URL` so we can run the same tests against Postgres when needed.

If I were to extend this further, I’d run **Alembic migrations** in deployment instead of `create_all` at startup, and add a **readiness check** that pings the database so orchestrators know the app is really ready.

---

## Running Tests

### Why SQLite by default?

The test suite defaults to **SQLite** (via `aiosqlite`) so that:

- **No extra setup** — You can run `pytest` without starting PostgreSQL. Great for CI (e.g. GitHub Actions) and for developers who don’t have Postgres running.
- **Fast** — SQLite is quick to spin up and tear down; the same schema and app code run against it.

The app is written for **PostgreSQL** in production; SQLite is only a convenience for tests. For this API (standard CRUD, dates, integers), behavior is the same in both. If you want to run tests against real Postgres (e.g. to catch dialect-specific issues), use the option below.

### Default: run tests with SQLite

```bash
# Install dependencies
pip install -r requirements.txt

# Run the test suite (uses SQLite by default)
pytest -v
```

### Run tests against your own PostgreSQL

Set `TEST_DATABASE_URL` to your Postgres URL. Use a **dedicated test database** (e.g. `taskdb_test`) so tests don’t touch real data.

**Windows (PowerShell):**

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/taskdb_test"
pytest -v
```

**Linux/macOS:**

```bash
export TEST_DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/taskdb_test
pytest -v
```

Create the test database once (e.g. in `psql` or pgAdmin):

```sql
CREATE DATABASE taskdb_test;
```

Tests will create and drop tables in that DB for each run.

### With Docker

```bash
docker compose run --rm api pytest -v
```

To run tests against the Postgres container from the host, point `TEST_DATABASE_URL` at `localhost:5432` (with port exposed) and use a test DB name.

### CI (GitHub Actions)

On every push and pull request to `main` or `master`, GitHub Actions runs:

- **Lint** — Ruff checks `app/` and `tests/` for code style and common issues.
- **Test** — Full pytest suite using SQLite (no PostgreSQL required in CI).

Workflow file: [.github/workflows/ci.yml](.github/workflows/ci.yml).

The test suite covers:
- ✅ Successful task creation
- ✅ Validation failures (missing fields, invalid priority, past dates)
- ✅ Filtering by priority, completion status, and tags
- ✅ Pagination (limit/offset)
- ✅ Partial updates (PATCH) — individual fields, tags, edge cases
- ✅ Soft delete behavior
- ✅ 404 handling for nonexistent/deleted tasks

---

## Project Structure

```
task-management-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── config.py             # Settings (pydantic-settings)
│   ├── database.py           # Async SQLAlchemy engine & session
│   ├── models.py             # ORM models (Task, Tag, task_tags)
│   ├── schemas.py            # Pydantic request/response schemas
│   ├── exceptions.py         # Custom exception handlers
│   └── routers/
│       ├── __init__.py
│       └── tasks.py          # /tasks endpoints
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Test fixtures & DB setup
│   └── test_tasks.py         # Test suite
├── alembic/                  # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
├── .env.example
├── .gitignore
└── README.md
```

---

## Error Handling

All errors return a consistent JSON structure:

```json
{
  "error": "Validation Failed",
  "details": {
    "priority": "Must be between 1 and 5"
  }
}
```

- `422` — Validation errors (Pydantic).
- `404` — Resource not found.
- `500` — Internal server error.

---

## Production Readiness Improvements

### Production & scaling

I built this to be correct and maintainable first. The app is stateless and fully async, so you can run multiple instances behind a load balancer and they’ll behave the same. Pagination and the indexes we added are there so list endpoints don’t fall over as data grows—so the bones are there for scaling.

For real high load I’d add a few things: tune the DB connection pool (size, overflow, recycle) so we don’t exhaust Postgres under concurrency; put something like Redis in front of the hot read paths (e.g. list tasks) and invalidate on write; and add rate limiting so one client can’t hammer the API. I didn’t add those in the first version because the brief was about a solid, working API—I’d introduce them when we have real traffic and metrics, rather than over-engineering up front.

The items below are what I’d do before calling this production-ready: auth, rate limiting, observability, proper migrations, and optionally caching and pool tuning depending on load.

The following enhancements would be recommended before deploying this API to a production environment:

### Authentication & Authorization
- Add JWT-based authentication (e.g., `python-jose` + `passlib`).
- Implement role-based access control (RBAC) so users can only manage their own tasks.
- Add API key or OAuth2 support for third-party integrations.

### Rate Limiting & Security
- Add rate limiting middleware (e.g., `slowapi`) to prevent abuse.
- Enable CORS with a strict allow-list of origins instead of open access.
- Add request-size limits and input sanitization to mitigate injection attacks.
- Use HTTPS termination via a reverse proxy (e.g., Nginx, Traefik).

### Observability & Monitoring
- Integrate structured logging (e.g., `structlog` or `python-json-logger`) with correlation IDs per request.
- Add health check endpoints for readiness (`/health/ready`) and liveness (`/health/live`) probes.
- Export metrics via Prometheus (`prometheus-fastapi-instrumentator`) for latency, error rates, and throughput.
- Integrate distributed tracing (e.g., OpenTelemetry) for debugging across services.

### Database & Data Layer
- Run Alembic migrations as part of the deployment pipeline rather than auto-creating tables at startup.
- Add connection pooling tuning (pool size, overflow, recycle) for production traffic.
- Implement database read replicas for read-heavy workloads.
- Add a periodic cleanup job to hard-delete soft-deleted tasks older than a retention window.
- Consider partitioning the `tasks` table by `created_at` if the dataset grows very large.

### Caching
- Add Redis-backed caching for frequently accessed task listings.
- Use cache invalidation on writes (POST/PATCH/DELETE).
- Cache tag lookups to avoid repeated DB hits for the same tag names.

### CI/CD & Testing
- Add a CI pipeline (GitHub Actions / GitLab CI) that runs linting (`ruff`), type checking (`mypy`), and the full test suite on every push.
- Add load/stress testing (e.g., `locust`) to validate performance under concurrent requests.
- Introduce integration tests against a real PostgreSQL instance (via Docker-in-CI).
- Add code coverage reporting with a minimum threshold gate.

### API Versioning & Pagination
- Version the API (`/api/v1/tasks`) to support future breaking changes without disrupting clients.
- Consider cursor-based pagination for more consistent results under concurrent writes (offset-based can skip/duplicate rows).

### Configuration & Secrets
- Use a secrets manager (e.g., AWS Secrets Manager, HashiCorp Vault) instead of `.env` files.
- Separate configuration per environment (dev, staging, production) using environment-specific `.env` files or config maps.

---

## Technologies

- **Python 3.12**
- **FastAPI** — async web framework
- **SQLAlchemy 2.x** — async ORM
- **PostgreSQL 16** — production database
- **Alembic** — database migrations
- **Pydantic v2** — data validation
- **pytest + httpx** — async test suite
- **Docker + Docker Compose** — containerization

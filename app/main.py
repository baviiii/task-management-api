from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import Base, engine
from app.exceptions import http_exception_handler, validation_exception_handler
from app.routers.tasks import router as tasks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Task Management API",
    description=(
        "A robust Task Management API supporting advanced filtering, tagging, and deadlines.\n\n"
        "## Features\n"
        "- **Task CRUD** — Create, read, update (partial), and soft-delete tasks\n"
        "- **Tagging** — Assign multiple tags to tasks; filter by any matching tag\n"
        "- **Filtering** — Filter by completion status, priority level, and tags\n"
        "- **Pagination** — Limit/offset pagination with total count\n"
        "- **Validation** — Strict input validation with structured error responses\n\n"
        "## Tech Stack\n"
        "FastAPI · SQLAlchemy 2 (async) · PostgreSQL · Pydantic v2 · Docker"
    ),
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Health", "description": "Health check endpoint"},
        {"name": "Tasks", "description": "Task management operations — create, list, read, update, and delete tasks"},
    ],
)

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.include_router(tasks_router)


@app.get("/", tags=["Health"], summary="Health check")
async def root():
    return {"status": "ok", "message": "Task Management API is running"}

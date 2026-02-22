import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Tag, Task
from app.schemas import ErrorDetail, PaginatedTaskResponse, TaskCreate, TaskResponse, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["Tasks"])


async def _get_or_create_tags(db: AsyncSession, tag_names: list[str]) -> list[Tag]:
    """Fetch existing tags or create new ones."""
    tags = []
    for name in tag_names:
        result = await db.execute(select(Tag).where(Tag.name == name))
        tag = result.scalar_one_or_none()
        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
            await db.flush()
        tags.append(tag)
    return tags


@router.post(
    "",
    response_model=TaskResponse,
    status_code=201,
    summary="Create a new task",
    description=(
        "Create a new task with a title, optional description, priority (1-5), "
        "due date (ISO YYYY-MM-DD, must not be in the past), and optional tags. "
        "Tags are normalised to lowercase and deduplicated."
    ),
    responses={
        201: {"description": "Task created successfully"},
        422: {"model": ErrorDetail, "description": "Validation error (e.g. missing title, invalid priority, past due date)"},
    },
)
async def create_task(payload: TaskCreate, db: AsyncSession = Depends(get_db)) -> Task:
    task = Task(
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        due_date=datetime.date.fromisoformat(payload.due_date),
    )
    if payload.tags:
        task.tags = await _get_or_create_tags(db, payload.tags)
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return task


@router.get(
    "",
    response_model=PaginatedTaskResponse,
    summary="List tasks with filtering and pagination",
    description=(
        "Retrieve tasks filtered by completion status, priority level, and/or tags (CSV, matches ANY). "
        "Supports pagination via limit/offset. Soft-deleted tasks are always excluded. "
        "Results are ordered by creation date (newest first)."
    ),
    responses={
        200: {"description": "Paginated list of tasks"},
        422: {"model": ErrorDetail, "description": "Invalid query parameter (e.g. priority out of range)"},
    },
)
async def list_tasks(
    completed: Optional[bool] = Query(None, description="Filter by completion status"),
    priority: Optional[int] = Query(None, ge=1, le=5, description="Filter by priority level (1-5)"),
    tags: Optional[str] = Query(None, description="Comma-separated tag names (matches any)"),
    limit: int = Query(20, ge=1, le=100, description="Max number of tasks to return"),
    offset: int = Query(0, ge=0, description="Number of tasks to skip"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Base filter: exclude soft-deleted
    filters = [Task.is_deleted == False]  # noqa: E712

    if completed is not None:
        filters.append(Task.completed == completed)
    if priority is not None:
        filters.append(Task.priority == priority)

    # Build base query
    query = select(Task).where(*filters)

    # Tag filtering: tasks matching ANY of the provided tags
    if tags:
        tag_names = [t.strip().lower() for t in tags.split(",") if t.strip()]
        if tag_names:
            query = query.join(Task.tags).where(Tag.name.in_(tag_names)).distinct()

    # Count total matching tasks
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Apply pagination and eager-load tags
    query = query.options(selectinload(Task.tags)).order_by(Task.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    tasks = result.scalars().unique().all()

    return {"total": total, "limit": limit, "offset": offset, "tasks": tasks}


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get a task by ID",
    description="Retrieve a single task by its ID. Returns 404 if the task does not exist or has been soft-deleted.",
    responses={
        200: {"description": "Task found"},
        404: {"model": ErrorDetail, "description": "Task not found or has been deleted"},
    },
)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)) -> Task:
    result = await db.execute(
        select(Task).options(selectinload(Task.tags)).where(Task.id == task_id, Task.is_deleted == False)  # noqa: E712
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Partially update a task",
    description=(
        "Update only the fields provided in the request body. Omitted fields remain unchanged. "
        "When updating tags, the provided list fully replaces the existing tags. "
        "An empty tag list clears all tags from the task."
    ),
    responses={
        200: {"description": "Task updated successfully"},
        404: {"model": ErrorDetail, "description": "Task not found or has been deleted"},
        422: {"model": ErrorDetail, "description": "Validation error on provided fields"},
    },
)
async def update_task(task_id: int, payload: TaskUpdate, db: AsyncSession = Depends(get_db)) -> Task:
    result = await db.execute(
        select(Task).options(selectinload(Task.tags)).where(Task.id == task_id, Task.is_deleted == False)  # noqa: E712
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "tags" in update_data:
        tag_names = update_data.pop("tags")
        if tag_names is not None:
            task.tags = await _get_or_create_tags(db, tag_names)
        else:
            task.tags = []

    if "due_date" in update_data and update_data["due_date"] is not None:
        update_data["due_date"] = datetime.date.fromisoformat(update_data["due_date"])

    for field, value in update_data.items():
        setattr(task, field, value)

    await db.flush()
    await db.refresh(task)
    return task


@router.delete(
    "/{task_id}",
    status_code=204,
    summary="Soft-delete a task",
    description=(
        "Mark a task as deleted (soft delete). The task will no longer appear in listings or "
        "be retrievable by ID. The record is retained in the database for audit purposes."
    ),
    responses={
        204: {"description": "Task deleted successfully"},
        404: {"model": ErrorDetail, "description": "Task not found or already deleted"},
    },
)
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.is_deleted == False)  # noqa: E712
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    task.is_deleted = True
    task.deleted_at = datetime.datetime.now(datetime.timezone.utc)
    await db.flush()

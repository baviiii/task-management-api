import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class TaskCreate(BaseModel):
    """Schema for creating a new task."""

    title: str = Field(..., min_length=1, max_length=200, description="Task title (required, max 200 chars)")
    description: Optional[str] = Field(None, description="Optional task description")
    priority: int = Field(..., ge=1, le=5, description="Priority level 1-5 (5 is highest)")
    due_date: str = Field(..., description="Due date in ISO format YYYY-MM-DD")
    tags: Optional[list[str]] = Field(default=None, description="Optional list of tag names")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Finish quarterly report",
                    "description": "Complete the Q4 financial report for stakeholders",
                    "priority": 4,
                    "due_date": "2026-03-15",
                    "tags": ["work", "urgent"],
                }
            ]
        }
    }

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, v: str) -> str:
        try:
            parsed = datetime.date.fromisoformat(v)
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD.")
        if parsed < datetime.date.today():
            raise ValueError("due_date must not be in the past.")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is not None:
            cleaned = [tag.strip().lower() for tag in v if tag.strip()]
            return cleaned if cleaned else None
        return v


class TaskUpdate(BaseModel):
    """Schema for partially updating a task. Only fields provided will be modified."""

    title: Optional[str] = Field(None, min_length=1, max_length=200, description="Task title")
    description: Optional[str] = Field(None, description="Task description")
    priority: Optional[int] = Field(None, ge=1, le=5, description="Priority level 1-5")
    due_date: Optional[str] = Field(None, description="Due date in ISO format YYYY-MM-DD")
    completed: Optional[bool] = Field(None, description="Task completion status")
    tags: Optional[list[str]] = Field(None, description="List of tag names (replaces existing tags)")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Updated report title",
                    "completed": True,
                    "tags": ["done"],
                }
            ]
        }
    }

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                parsed = datetime.date.fromisoformat(v)
            except ValueError:
                raise ValueError("Invalid date format. Use YYYY-MM-DD.")
            if parsed < datetime.date.today():
                raise ValueError("due_date must not be in the past.")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is not None:
            cleaned = [tag.strip().lower() for tag in v if tag.strip()]
            return cleaned if cleaned else None
        return v


class TagResponse(BaseModel):
    """Schema for tag in responses."""

    id: int
    name: str

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    """Full task object returned by the API."""

    id: int
    title: str
    description: Optional[str] = None
    priority: int
    due_date: datetime.date
    completed: bool
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    tags: list[TagResponse] = []

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "title": "Finish quarterly report",
                    "description": "Complete the Q4 financial report",
                    "priority": 4,
                    "due_date": "2026-03-15",
                    "completed": False,
                    "is_deleted": False,
                    "created_at": "2026-02-20T10:30:00Z",
                    "updated_at": "2026-02-20T10:30:00Z",
                    "tags": [{"id": 1, "name": "work"}, {"id": 2, "name": "urgent"}],
                }
            ]
        },
    }


class PaginatedTaskResponse(BaseModel):
    """Paginated list of tasks with total count for client-side pagination."""

    total: int = Field(..., description="Total number of matching tasks")
    limit: int = Field(..., description="Maximum number of tasks returned")
    offset: int = Field(..., description="Number of tasks skipped")
    tasks: list[TaskResponse] = Field(..., description="List of task objects")


class ErrorDetail(BaseModel):
    """Structured error response returned for validation and HTTP errors."""

    error: str = Field(..., description="High-level error message")
    details: dict[str, Any] = Field(default={}, description="Field-level error details")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "error": "Validation Failed",
                    "details": {"priority": "Input should be less than or equal to 5"},
                }
            ]
        }
    }

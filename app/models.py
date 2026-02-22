import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base

# Association table for many-to-many Task <-> Tag
task_tags = Table(
    "task_tags",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)

    tasks = relationship("Task", secondary=task_tags, back_populates="tags")

    def __repr__(self) -> str:
        return f"<Tag(id={self.id}, name='{self.name}')>"


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_task_completed", "completed"),
        Index("ix_task_priority", "priority"),
        Index("ix_task_is_deleted", "is_deleted"),
        Index("ix_task_composite_filter", "is_deleted", "completed", "priority"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Integer, nullable=False, default=1)
    due_date = Column(Date, nullable=False)
    completed = Column(Boolean, nullable=False, default=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tags = relationship("Tag", secondary=task_tags, back_populates="tasks", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title='{self.title}')>"

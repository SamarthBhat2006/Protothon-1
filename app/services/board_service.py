"""Kanban board service — CRUD operations for tasks."""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models import Task

logger = logging.getLogger(__name__)

VALID_STATUSES = {"todo", "in_progress", "done"}
VALID_PRIORITIES = {"low", "medium", "high", "critical"}


def get_all_tasks(db: Session) -> List[Task]:
    """Get all tasks ordered by creation date."""
    return db.query(Task).order_by(Task.created_at.desc()).all()


def get_tasks_by_status(db: Session, status: str) -> List[Task]:
    """Get tasks filtered by status."""
    return db.query(Task).filter(Task.status == status).order_by(Task.created_at.desc()).all()


def get_tasks_by_meeting(db: Session, meeting_id: int) -> List[Task]:
    """Get all tasks for a specific meeting."""
    return db.query(Task).filter(Task.meeting_id == meeting_id).order_by(Task.created_at.desc()).all()


def create_task(db: Session, task_data: dict) -> Task:
    """Create a new task."""
    task = Task(
        meeting_id=task_data.get("meeting_id"),
        title=task_data["title"],
        description=task_data.get("description", ""),
        assignee=task_data.get("assignee"),
        priority=task_data.get("priority", "medium"),
        status=task_data.get("status", "todo"),
        context=task_data.get("context", ""),
        feature_area=task_data.get("feature_area", ""),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    logger.info(f"Task created: #{task.id} — {task.title}")
    return task


def move_task(db: Session, task_id: int, new_status: str) -> Optional[Task]:
    """Move a task to a different column (status)."""
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {new_status}. Must be one of {VALID_STATUSES}")

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return None

    old_status = task.status
    task.status = new_status
    db.commit()
    db.refresh(task)
    logger.info(f"Task #{task.id} moved: {old_status} → {new_status}")
    return task


def update_task(db: Session, task_id: int, update_data: dict) -> Optional[Task]:
    """Update task fields."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return None

    for key, value in update_data.items():
        if hasattr(task, key) and key not in ("id", "created_at"):
            setattr(task, key, value)

    db.commit()
    db.refresh(task)
    logger.info(f"Task #{task.id} updated")
    return task


def delete_task(db: Session, task_id: int) -> bool:
    """Delete a task by ID."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return False

    db.delete(task)
    db.commit()
    logger.info(f"Task #{task_id} deleted")
    return True


def get_board_summary(db: Session) -> dict:
    """Get counts by status for the Kanban board."""
    todo = db.query(Task).filter(Task.status == "todo").count()
    in_progress = db.query(Task).filter(Task.status == "in_progress").count()
    done = db.query(Task).filter(Task.status == "done").count()
    return {
        "todo": todo,
        "in_progress": in_progress,
        "done": done,
        "total": todo + in_progress + done,
    }

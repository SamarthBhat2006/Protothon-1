"""Kanban Board API router — task CRUD and board management."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.board_service import (
    get_all_tasks,
    get_tasks_by_status,
    create_task,
    move_task,
    update_task,
    delete_task,
    get_board_summary,
)
from app.services.spark_service import get_meeting_analytics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/board", tags=["board"])


class TaskCreateRequest(BaseModel):
    title: str
    description: str = ""
    assignee: str = None
    priority: str = "medium"
    feature_area: str = ""
    meeting_id: int = None


class TaskMoveRequest(BaseModel):
    status: str


class TaskUpdateRequest(BaseModel):
    title: str = None
    description: str = None
    assignee: str = None
    priority: str = None
    feature_area: str = None


@router.get("/tasks")
async def get_tasks(status: Optional[str] = None, db: Session = Depends(get_db)):
    """Get all tasks, optionally filtered by status."""
    if status:
        tasks = get_tasks_by_status(db, status)
    else:
        tasks = get_all_tasks(db)

    return {
        "tasks": [
            {
                "id": t.id,
                "meeting_id": t.meeting_id,
                "title": t.title,
                "description": t.description,
                "assignee": t.assignee,
                "priority": t.priority,
                "status": t.status,
                "context": t.context,
                "feature_area": t.feature_area,
                "created_at": t.created_at.isoformat(),
            }
            for t in tasks
        ]
    }


@router.post("/tasks")
async def create_new_task(req: TaskCreateRequest, db: Session = Depends(get_db)):
    """Manually create a new task on the board."""
    task = create_task(db, req.dict())
    return {
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "created_at": task.created_at.isoformat(),
    }


@router.put("/tasks/{task_id}/move")
async def move_task_status(task_id: int, req: TaskMoveRequest, db: Session = Depends(get_db)):
    """Move a task to a different column (status)."""
    try:
        task = move_task(db, task_id, req.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "message": f"Task moved to {task.status}",
    }


@router.put("/tasks/{task_id}")
async def update_task_details(task_id: int, req: TaskUpdateRequest, db: Session = Depends(get_db)):
    """Update task details."""
    update_data = {k: v for k, v in req.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    task = update_task(db, task_id, update_data)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "message": "Task updated",
    }


@router.delete("/tasks/{task_id}")
async def delete_task_endpoint(task_id: int, db: Session = Depends(get_db)):
    """Delete a task."""
    if not delete_task(db, task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted", "id": task_id}


@router.get("/summary")
async def board_summary(db: Session = Depends(get_db)):
    """Get board summary with counts and analytics."""
    summary = get_board_summary(db)
    analytics = get_meeting_analytics()

    return {
        "board": summary,
        "analytics": analytics,
    }
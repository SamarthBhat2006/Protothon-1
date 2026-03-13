"""Meeting API router — upload, transcript, analysis endpoints."""
import os
import logging
import shutil
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Meeting, MeetingAnalysis, Task
from app.services.stt_service import transcribe_audio
from app.services.board_service import create_task
from app.services.spark_service import store_structured_data
from app.agents.meeting_agent.agent import analyze_meeting_transcript
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/meetings", tags=["meetings"])


@router.post("/upload")
async def upload_voice_meeting(
    file: UploadFile = File(...),
    title: str = Form("Voice Meeting"),
    language_code: str = Form("en-IN"),
    db: Session = Depends(get_db),
):
    """Upload a voice recording → transcribe with Sarvam AI → store meeting."""
    logger.info(f"Incoming voice upload: {file.filename} (title: {title}, lang: {language_code})")
    # Save uploaded file
    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Create meeting record
    meeting = Meeting(
        title=title,
        source_type="voice",
        audio_filename=file.filename,
        status="transcribing",
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    # Transcribe using Sarvam AI
    logger.info(f"Starting transcription for {file.filename} via Sarvam AI...")
    stt_result = await transcribe_audio(file_path, language_code)

    if stt_result["success"]:
        meeting.transcript = stt_result["transcript"]
        meeting.status = "pending"
        logger.info(f"Transcription successful for {file.filename}")
    else:
        meeting.status = "failed"
        db.commit()
        logger.error(f"STT failed for {file.filename}: {stt_result.get('error')}")
        raise HTTPException(status_code=500, detail=f"STT failed: {stt_result.get('error', 'Unknown error')}")

    db.commit()
    db.refresh(meeting)

    return {
        "id": meeting.id,
        "title": meeting.title,
        "source_type": meeting.source_type,
        "transcript": meeting.transcript,
        "status": meeting.status,
        "language": stt_result.get("language_code"),
        "mock": stt_result.get("mock", False),
    }


@router.post("/transcript")
async def submit_transcript(
    title: str = Form(None),
    transcript: str = Form(None),
    db: Session = Depends(get_db),
):
    """Submit a text transcript directly."""
    # Handle both JSON and form data
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript text is required")

    if not title:
        title = "Meeting " + str(db.query(Meeting).count() + 1)

    meeting = Meeting(
        title=title,
        transcript=transcript,
        source_type="text",
        status="pending",
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    return {
        "id": meeting.id,
        "title": meeting.title,
        "source_type": meeting.source_type,
        "status": meeting.status,
        "created_at": meeting.created_at.isoformat(),
    }


@router.post("/{meeting_id}/analyze")
async def analyze_meeting(meeting_id: int, db: Session = Depends(get_db)):
    """Trigger AI analysis on a meeting transcript."""
    logger.info(f"Starting analysis for meeting_id: {meeting_id}")
    from app.services.spark_service import store_raw_transcript, clean_and_structure_transcript, store_structured_data
    
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if not meeting.transcript:
        raise HTTPException(status_code=400, detail="Meeting has no transcript to analyze")

    meeting.status = "analyzing"
    db.commit()

    # 1. Delta Lake: Store Raw Data
    try:
        store_raw_transcript(meeting_id, meeting.transcript)
    except Exception as e:
        logger.warning(f"Failed to store raw transcript to Delta Lake: {e}")

    # 2. Spark: Data Cleaning & Structuring
    cleaned_transcript = meeting.transcript
    try:
        cleaned_transcript = clean_and_structure_transcript(meeting_id, meeting.transcript)
    except Exception as e:
        logger.warning(f"Failed to clean transcript via Spark: {e}")

    # 3. AI Intelligence Layer (Multi-Agent)
    logger.info(f"Running multi-agent analysis for meeting {meeting_id}...")
    try:
        result = await analyze_meeting_transcript(cleaned_transcript)
        logger.info(f"Multi-agent analysis complete for meeting {meeting_id}")
    except Exception as e:
        meeting.status = "failed"
        db.commit()
        logger.error(f"Analysis failed for meeting {meeting_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    # 4. Output & Workflow Layer (SQLite + Tasks)
    analysis = db.query(MeetingAnalysis).filter(MeetingAnalysis.meeting_id == meeting_id).first()
    if analysis:
        analysis.summary = result.get("summary", "")
        analysis.decisions = result.get("decisions", [])
        analysis.raw_response = str(result)
    else:
        analysis = MeetingAnalysis(
            meeting_id=meeting_id,
            summary=result.get("summary", ""),
            decisions=result.get("decisions", []),
            raw_response=str(result),
        )
        db.add(analysis)

    # Create tasks from action items
    action_items = result.get("action_items", [])
    created_tasks = []
    for item in action_items:
        task = create_task(db, {
            "meeting_id": meeting_id,
            "title": item.get("title", "Untitled Task"),
            "description": item.get("description", ""),
            "assignee": item.get("assignee"),
            "priority": item.get("priority", "medium"),
            "context": item.get("context", ""),
            "feature_area": item.get("feature_area", ""),
        })
        created_tasks.append(task)

    meeting.status = "analyzed"
    db.commit()
    db.refresh(meeting)

    # 5. Output Layer (Delta Tables generation)
    try:
        store_structured_data({
            "meeting_id": meeting.id,
            "title": meeting.title,
            "transcript": meeting.transcript,
            "summary": result.get("summary", ""),
            "decisions": result.get("decisions", []),
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "description": t.description,
                    "assignee": t.assignee,
                    "priority": t.priority,
                    "status": t.status,
                    "context": t.context,
                    "feature_area": t.feature_area,
                }
                for t in created_tasks
            ],
            "task_count": len(created_tasks),
            "source_type": meeting.source_type,
        })
    except Exception as e:
        logger.warning(f"Delta Lake structured store failed (non-critical): {e}")

    return {
        "meeting_id": meeting.id,
        "status": "analyzed",
        "summary": result.get("summary", ""),
        "decisions": result.get("decisions", []),
        "action_items_count": len(created_tasks),
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "assignee": t.assignee,
                "priority": t.priority,
                "status": t.status,
                "feature_area": t.feature_area,
            }
            for t in created_tasks
        ],
        "mock": result.get("mock", False),
    }


@router.get("/{meeting_id}/results")
async def get_meeting_results(meeting_id: int, db: Session = Depends(get_db)):
    """Get analysis results for a meeting."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    analysis = db.query(MeetingAnalysis).filter(MeetingAnalysis.meeting_id == meeting_id).first()
    tasks = db.query(Task).filter(Task.meeting_id == meeting_id).all()

    return {
        "meeting": {
            "id": meeting.id,
            "title": meeting.title,
            "transcript": meeting.transcript,
            "source_type": meeting.source_type,
            "status": meeting.status,
            "created_at": meeting.created_at.isoformat(),
        },
        "analysis": {
            "summary": analysis.summary if analysis else None,
            "decisions": analysis.decisions if analysis else [],
        } if analysis else None,
        "tasks": [
            {
                "id": t.id,
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
        ],
    }


@router.get("")
async def list_meetings(db: Session = Depends(get_db)):
    """List all meetings."""
    meetings = db.query(Meeting).order_by(Meeting.created_at.desc()).all()
    return {
        "meetings": [
            {
                "id": m.id,
                "title": m.title,
                "source_type": m.source_type,
                "status": m.status,
                "has_transcript": bool(m.transcript),
                "created_at": m.created_at.isoformat(),
            }
            for m in meetings
        ]
    }
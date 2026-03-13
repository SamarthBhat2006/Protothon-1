"""Delta Lake service — uses deltalake (delta-rs) for pure-Python Delta storage.
No Java or Spark required.
"""
import os
import logging
import json
import datetime
import re
import pyarrow as pa
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

DELTA_PATH = settings.DELTA_PATH or "./data/delta"


def _clean_transcript(raw: str) -> str:
    """Basic NLP-style cleaning of a transcript."""
    text = raw.strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s.,!?;:\'\"-]', '', text)
    return text


def store_raw_transcript(meeting_id: int, transcript: str):
    """Store raw transcript to the Delta Lake raw_transcripts table."""
    table_path = os.path.join(DELTA_PATH, "raw_transcripts")

    try:
        from deltalake import write_deltalake, DeltaTable

        cleaned = _clean_transcript(transcript)

        table = pa.table({
            "meeting_id": pa.array([meeting_id], type=pa.int64()),
            "raw_transcript": pa.array([transcript]),
            "cleaned_transcript": pa.array([cleaned]),
            "ingested_at": pa.array([datetime.datetime.now().isoformat()]),
        })

        write_deltalake(
            table_path,
            table,
            mode="append",
        )

        logger.info(f"Delta Lake: raw transcript stored for meeting {meeting_id}")

    except Exception as e:
        logger.error(f"Delta write failed: {e}")
        logger.warning("Falling back to JSON storage for raw transcript")
        _json_fallback(meeting_id, "raw", {
            "meeting_id": meeting_id,
            "raw_transcript": transcript,
            "cleaned_transcript": _clean_transcript(transcript),
            "ingested_at": datetime.datetime.now().isoformat(),
        })


def store_structured_data(meeting_id: int, analysis_result: dict):
    """Store structured analysis results to the Delta Lake structured_results table."""
    table_path = os.path.join(DELTA_PATH, "structured_results")

    try:
        from deltalake import write_deltalake

        table = pa.table({
            "meeting_id": pa.array([meeting_id], type=pa.int64()),
            "summary": pa.array([analysis_result.get("summary", "")]),
            "decisions": pa.array([json.dumps(analysis_result.get("decisions", []))]),
            "action_items": pa.array([json.dumps(analysis_result.get("action_items", []))]),
            "context": pa.array([json.dumps(analysis_result.get("context", {}))]),
            "processed_at": pa.array([datetime.datetime.now().isoformat()]),
        })

        write_deltalake(
            table_path,
            table,
            mode="append",
        )

        logger.info(f"Delta Lake: structured data stored for meeting {meeting_id}")

    except Exception as e:
        logger.error(f"Delta write failed: {e}")
        logger.warning("Falling back to JSON storage")
        _json_fallback(meeting_id, "structured", {
            "meeting_id": meeting_id,
            **analysis_result,
            "processed_at": datetime.datetime.now().isoformat(),
        })


def get_meeting_analytics() -> dict:
    """Read analytics from Delta Lake."""
    raw_path = os.path.join(DELTA_PATH, "raw_transcripts")
    structured_path = os.path.join(DELTA_PATH, "structured_results")

    analytics: dict[str, Any] = {"total_raw": 0, "total_structured": 0, "latest_meetings": []}

    try:
        from deltalake import DeltaTable

        if os.path.exists(raw_path) and DeltaTable.is_deltatable(raw_path):
            dt = DeltaTable(raw_path)
            analytics["total_raw"] = len(dt.to_pyarrow_table())

        if os.path.exists(structured_path) and DeltaTable.is_deltatable(structured_path):
            dt = DeltaTable(structured_path)
            tbl = dt.to_pyarrow_table()
            analytics["total_structured"] = len(tbl)

            # Get latest 5
            if len(tbl) > 0:
                rows = tbl.to_pydict()
                for i in range(min(5, len(rows["meeting_id"]))):
                    analytics["latest_meetings"].append({
                        "meeting_id": rows["meeting_id"][i],
                        "summary": rows["summary"][i][:100] if rows["summary"][i] else "",
                        "processed_at": rows["processed_at"][i],
                    })

    except Exception as e:
        logger.error(f"Delta analytics read failed: {e}")

    return analytics


def _json_fallback(meeting_id: int, data_type: str, data: dict):
    """Fallback: store as plain JSON when Delta Lake is unavailable."""
    fallback_dir = os.path.join(DELTA_PATH, "json_fallback")
    os.makedirs(fallback_dir, exist_ok=True)

    filepath = os.path.join(fallback_dir, f"meeting_{meeting_id}_{data_type}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Fallback JSON stored: {filepath}")
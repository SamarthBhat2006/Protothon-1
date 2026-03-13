"""PySpark + Delta Lake service — local mode, CPU-only."""
import os
import logging
import json
import datetime
import re
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Global SparkSession (lazy init)
_spark = None

def _get_spark():
    """Get or create a SparkSession with Delta Lake support."""
    global _spark
    if _spark is not None:
        return _spark

    try:
        from pyspark.sql import SparkSession

        _spark = (
            SparkSession.builder
            .appName("MeetingToAction")
            .master("local[*]")
            .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
            .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
            .config("spark.jars.packages", "io.delta:delta-spark_2.12:3.2.1")
            .config("spark.driver.memory", "1g")
            .config("spark.ui.enabled", "false")
            .getOrCreate()
        )
        _spark.sparkContext.setLogLevel("WARN")
        logger.info("SparkSession created successfully (local mode)")
    except Exception as e:
        logger.error(f"Failed to create SparkSession: {e}")
        _spark = None

    return _spark

def store_raw_transcript(meeting_id: int, transcript: str) -> bool:
    """Write raw meeting transcript to Delta Lake (Raw Data layer)."""
    spark = _get_spark()
    if spark is None:
        logger.warning("Spark unavailable — falling back to JSON storage for raw transcript")
        return _fallback_json_store({"meeting_id": meeting_id, "type": "raw", "transcript": transcript})

    try:
        from pyspark.sql.types import StructType, StructField, StringType, IntegerType
        
        schema = StructType([
            StructField("meeting_id", IntegerType(), False),
            StructField("raw_transcript", StringType(), True),
            StructField("ingested_at", StringType(), True),
        ])

        row_data = [{
            "meeting_id": meeting_id,
            "raw_transcript": transcript,
            "ingested_at": datetime.datetime.utcnow().isoformat(),
        }]

        df = spark.createDataFrame(row_data, schema=schema)
        delta_path = os.path.join(settings.DELTA_PATH, "raw_transcripts")
        os.makedirs(delta_path, exist_ok=True)
        df.write.format("delta").mode("append").save(delta_path)

        logger.info(f"Raw transcript for meeting {meeting_id} stored to Delta Lake")
        return True
    except Exception as e:
        logger.error(f"Delta Lake write error (Raw): {e}")
        return False

def clean_and_structure_transcript(meeting_id: int, transcript: str) -> str:
    """Use Spark to clean the transcript before sending to AI Intelligence layer."""
    spark = _get_spark()
    if spark is None:
        # Fallback basic cleaning
        return re.sub(r'\s+', ' ', transcript).strip()
    
    try:
        from pyspark.sql.types import StructType, StructField, StringType, IntegerType
        import pyspark.sql.functions as F

        # Load into Spark dataframe
        schema = StructType([StructField("id", IntegerType(), False), StructField("text", StringType(), True)])
        df = spark.createDataFrame([{"id": meeting_id, "text": transcript}], schema=schema)

        # Basic data cleaning transformations
        df_cleaned = df.withColumn(
            "cleaned_text", 
            F.trim(F.regexp_replace(F.col("text"), r"\s+", " "))  # Normalize whitespaces
        )

        cleaned_text = df_cleaned.collect()[0]["cleaned_text"]
        logger.info(f"Transcript cleaned for meeting {meeting_id}")
        return cleaned_text
    except Exception as e:
        logger.error(f"Spark Data Cleaning error: {e}")
        return re.sub(r'\s+', ' ', transcript).strip()

def store_structured_data(meeting_data: dict) -> bool:
    """
    Write structured meeting analysis data to Delta Lake tables (Tasks/Decisions/Summaries layer).
    """
    spark = _get_spark()
    if spark is None:
        logger.warning("Spark unavailable — falling back to JSON storage")
        return _fallback_json_store(meeting_data)

    try:
        from pyspark.sql.types import (
            StructType, StructField, StringType, IntegerType
        )

        schema = StructType([
            StructField("meeting_id", IntegerType(), False),
            StructField("title", StringType(), True),
            StructField("summary", StringType(), True),
            StructField("decisions", StringType(), True),
            StructField("task_count", IntegerType(), True),
            StructField("source_type", StringType(), True),
            StructField("processed_at", StringType(), True),
        ])

        row_data = [{
            "meeting_id": meeting_data.get("meeting_id"),
            "title": meeting_data.get("title", ""),
            "summary": meeting_data.get("summary", ""),
            "decisions": json.dumps(meeting_data.get("decisions", [])),
            "task_count": meeting_data.get("task_count", 0),
            "source_type": meeting_data.get("source_type", "text"),
            "processed_at": datetime.datetime.utcnow().isoformat(),
        }]

        df = spark.createDataFrame(row_data, schema=schema)

        delta_path = os.path.join(settings.DELTA_PATH, "structured_meetings")
        os.makedirs(delta_path, exist_ok=True)

        df.write.format("delta").mode("append").save(delta_path)

        logger.info(f"Structured data for meeting {meeting_data.get('meeting_id')} stored to Delta Lake")
        return True

    except Exception as e:
        logger.error(f"Delta Lake write error (Structured): {e}")
        return _fallback_json_store(meeting_data)

def get_meeting_analytics() -> dict:
    """Get analytics from Delta Lake — total meetings, tasks, etc."""
    spark = _get_spark()
    if spark is None:
        return _fallback_json_analytics()

    try:
        delta_path = os.path.join(settings.DELTA_PATH, "structured_meetings")
        if not os.path.exists(delta_path):
            return {"total_meetings": 0, "total_tasks": 0, "recent": []}

        df = spark.read.format("delta").load(delta_path)
        total_meetings = df.count()
        total_tasks = df.agg({"task_count": "sum"}).collect()[0][0] or 0

        recent = (
            df.orderBy(df.processed_at.desc())
            .limit(5)
            .select("meeting_id", "title", "task_count", "processed_at")
            .collect()
        )

        return {
            "total_meetings": total_meetings,
            "total_tasks": int(total_tasks),
            "recent": [row.asDict() for row in recent],
        }

    except Exception as e:
        logger.error(f"Delta Lake read error: {e}")
        return {"total_meetings": 0, "total_tasks": 0, "recent": [], "error": str(e)}

def _fallback_json_store(meeting_data: dict) -> bool:
    """Fallback: store as JSON when Spark is unavailable."""
    try:
        json_dir = os.path.join(settings.DELTA_PATH, "json_fallback")
        os.makedirs(json_dir, exist_ok=True)
        # Use a unique name including type to avoid overwriting raw with structured
        file_type = meeting_data.get("type", "structured")
        file_path = os.path.join(json_dir, f"meeting_{meeting_data.get('meeting_id', 'unknown')}_{file_type}.json")
        with open(file_path, "w") as f:
            json.dump(meeting_data, f, indent=2, default=str)
        logger.info(f"Fallback JSON stored: {file_path}")
        return True
    except Exception as e:
        logger.error(f"JSON fallback store error: {e}")
        return False

def _fallback_json_analytics() -> dict:
    """Fallback analytics from JSON files."""
    json_dir = os.path.join(settings.DELTA_PATH, "json_fallback")
    if not os.path.exists(json_dir):
        return {"total_meetings": 0, "total_tasks": 0, "recent": []}

    files = [f for f in os.listdir(json_dir) if f.endswith("_structured.json")]
    total_tasks = 0
    recent = []
    for f_name in sorted(files, reverse=True)[:5]:
        with open(os.path.join(json_dir, f_name)) as f:
            data = json.load(f)
            total_tasks += data.get("task_count", 0)
            recent.append({
                "meeting_id": data.get("meeting_id"),
                "title": data.get("title"),
                "task_count": data.get("task_count", 0),
                "processed_at": data.get("processed_at"),
            })

    return {
        "total_meetings": len(files),
        "total_tasks": total_tasks,
        "recent": recent,
    }
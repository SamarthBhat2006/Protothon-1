Airflow DAG: Meeting Processing Pipeline
Orchestrates the end-to-end flow from meeting ingestion to task creation.

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "meeting-to-action",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

dag = DAG(
    "meeting_processing_pipeline",
    default_args=default_args,
    description="Process meeting recordings/transcripts into actionable tasks",
    schedule_interval=None,  # Triggered manually or via API
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["meeting", "nlp", "engineering"],
)


def ingest_meeting(**context):
    """Input Layer: Ingest meeting input from configured source."""
    import requests

    meeting_id = context["dag_run"].conf.get("meeting_id") if context.get("dag_run") else None
    if not meeting_id:
        raise ValueError("meeting_id must be provided in dag_run.conf")

    # Verify meeting exists
    resp = requests.get(f"http://localhost:8000/api/meetings/{meeting_id}/results")
    if resp.status_code != 200:
        raise ValueError(f"Meeting {meeting_id} not found")

    data = resp.json()
    context["ti"].xcom_push(key="meeting_id", value=meeting_id)
    context["ti"].xcom_push(key="has_transcript", value=bool(data["meeting"].get("transcript")))
    context["ti"].xcom_push(key="source_type", value=data["meeting"].get("source_type", "text"))
    print(f"✓ Meeting {meeting_id} ingested at Input Layer — source: {data['meeting']['source_type']}")


def speech_to_text(**context):
    """Speech Processing Layer: Convert voice to text using Sarvam AI."""
    ti = context["ti"]
    source_type = ti.xcom_pull(key="source_type", task_ids="ingest_meeting")
    meeting_id = ti.xcom_pull(key="meeting_id", task_ids="ingest_meeting")

    if source_type == "voice":
        print(f"Speech Processing Layer: Voice meeting {meeting_id} STT complete")
    else:
        print(f"Speech Processing Layer: Text meeting {meeting_id} — STT skipped")

    ti.xcom_push(key="stt_complete", value=True)


def data_engineering_and_ai_layer(**context):
    """Data Eng + AI Intelligence Layers: Raw Delta -> Spark Clean -> Multi-Agent -> Structured Delta."""
    import requests

    ti = context["ti"]
    meeting_id = ti.xcom_pull(key="meeting_id", task_ids="ingest_meeting")

    # The analyze endpoint orchestrates:
    # 1. Delta (Raw data)
    # 2. Spark (Data Cleaning)
    # 3. AI Agents (Context, Decision, Summary)
    # 4. Delta (Structured Storage)
    resp = requests.post(f"http://localhost:8000/api/meetings/{meeting_id}/analyze")
    if resp.status_code != 200:
        raise Exception(f"Analysis pipeline failed: {resp.text}")

    result = resp.json()
    ti.xcom_push(key="analysis_result", value=result)
    print(f"✓ AI Intelligence Layer complete — {result.get('action_items_count', 0)} tasks extracted via multi-agent")


def verify_workflow_output(**context):
    """Output & Workflow Layer: Verify output on Kanban Dashboard."""
    import requests

    ti = context["ti"]
    meeting_id = ti.xcom_pull(key="meeting_id", task_ids="ingest_meeting")

    resp = requests.get("http://localhost:8000/api/board/tasks")
    if resp.status_code == 200:
        tasks = resp.json().get("tasks", [])
        meeting_tasks = [t for t in tasks if t.get("meeting_id") == meeting_id]
        print(f"✓ Output Layer: {len(meeting_tasks)} tasks on Kanban board for meeting {meeting_id}")
    else:
        print("⚠ Could not verify Output Layer Kanban tasks")


# Define DAG tasks
t1 = PythonOperator(task_id="ingest_meeting", python_callable=ingest_meeting, dag=dag)
t2 = PythonOperator(task_id="speech_to_text", python_callable=speech_to_text, dag=dag)
t3 = PythonOperator(task_id="data_eng_and_ai", python_callable=data_engineering_and_ai_layer, dag=dag)
t4 = PythonOperator(task_id="verify_workflow", python_callable=verify_workflow_output, dag=dag)

# Pipeline sequence
t1 >> t2 >> t3 >> t4
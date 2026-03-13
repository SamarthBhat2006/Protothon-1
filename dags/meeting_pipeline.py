from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

# Dummy imports - in reality, these will be the functions your teammates write!
# from backend.sarvam_api import transcribe_audio
# from ai.adk_agent import extract_tasks_with_gemini
# from ops.delta_lake import save_to_delta
# from integrations.github_mcp import create_tickets

def task_transcribe():
    print("Calling Sarvam AI API to transcribe audio...")
    # transcript = transcribe_audio('/opt/airflow/data/meeting.wav')
    # return transcript

def task_extract_action_items():
    print("Sending transcript to Gemini via Google ADK...")
    # tasks_json = extract_tasks_with_gemini(transcript)
    # return tasks_json

def task_save_to_delta():
    print("Using PySpark to save raw transcript and JSON to Delta Lake...")
    # save_to_delta(transcript, tasks_json)

def task_create_github_issues():
    print("Using MCP to create GitHub issues for the engineering team...")
    # create_tickets(tasks_json)

# Define the DAG
default_args = {
    'owner': 'data_ops_engineer',
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

with DAG(
    dag_id='meeting_to_action_pipeline',
    default_args=default_args,
    start_date=datetime(2026, 3, 13),
    schedule_interval=None, # Triggered manually or via API when a meeting ends
    catchup=False
) as dag:

    # Define the nodes (tasks)
    transcribe = PythonOperator(
        task_id='transcribe_audio_sarvam',
        python_callable=task_transcribe
    )

    extract = PythonOperator(
        task_id='extract_tasks_adk',
        python_callable=task_extract_action_items
    )

    save_delta = PythonOperator(
        task_id='save_to_delta_lake',
        python_callable=task_save_to_delta
    )

    create_tickets = PythonOperator(
        task_id='create_github_issues',
        python_callable=task_create_github_issues
    )

    # Define the flow (The >> operator is Airflow's version of drawing a line in n8n)
    transcribe >> extract >> [save_delta, create_tickets]

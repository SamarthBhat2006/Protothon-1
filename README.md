# ⚡ MeetAction AI — Meeting Intelligence System

> **Meeting → Transcript → AI Analysis → Action Items → Kanban Board**

An end-to-end AI-powered system that converts meeting recordings or text transcripts into structured action items on a Kanban board — using Sarvam AI for speech-to-text, Google Gemini 2.0 Flash (via ADK) for intelligent extraction, and Apache Spark + Delta Lake for data engineering.

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | HTML + Vanilla JS + Tailwind CSS |
| **Backend** | FastAPI (Python) |
| **Voice AI** | Sarvam AI API (standard + batch mode for long audio) |
| **Agentic AI** | Google ADK / Gemini 2.0 Flash |
| **Data Lake** | Apache Spark + Delta Lake |
| **Relational DB** | SQLite via SQLAlchemy |
| **Orchestration** | Apache Airflow |
| **Containerization** | Docker + Docker Compose |

---

## 📂 Code Structure

```
app/
├── main.py                  # FastAPI entry point, CORS, routers, startup
├── config.py                # Environment variable loader (from .env)
├── db/
│   ├── database.py          # SQLAlchemy engine, sessions, init_db
│   └── models.py            # ORM models: Meeting, MeetingAnalysis, Task
├── routers/
│   ├── meetings.py          # Audio upload, text transcript, analysis trigger
│   └── board.py             # Kanban task CRUD, move, board summary
├── services/
│   ├── stt_service.py       # Sarvam AI STT (standard <30s, batch >30s)
│   ├── spark_service.py     # PySpark + Delta Lake storage
│   └── board_service.py     # Task management business logic
├── agents/
│   └── meeting_agent/
│       └── agent.py         # Google ADK Master Agent (Gemini 2.0 Flash)
└── static/
    ├── index.html           # Dashboard UI
    ├── css/style.css         # Custom styles
    └── js/app.js             # Frontend logic (tabs, API calls, kanban, modals)

airflow/
└── dags/
    └── meetings_pipeline.py # DAG: Ingest → STT → AI Analysis → Board

data/                        # Runtime data (created automatically)
├── app.db                   # SQLite database
├── delta/                   # Delta Lake parquet files
└── uploads/                 # Uploaded audio files

Dockerfile                   # Python 3.11 + Java 17 (for PySpark)
docker-compose.yml           # app + airflow-webserver + airflow-scheduler
.env                         # API keys and configuration
requirements.txt             # Python dependencies
```

---

## 🌐 API Endpoints

### Meeting APIs (`/api/meetings`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/upload` | Upload audio file → Sarvam AI STT → create Meeting |
| `POST` | `/transcript` | Submit raw text transcript → create Meeting |
| `POST` | `/{id}/analyze` | Run AI analysis → extract tasks → save to Delta Lake |
| `GET` | `/` | List all meetings |
| `GET` | `/{id}/results` | Get analysis results for a specific meeting |

### Board APIs (`/api/board`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/tasks` | Get all tasks (grouped by status) |
| `PUT` | `/tasks/{id}/move` | Move task to a new status column |
| `PUT` | `/tasks/{id}` | Update task details |
| `DELETE` | `/tasks/{id}` | Delete a task |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Java 17+ (for PySpark)

### Local Setup

```bash
# 1. Clone and navigate
git clone <repo-url>
cd Protothon-1

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
# Edit .env with your API keys:
#   SARVAM_API_KEY=your_key
#   GOOGLE_API_KEY=your_key

# 5. Start the server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open **http://localhost:8000** for the dashboard, and **http://localhost:8000/docs** for the interactive API docs.

### Docker Setup

```bash
# Build and start all services
docker-compose up --build

# Services:
#   App:              http://localhost:8000
#   Airflow UI:       http://localhost:8080 (admin/admin)
```

---

## 🔄 Processing Pipeline

```
🎙️ Input Capture  →  🔊 Sarvam STT  →  🌐 Google ADK Agent  →  🗄️ Delta Lake  →  📋 Kanban Board
```

1. **Input Capture** — Upload audio or paste text transcript
2. **Sarvam STT** — Converts voice to text (auto-detects >30s for batch mode)
3. **Google ADK Agent** — Gemini 2.0 Flash extracts context, decisions, and action items
4. **Delta Lake** — Raw transcripts + structured results stored permanently via Spark
5. **Kanban Board** — Tasks appear on the board with priority, assignee, and status

---

## ⚙️ Environment Variables

| Variable | Description | Default |
|---|---|---|
| `SARVAM_API_KEY` | Sarvam AI API key for STT | _(mock mode if empty)_ |
| `GOOGLE_API_KEY` | Google AI API key for Gemini | _(mock mode if empty)_ |
| `DATABASE_URL` | SQLAlchemy connection string | `sqlite:///./data/app.db` |
| `DELTA_PATH` | Delta Lake storage path | `./data/delta` |
| `UPLOAD_DIR` | Audio upload directory | `./data/uploads` |

> **Note:** The system runs in mock mode when API keys are not set, returning simulated responses for testing.

---

## 📋 Airflow DAG

The `meetings_pipeline` DAG orchestrates the full pipeline:

```
ingest_meeting → speech_to_text → data_eng_and_ai → verify_workflow
```

Trigger it via the Airflow UI at `http://localhost:8080` with a config like:
```json
{ "meeting_id": 1 }
```
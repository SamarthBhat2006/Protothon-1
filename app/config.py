"""Application configuration — loads environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "AI Meeting-to-Action System"
    VERSION: str = "1.0.0"

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/meetings.db")

    # Sarvam AI
    SARVAM_API_KEY: str = os.getenv("SARVAM_API_KEY", "")

    # Google Gemini / ADK
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")

    # Delta Lake
    DELTA_PATH: str = os.getenv("DELTA_PATH", "./data/delta")

    # Upload directory
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./data/uploads")


settings = Settings()

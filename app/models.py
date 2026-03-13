"""SQLAlchemy ORM models for meetings, analyses, and tasks."""
import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    transcript = Column(Text, nullable=True)
    source_type = Column(String(20), nullable=False, default="text")  # "text" or "voice"
    audio_filename = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending / transcribing / analyzed / failed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    analysis = relationship("MeetingAnalysis", back_populates="meeting", uselist=False)
    tasks = relationship("Task", back_populates="meeting")


class MeetingAnalysis(Base):
    __tablename__ = "meeting_analyses"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, unique=True)
    summary = Column(Text, nullable=True)
    decisions = Column(JSON, nullable=True)  # list of decision strings
    raw_response = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    meeting = relationship("Meeting", back_populates="analysis")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    assignee = Column(String(255), nullable=True)
    priority = Column(String(20), nullable=False, default="medium")  # low / medium / high / critical
    status = Column(String(20), nullable=False, default="todo")  # todo / in_progress / done
    context = Column(Text, nullable=True)  # original meeting quote
    feature_area = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    meeting = relationship("Meeting", back_populates="tasks")

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from database import Base

class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=True)
    email = Column(String(320), index=True, nullable=True)
    phone = Column(String(80), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resumes = relationship("Resume", back_populates="candidate")

class UploadBatch(Base):
    __tablename__ = "upload_batches"
    id = Column(String(36), primary_key=True)
    total_files = Column(Integer, default=0, nullable=False)
    completed_files = Column(Integer, default=0, nullable=False)
    failed_files = Column(Integer, default=0, nullable=False)
    status = Column(String(30), default="processing", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resumes = relationship("Resume", back_populates="batch")

class Resume(Base):
    __tablename__ = "resumes"
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=True)
    batch_id = Column(String(36), ForeignKey("upload_batches.id"), nullable=True)
    original_filename = Column(String(500), nullable=False)
    stored_filename = Column(String(500), nullable=False)
    file_path = Column(Text, nullable=False)
    content_type = Column(String(150), nullable=True)
    extracted_text = Column(Text, nullable=True)
    parse_status = Column(String(30), default="uploaded", nullable=False)
    parse_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    candidate = relationship("Candidate", back_populates="resumes")
    batch = relationship("UploadBatch", back_populates="resumes")
    profile = relationship("ResumeProfileDB", back_populates="resume", uselist=False)

class ResumeProfileDB(Base):
    __tablename__ = "resume_profiles"
    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), unique=True, nullable=False)
    profile_json = Column(JSON, nullable=False)
    resume = relationship("Resume", back_populates="profile")

class ScreeningResult(Base):
    __tablename__ = "screening_results"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, index=True, nullable=False)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False)
    score = Column(Integer, nullable=True)
    status = Column(String(40), default="needs_review", nullable=False)
    explanation = Column(Text, nullable=True)
    evidence = Column(JSON, default=list, nullable=False)
    recruiter_reviewed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

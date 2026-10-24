from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Candidate, Resume, ResumeProfileDB

router = APIRouter(prefix="/candidates", tags=["candidates"])

@router.get("/")
def list_candidates(db: Session = Depends(get_db)):
    rows = db.query(Candidate).order_by(Candidate.created_at.desc()).all()
    return [{"id": c.id, "name": c.name, "email": c.email, "phone": c.phone} for c in rows]

@router.get("/{candidate_id}")
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    c = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    resumes = []
    for r in c.resumes:
        profile = db.query(ResumeProfileDB).filter(ResumeProfileDB.resume_id == r.id).first()
        resumes.append({"resume_id": r.id, "filename": r.original_filename, "status": r.parse_status, "profile": profile.profile_json if profile else None})
    return {"id": c.id, "name": c.name, "email": c.email, "phone": c.phone, "resumes": resumes}

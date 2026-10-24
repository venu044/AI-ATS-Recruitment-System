from fastapi import FastAPI
from database import Base, engine
import models  # register ORM tables before create_all
from routers.resumes import router as resume_router
from routers.candidates import router as candidate_router

app = FastAPI(title="AI ATS Backend", version="0.2.0")
Base.metadata.create_all(bind=engine)
app.include_router(resume_router)
app.include_router(candidate_router)

@app.get("/")
def root():
    return {"message": "AI ATS backend is running"}

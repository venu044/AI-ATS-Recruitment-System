from schemas.resumes import ResumeProfile
from services.resume_parser_service import parse_resume_with_gemini

def run_resume_parser(resume_text: str) -> ResumeProfile:
    if not resume_text or not resume_text.strip():
        raise ValueError("No readable text was extracted from this resume.")
    return parse_resume_with_gemini(resume_text)

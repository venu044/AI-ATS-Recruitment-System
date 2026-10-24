import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from schemas.resumes import ResumeProfile

load_dotenv()

def parse_resume_with_gemini(resume_text: str) -> ResumeProfile:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to backend/.env.")
    client = genai.Client(api_key=api_key)
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    response = client.models.generate_content(
        model=model,
        contents=(
            "Extract a structured profile from this resume. Only include details supported "
            "by the text. Use empty strings/lists for missing fields. Do not infer protected "
            "traits or make hiring decisions. Resume text follows:\\n\\n" + resume_text[:45000]
        ),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ResumeProfile,
            temperature=0.1,
        ),
    )
    if not response.text:
        raise RuntimeError("Gemini returned an empty response.")
    return ResumeProfile.model_validate_json(response.text)

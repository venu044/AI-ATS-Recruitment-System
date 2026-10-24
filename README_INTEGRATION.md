# AI ATS — Your implementation package + integration guide

## What is included
This implementation extends the uploaded snapshot with:
- SQLAlchemy candidate, resume, upload batch, resume-profile, and screening-result tables
- PDF/DOCX extraction and Gemini structured resume parsing
- Multi-file and ZIP upload handling
- Candidate matching by email when an email is explicitly extracted
- Batch status endpoint and candidate listing/profile endpoints
- `.env.example` configuration

**Note:** This uploaded snapshot did not include the earlier job-analysis/database modules or your friend's code. This package is a working resume-processing module and a scaffold for the combined app. Merge it with your existing job-analysis modules rather than replacing those files.

## Setup
1. Extract this package.
2. Copy `backend/.env.example` to `backend/.env`.
3. Set `DATABASE_URL` and `GEMINI_API_KEY` in `.env`.
4. In the backend folder:
   ```powershell
   python -m venv .venv
   .\\.venv\\Scripts\\activate
   python -m pip install -r requirements.txt
   python -m uvicorn main:app --reload
   ```
5. Open `http://127.0.0.1:8000/docs`.

For local first-run testing, if DATABASE_URL is omitted, the app uses SQLite `ai_ats_dev.db`. Use PostgreSQL for the combined app.

## Endpoints added
- `POST /resumes/upload` — multiple PDF/DOCX or ZIP files
- `GET /resumes/batches/{batch_id}` — batch result/progress snapshot
- `GET /candidates/` — list candidates
- `GET /candidates/{candidate_id}` — candidate profile and resumes

## Important limits / next engineering step
This implementation parses uploads during the request, so it is appropriate for validating the flow with a small test batch. For 100–500 resumes, move per-file parsing into a durable task queue (Celery/RQ + Redis) and return the batch ID immediately. The batch endpoint currently reports the persisted batch state, but this route is not yet a distributed worker.

Scanned PDFs need OCR; text extraction alone cannot read image-only pages. Add OCR as a separate pipeline stage.

## How to integrate your friend's project
Your friend’s project was described as Spring Boot + React + PostgreSQL. Integrate at the API/data-contract layer, not by mixing Java and Python source files.

### Recommended integration strategy
1. Keep **FastAPI** as the AI service: job analysis, resume parsing, eligibility, evaluation, ranking, and retrieval.
2. Keep the friend's **React frontend**. Change its API base URL to the FastAPI service for AI endpoints, or keep Spring Boot as a gateway if it already serves the UI.
3. Keep PostgreSQL as the shared database only after agreeing on a single schema. Do not let both services independently create competing versions of `candidates`, `resumes`, or `screening_results`.
4. Pick one service as owner for each table. Recommended: Spring Boot owns general recruitment CRUD if already complete; FastAPI owns AI analysis/profile/evaluation tables. Coordinate via APIs.
5. Use stable IDs. If Spring Boot creates candidate/job IDs, pass those IDs to FastAPI as external IDs or add `external_candidate_id` / `external_job_id` columns. Do not assume IDs from separate databases match.
6. Agree request/response JSON before frontend wiring.

### Suggested integration API contract
- Spring Boot job created → send job ID, title, description to FastAPI `POST /jobs` or a dedicated sync endpoint.
- Frontend uploads resume files to FastAPI `POST /resumes/upload` (or Spring Boot forwards the files).
- FastAPI returns batch ID and per-resume status.
- React polls `GET /resumes/batches/{batch_id}`.
- React requests screening with job ID, then reads ranked results.
- Recruiter decisions are stored by the app's authoritative service.

### If both services use PostgreSQL
Use one database with a clear table owner and migrations (Alembic for FastAPI; Flyway/Liquibase for Spring Boot). Avoid calling `Base.metadata.create_all()` as a production migration strategy. It is suitable for development only.

### What to merge from your friend's app
- React dashboard navigation/layout
- Job CRUD screens and API calls
- Candidate table/list UI
- Resume metadata and screening result UI patterns
- Interview stages and recruiter decision workflow

### What to keep from your project
- FastAPI AI service
- Gemini job/resume structured extraction
- Bulk/ZIP resume ingestion
- Eligibility and evaluation agents
- Evidence-grounded score explanations
- Vector retrieval/RAG (select one vector DB first)

### Human review / fairness
AI output should be decision support. Keep criteria job-related, expose evidence and uncertainty, and allow recruiter review/override. Treat missing resume details as unknown rather than automatically rejecting.

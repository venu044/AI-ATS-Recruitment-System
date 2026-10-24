
import io
import os
import uuid
import zipfile

from pathlib import Path, PurePosixPath
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Candidate, UploadBatch, Resume, ResumeProfileDB
from services.document_phaser import extract_resume_text
from agents.resume_parser_agent import run_resume_parser


router = APIRouter(
    prefix="/resumes",
    tags=["resumes"],
)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads")).resolve()

ALLOWED_EXTENSIONS = {".pdf", ".docx"}

MAX_RESUME_SIZE = 20 * 1024 * 1024       # 20 MB per resume
MAX_ZIP_SIZE = 100 * 1024 * 1024         # 100 MB per ZIP
MAX_BATCH_FILES = 500
MAX_BATCH_SIZE = 500 * 1024 * 1024       # 500 MB total extracted content


# ---------------------------------------------------------
# Helper: Safely get the original filename
# ---------------------------------------------------------

def safe_filename(filename: str) -> str:
    """
    Prevent directory traversal by keeping only the filename.
    """
    return Path(filename or "resume").name


# ---------------------------------------------------------
# Helper: Process and save one resume
# ---------------------------------------------------------

async def process_resume(
    original_filename: str,
    file_content: bytes,
    content_type: str,
    batch_id: str,
    db: Session,
    results: list,
):
    """
    Save one resume, extract its text, parse it using Gemini,
    and store the candidate profile in PostgreSQL.
    """

    original = safe_filename(original_filename)
    extension = Path(original).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        results.append({
            "filename": original,
            "status": "failed",
            "error": "Only PDF and DOCX files are supported.",
        })
        return

    if not file_content:
        results.append({
            "filename": original,
            "status": "failed",
            "error": "The uploaded file is empty.",
        })
        return

    if len(file_content) > MAX_RESUME_SIZE:
        results.append({
            "filename": original,
            "status": "failed",
            "error": "Resume exceeds the 20 MB limit.",
        })
        return

    # Generate a unique stored filename.
    stored_filename = f"{uuid.uuid4().hex}{extension}"
    file_path = UPLOAD_DIR / stored_filename

    # Save the file.
    file_path.write_bytes(file_content)

    resume = Resume(
        batch_id=batch_id,
        original_filename=original,
        stored_filename=stored_filename,
        file_path=str(file_path),
        content_type=content_type,
        parse_status="processing",
    )

    db.add(resume)
    db.flush()

    try:
        # Step 1: Extract text from the PDF or DOCX.
        extracted_text = extract_resume_text(str(file_path))

        if not extracted_text or not extracted_text.strip():
            raise ValueError(
                "No selectable text found. "
                "Scanned PDFs may require OCR."
            )

        resume.extracted_text = extracted_text

        # Step 2: Parse the resume using the Gemini agent.
        profile = run_resume_parser(extracted_text)

        # Step 3: Normalize the candidate email.
        email = (profile.email or "").strip().lower()
        email = email or None

        # Step 4: Find an existing candidate using email.
        candidate = None

        if email:
            candidate = (
                db.query(Candidate)
                .filter(Candidate.email == email)
                .first()
            )

        # Step 5: Create a candidate if one does not exist.
        if candidate is None:
            candidate = Candidate(
                name=profile.name or None,
                email=email,
                phone=profile.phone or None,
            )

            db.add(candidate)
            db.flush()

        else:
            # Update missing candidate details when available.
            if profile.name and not candidate.name:
                candidate.name = profile.name

            if profile.phone and not candidate.phone:
                candidate.phone = profile.phone

        # Step 6: Associate the resume with the candidate.
        resume.candidate_id = candidate.id

        # Step 7: Store the complete structured profile.
        profile_record = ResumeProfileDB(
            resume_id=resume.id,
            profile_json=profile.model_dump(),
        )

        db.add(profile_record)

        # Step 8: Update the resume status.
        resume.parse_status = "completed"
        resume.parse_error = None

        results.append({
            "resume_id": resume.id,
            "filename": original,
            "status": "completed",
            "candidate_id": candidate.id,
            "profile": profile.model_dump(),
        })

    except Exception as exc:
        # Keep the failed resume record for tracking.
        resume.parse_status = "failed"
        resume.parse_error = str(exc)[:1500]

        results.append({
            "resume_id": resume.id,
            "filename": original,
            "status": "failed",
            "error": str(exc)[:500],
        })


# ---------------------------------------------------------
# POST: Upload multiple resumes or a ZIP file
# ---------------------------------------------------------

@router.post("/upload")
async def upload_resumes(
    files: List[UploadFile] = File(
        ...,
        description="Upload multiple PDF/DOCX resumes or a ZIP file",
    ),
    db: Session = Depends(get_db),
):
    """
    Accepts:
    - Multiple PDF/DOCX files
    - One or more ZIP files containing PDF/DOCX resumes

    Each resume is extracted, parsed, and saved to PostgreSQL.
    """

    if not files:
        raise HTTPException(
            status_code=400,
            detail="Select at least one file.",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    batch_id = str(uuid.uuid4())

    batch = UploadBatch(
        id=batch_id,
        total_files=0,
        completed_files=0,
        failed_files=0,
        status="processing",
    )

    db.add(batch)
    db.flush()

    results = []

    # Store extracted files temporarily in memory.
    expanded_files = []

    total_extracted_size = 0

    try:
        # -------------------------------------------------
        # Step 1: Read the uploaded files.
        # -------------------------------------------------

        for upload in files:

            filename = safe_filename(upload.filename)
            extension = Path(filename).suffix.lower()

            # ---------------------------------------------
            # ZIP upload
            # ---------------------------------------------

            if extension == ".zip":

                zip_content = await upload.read()

                if len(zip_content) > MAX_ZIP_SIZE:
                    results.append({
                        "filename": filename,
                        "status": "failed",
                        "error": "ZIP file exceeds the 100 MB limit.",
                    })
                    continue

                try:
                    with zipfile.ZipFile(
                        io.BytesIO(zip_content)
                    ) as archive:

                        for info in archive.infolist():

                            if info.is_dir():
                                continue

                            # Normalize ZIP paths, including Windows paths.
                            normalized_name = info.filename.replace(
                                "\\", "/"
                            )

                            member = PurePosixPath(normalized_name)

                            # Prevent path traversal.
                            if (
                                member.is_absolute()
                                or ".." in member.parts
                            ):
                                continue

                            member_extension = member.suffix.lower()

                            if member_extension not in ALLOWED_EXTENSIONS:
                                continue

                            if len(expanded_files) >= MAX_BATCH_FILES:
                                results.append({
                                    "filename": filename,
                                    "status": "failed",
                                    "error": (
                                        f"Maximum batch size is "
                                        f"{MAX_BATCH_FILES} resumes."
                                    ),
                                })
                                break

                            # Check declared size before reading.
                            if info.file_size > MAX_RESUME_SIZE:
                                results.append({
                                    "filename": member.name,
                                    "status": "failed",
                                    "error": "Resume exceeds the 20 MB limit.",
                                })
                                continue

                            content = archive.read(info)

                            if len(content) > MAX_RESUME_SIZE:
                                results.append({
                                    "filename": member.name,
                                    "status": "failed",
                                    "error": "Resume exceeds the 20 MB limit.",
                                })
                                continue

                            total_extracted_size += len(content)

                            if total_extracted_size > MAX_BATCH_SIZE:
                                raise ValueError(
                                    "Total extracted batch size "
                                    "exceeds 500 MB."
                                )

                            expanded_files.append({
                                "filename": member.name,
                                "content": content,
                                "content_type": "application/zip",
                            })

                except zipfile.BadZipFile:
                    results.append({
                        "filename": filename,
                        "status": "failed",
                        "error": "Invalid ZIP file.",
                    })

            # ---------------------------------------------
            # Individual PDF or DOCX upload
            # ---------------------------------------------

            elif extension in ALLOWED_EXTENSIONS:

                content = await upload.read()

                if len(content) > MAX_RESUME_SIZE:
                    results.append({
                        "filename": filename,
                        "status": "failed",
                        "error": "Resume exceeds the 20 MB limit.",
                    })
                    continue

                total_extracted_size += len(content)

                if total_extracted_size > MAX_BATCH_SIZE:
                    raise ValueError(
                        "Total batch size exceeds 500 MB."
                    )

                expanded_files.append({
                    "filename": filename,
                    "content": content,
                    "content_type": upload.content_type
                    or "application/octet-stream",
                })

            # ---------------------------------------------
            # Unsupported upload
            # ---------------------------------------------

            else:
                results.append({
                    "filename": filename,
                    "status": "failed",
                    "error": "Unsupported file type. Use PDF, DOCX, or ZIP.",
                })

        # -------------------------------------------------
        # Step 2: Process each extracted resume.
        # -------------------------------------------------

        for item in expanded_files:

            await process_resume(
                original_filename=item["filename"],
                file_content=item["content"],
                content_type=item["content_type"],
                batch_id=batch_id,
                db=db,
                results=results,
            )

        # -------------------------------------------------
        # Step 3: Calculate batch statistics.
        # -------------------------------------------------

        completed = sum(
            result.get("status") == "completed"
            for result in results
        )

        failed = sum(
            result.get("status") == "failed"
            for result in results
        )

        total = len(results)

        batch.total_files = total
        batch.completed_files = completed
        batch.failed_files = failed

        if failed == 0:
            batch.status = "completed"

        elif completed > 0:
            batch.status = "partial"

        else:
            batch.status = "failed"

        # -------------------------------------------------
        # Step 4: Commit database changes.
        # -------------------------------------------------

        db.commit()

        return {
            "batch_id": batch_id,
            "total": total,
            "completed": completed,
            "failed": failed,
            "status": batch.status,
            "results": results,
        }

    except Exception as exc:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Bulk upload failed: {str(exc)[:500]}",
        )

    finally:

        # Close uploaded files.
        for upload in files:
            await upload.close()


# ---------------------------------------------------------
# GET: Retrieve upload batch information
# ---------------------------------------------------------

@router.get("/batches/{batch_id}")
def get_batch(
    batch_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve the status and resume details of an upload batch.
    """

    batch = (
        db.query(UploadBatch)
        .filter(UploadBatch.id == batch_id)
        .first()
    )

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Batch not found.",
        )

    return {
        "batch_id": batch.id,
        "status": batch.status,
        "total_files": batch.total_files,
        "completed_files": batch.completed_files,
        "failed_files": batch.failed_files,
        "resumes": [
            {
                "resume_id": resume.id,
                "filename": resume.original_filename,
                "status": resume.parse_status,
                "error": resume.parse_error,
                "candidate_id": resume.candidate_id,
            }
            for resume in batch.resumes
        ],
    }



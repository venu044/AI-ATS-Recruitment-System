import fitz
from docx import Document

def extract_text_from_pdf(file_path: str) -> str:
    with fitz.open(file_path) as document:
        return "\\n".join(page.get_text() for page in document)

def extract_text_from_docx(file_path: str) -> str:
    document = Document(file_path)
    return "\\n".join(paragraph.text for paragraph in document.paragraphs)

def extract_resume_text(file_path: str) -> str:
    lower = file_path.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    if lower.endswith(".docx"):
        return extract_text_from_docx(file_path)
    raise ValueError("Only PDF and DOCX files are supported.")

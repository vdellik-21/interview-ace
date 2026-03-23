"""
InterviewAce — File Parser Service
Parses uploaded files (PDF, DOCX, TXT) into plain text.

Owner: Dev 1 (Vineeth)
Status: STUB — implement the parse functions
"""

import os
from pathlib import Path


async def parse_file(file_path: str) -> str:
    """
    Parse a file into plain text.

    Supports: .pdf, .docx, .doc, .txt, .md
    
    Args:
        file_path: Absolute path to the uploaded file
    
    Returns:
        Extracted plain text content
    
    Raises:
        ValueError: If file format is not supported
    """
    ext = Path(file_path).suffix.lower()

    if ext == ".pdf":
        return await _parse_pdf(file_path)
    elif ext in (".docx", ".doc"):
        return await _parse_docx(file_path)
    elif ext in (".txt", ".md"):
        return await _parse_text(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Supported: .pdf, .docx, .txt, .md")


async def _parse_pdf(file_path: str) -> str:
    """
    Extract text from a PDF file using pdfplumber.
    
    TODO: Implement
    - Use pdfplumber to open the PDF
    - Extract text from all pages
    - Join with newlines
    - Strip excessive whitespace
    """
    # STUB — replace with real implementation
    import pdfplumber

    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    
    return "\n\n".join(text_parts).strip()


async def _parse_docx(file_path: str) -> str:
    """
    Extract text from a DOCX file using python-docx.
    
    TODO: Implement
    - Use python-docx to open the document
    - Extract text from all paragraphs
    - Join with newlines
    """
    # STUB — replace with real implementation
    from docx import Document

    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs).strip()


async def _parse_text(file_path: str) -> str:
    """Read a plain text file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()

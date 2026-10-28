"""Document parsing and text extraction service.
Preserves page numbers, source location metadata, and table structures for financial documents.
"""

import io
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import pypdf
import docx


class ExtractedPage(BaseModel):
    page_number: int  # 1-indexed
    text: str
    char_count: int
    table_count: int = 0


class ExtractedDocument(BaseModel):
    filename: str
    file_type: str
    total_pages: int
    pages: List[ExtractedPage]
    total_characters: int


def normalize_financial_text(text: str) -> str:
    """Normalize whitespace and control characters without destroying financial tables,
    numbers, decimal points, negative indicators (parentheses), and currency symbols.
    """
    if not text:
        return ""

    # Replace non-breaking spaces and exotic spaces with standard space
    text = re.sub(r"[\u00A0\u1680\u2000-\u200B\u202F\u205F\u3000]", " ", text)
    # Replace carriage returns
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Replace consecutive blank lines with maximum two
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip trailing whitespace on each line while preserving indentation/columns
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def parse_pdf(file_bytes: bytes, filename: str) -> ExtractedDocument:
    """Extract text from PDF while recording page-level boundaries."""
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    total_pages = len(reader.pages)
    pages: List[ExtractedPage] = []
    total_chars = 0

    for i, page in enumerate(reader.pages):
        page_num = i + 1
        raw_text = page.extract_text() or ""
        clean_text = normalize_financial_text(raw_text)
        
        # Detect if text appears to contain table rows (lines with aligned numeric values)
        has_table_patterns = bool(re.search(r"(\$|€|£)?\s*-?\(?\d+[\d,]*\.?\d*\)?\s+(\$|€|£)?\s*-?\(?\d+[\d,]*\.?\d*\)?", clean_text))
        table_count = 1 if has_table_patterns else 0

        extracted_page = ExtractedPage(
            page_number=page_num,
            text=clean_text,
            char_count=len(clean_text),
            table_count=table_count,
        )
        pages.append(extracted_page)
        total_chars += len(clean_text)

    return ExtractedDocument(
        filename=filename,
        file_type="pdf",
        total_pages=total_pages,
        pages=pages,
        total_characters=total_chars,
    )


def parse_docx(file_bytes: bytes, filename: str) -> ExtractedDocument:
    """Extract text and tables from DOCX document."""
    doc = docx.Document(io.BytesIO(file_bytes))
    full_text_blocks: List[str] = []
    table_count = 0

    # Extract paragraphs
    for para in doc.paragraphs:
        if para.text.strip():
            full_text_blocks.append(para.text.strip())

    # Extract tables, formatting rows and columns clearly with tab delimiters
    for table in doc.tables:
        table_count += 1
        table_lines: List[str] = []
        for row in table.rows:
            row_cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            if any(row_cells):
                table_lines.append(" | ".join(row_cells))
        if table_lines:
            full_text_blocks.append("\n[TABLE START]\n" + "\n".join(table_lines) + "\n[TABLE END]")

    combined_text = "\n\n".join(full_text_blocks)
    clean_text = normalize_financial_text(combined_text)

    # DOCX does not have native fixed pagination; treat each ~3000 chars as a virtual page
    # while preserving section breaks
    char_threshold = 3000
    pages: List[ExtractedPage] = []
    if len(clean_text) <= char_threshold:
        pages.append(ExtractedPage(page_number=1, text=clean_text, char_count=len(clean_text), table_count=table_count))
    else:
        # Split into logical sections/pages
        chunks = [clean_text[i:i + char_threshold] for i in range(0, len(clean_text), char_threshold)]
        for i, chunk in enumerate(chunks):
            pages.append(ExtractedPage(page_number=i + 1, text=chunk, char_count=len(chunk), table_count=table_count if i == 0 else 0))

    return ExtractedDocument(
        filename=filename,
        file_type="docx",
        total_pages=len(pages),
        pages=pages,
        total_characters=len(clean_text),
    )


def parse_txt(file_bytes: bytes, filename: str) -> ExtractedDocument:
    """Extract text from TXT file with robust encoding detection."""
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            raw_text = file_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raw_text = file_bytes.decode("utf-8", errors="replace")

    clean_text = normalize_financial_text(raw_text)

    # Virtual pagination for large text files (approx 3000 chars per page)
    char_threshold = 3000
    pages: List[ExtractedPage] = []
    if len(clean_text) <= char_threshold:
        pages.append(ExtractedPage(page_number=1, text=clean_text, char_count=len(clean_text)))
    else:
        chunks = [clean_text[i:i + char_threshold] for i in range(0, len(clean_text), char_threshold)]
        for i, chunk in enumerate(chunks):
            pages.append(ExtractedPage(page_number=i + 1, text=chunk, char_count=len(chunk)))

    return ExtractedDocument(
        filename=filename,
        file_type="txt",
        total_pages=len(pages),
        pages=pages,
        total_characters=len(clean_text),
    )


def extract_document_text(file_bytes: bytes, filename: str, file_type: str) -> ExtractedDocument:
    """Dispatch to appropriate parser based on file type."""
    ext = file_type.lower().lstrip(".")
    if ext == "pdf":
        return parse_pdf(file_bytes, filename)
    elif ext == "docx":
        return parse_docx(file_bytes, filename)
    elif ext in ("txt", "text", "csv", "md"):
        return parse_txt(file_bytes, filename)
    else:
        raise ValueError(f"Unsupported file format '{file_type}'. Supported formats: PDF, TXT, DOCX.")

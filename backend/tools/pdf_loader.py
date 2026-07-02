"""PDF text extraction tool using PyMuPDF."""
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger


try:
    import fitz
except ImportError:
    fitz = None


class PDFLoadError(Exception):
    """Exception raised for PDF loading errors."""


def load_pdf(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Load a PDF file and extract text with page metadata.

    Args:
        file_path: Path to the PDF file.

    Returns:
        Tuple of (full_text, pages) where pages is a list of dicts
        with 'page_number' and 'text' keys.

    Raises:
        PDFLoadError: If the PDF cannot be loaded.
        FileNotFoundError: If the file does not exist.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    if fitz is None:
        raise PDFLoadError("PyMuPDF (fitz) is not installed")

    logger.info(f"Loading PDF: {path.name}")

    try:
        doc = fitz.open(str(path))
        full_text = ""
        pages: List[Dict[str, Any]] = []

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text()
            full_text += text + "\n\n"
            pages.append({
                "page_number": page_num + 1,
                "text": text,
                "char_count": len(text),
            })

        doc.close()

        logger.info(
            f"Extracted {len(pages)} pages, "
            f"{len(full_text)} characters from {path.name}"
        )

        return full_text, pages

    except Exception as e:
        raise PDFLoadError(f"Failed to load PDF {file_path}: {e}") from e


def get_pdf_metadata(file_path: str) -> Dict[str, Any]:
    """Get metadata from a PDF file."""
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    if fitz is None:
        raise PDFLoadError("PyMuPDF (fitz) is not installed")

    try:
        doc = fitz.open(str(path))
        metadata = {
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "subject": doc.metadata.get("subject", ""),
            "page_count": len(doc),
            "file_size": os.path.getsize(file_path),
            "filename": path.name,
        }
        doc.close()
        return metadata

    except Exception as e:
        raise PDFLoadError(f"Failed to read PDF metadata {file_path}: {e}") from e


def extract_page_text(file_path: str, page_numbers: List[int]) -> List[Dict[str, Any]]:
    """Extract text from specific pages of a PDF.

    Args:
        file_path: Path to the PDF file.
        page_numbers: List of 1-indexed page numbers to extract.

    Returns:
        List of dicts with 'page_number' and 'text' keys.
    """
    if fitz is None:
        raise PDFLoadError("PyMuPDF (fitz) is not installed")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    try:
        doc = fitz.open(str(path))
        extracted: List[Dict[str, Any]] = []

        for page_num in page_numbers:
            if 1 <= page_num <= len(doc):
                page = doc.load_page(page_num - 1)
                text = page.get_text()
                extracted.append({
                    "page_number": page_num,
                    "text": text,
                })

        doc.close()
        return extracted

    except Exception as e:
        raise PDFLoadError(
            f"Failed to extract pages {page_numbers} from {file_path}: {e}"
        ) from e

"""
Document loading and text extraction.
Handles multiple formats: PDF, DOCX, HTML, plain text, etc.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import logging

from .config import LoaderConfig
from .types import DocumentRef, LoadException

log = logging.getLogger(__name__)


@dataclass
class LoadedDocument:
    """
    Normalized document content after loading.
    """
    raw_bytes: bytes
    extracted_text: Optional[str] = None
    pages_count: Optional[int] = None
    
    @property
    def text_length(self) -> int:
        """Length of extracted text or 0."""
        return len(self.extracted_text) if self.extracted_text else 0


class DocumentLoader:
    """
    Load and extract text from various document formats.
    """
    
    def __init__(self, config: LoaderConfig):
        self.config = config
    
    def load(self, file_ref: DocumentRef) -> LoadedDocument:
        """
        Load document and extract text.
        
        Args:
            file_ref: Reference to document file
        
        Returns:
            LoadedDocument with raw bytes and extracted text
        
        Raises:
            LoadException: If loading fails
        """
        if not file_ref.real_path.exists():
            raise LoadException(f"File not found: {file_ref.real_path}")
        
        try:
            raw_bytes = file_ref.real_path.read_bytes()
        except Exception as e:
            raise LoadException(f"Failed to read file {file_ref.real_path}: {e}")
        
        # Extract text based on format
        extracted_text = None
        pages_count = None
        
        try:
            if file_ref.format == "pdf":
                extracted_text, pages_count = self._load_pdf(raw_bytes, file_ref.real_path)
            
            elif file_ref.format == "html" or file_ref.format == "htm":
                extracted_text = self._load_html(raw_bytes)
            
            elif file_ref.format == "txt":
                extracted_text = self._load_text(raw_bytes)
            
            elif file_ref.format == "docx":
                extracted_text = self._load_docx(raw_bytes)
            
            elif file_ref.format == "doc":
                # DOC files typically need conversion first
                # For now, return bytes without extraction
                log.warning(f"DOC format not directly supported: {file_ref.real_path}")
            
            elif file_ref.format == "md":
                extracted_text = self._load_markdown(raw_bytes)
            
            elif file_ref.format == "xml":
                extracted_text = self._load_xml(raw_bytes)
            
            elif file_ref.format == "json":
                extracted_text = self._load_json(raw_bytes)
            
            # Enforce max text length
            if extracted_text and self.config.max_text_length > 0:
                if len(extracted_text) > self.config.max_text_length:
                    log.warning(
                        f"Truncating text for {file_ref.logical_path} "
                        f"({len(extracted_text)} → {self.config.max_text_length} chars)"
                    )
                    extracted_text = extracted_text[:self.config.max_text_length]
        
        except Exception as e:
            log.warning(f"Failed to extract text from {file_ref.logical_path}: {e}")
            # Don't fail the whole ingestion, just skip text extraction
        
        return LoadedDocument(
            raw_bytes=raw_bytes,
            extracted_text=extracted_text,
            pages_count=pages_count,
        )
    
    def _load_pdf(self, data: bytes, path: Path) -> tuple[Optional[str], Optional[int]]:
        """
        Extract text from PDF.
        
        Handles malformed PDFs gracefully with fallback strategies.
        
        Returns: (text, pages_count)
        """
        try:
            from pypdf import PdfReader
        except ImportError:
            log.warning("pypdf not installed, skipping PDF text extraction")
            return None, None
        
        try:
            from io import BytesIO
            pdf = PdfReader(BytesIO(data))
            pages_count = len(pdf.pages)
            
            if not self.config.pdf_extract_text:
                return None, pages_count
            
            max_pages = self.config.pdf_max_pages or len(pdf.pages)
            max_pages = min(max_pages, len(pdf.pages))
            
            texts = []
            extraction_errors = 0
            
            for i, page in enumerate(pdf.pages[:max_pages]):
                try:
                    text = page.extract_text()
                    if text:
                        texts.append(text)
                except Exception as e:
                    # Log PDF-specific errors at debug level - they're common with malformed PDFs
                    if "startxref" in str(e).lower():
                        log.debug(f"Malformed PDF content at page {i} from {path}: {e}")
                    else:
                        log.debug(f"Failed to extract page {i} from {path}: {e}")
                    extraction_errors += 1
            
            result_text = "\n".join(texts) if texts else None
            
            # Log summary if we had significant extraction errors
            if extraction_errors > max_pages // 2:
                log.debug(f"PDF extraction: {max_pages - extraction_errors}/{max_pages} pages successful from {path}")
            
            return result_text, pages_count
        
        except Exception as e:
            log.debug(f"Failed to read PDF {path}: {e}")
            return None, None
    
    def _load_html(self, data: bytes) -> Optional[str]:
        """
        Extract text from HTML with STRICT correctness enforcement.
        
        INGESTION PHASE CONTRACT:
        - HTML text extraction happens in INGESTION phase (not parsing)
        - Ingestion responsibility ENDS at valid text extraction
        - Parsing responsibility BEGINS after successful ingestion
        
        FAILING FAST IS MANDATORY:
        - If text cannot be extracted with required quality, ingestion MUST FAIL
        - No partial success allowed - empty/invalid text = ingestion failure
        - Prevents downstream processing of corrupted/invalid documents
        - Ensures pipeline correctness over completeness
        
        Args:
            data: Raw HTML bytes
            
        Returns:
            Extracted plain text
            
        Raises:
            LoadException: If text extraction fails validation criteria
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise LoadException("beautifulsoup4 not installed - required for HTML text extraction")
        
        try:
            # Decode bytes to string
            text = data.decode("utf-8", errors="replace")
            log.debug(f"HTML decode successful, length: {len(text)}")
            
            if not self.config.html_extract_text:
                log.debug("HTML text extraction disabled in config")
                # When keeping HTML, validate it's not empty
                if not text.strip():
                    raise LoadException("HTML file is empty or contains no readable content")
                return text
            
            # Parse and extract text
            soup = BeautifulSoup(text, "html.parser")
            log.debug(f"HTML parsed successfully, title: {soup.title.string if soup.title else 'No title'}")
            
            # Remove script and style elements
            scripts_removed = len(soup.find_all(["script", "style"]))
            for script in soup(["script", "style"]):
                script.decompose()
            log.debug(f"Removed {scripts_removed} script/style elements")
            
            # Get text
            extracted = soup.get_text()
            log.debug(f"Raw extracted text length: {len(extracted)}")
            
            # Clean up whitespace
            lines = [line.strip() for line in extracted.split("\n") if line.strip()]
            extracted = "\n".join(lines)
            
            log.debug(f"Cleaned extracted text length: {len(extracted)}")
            
            # STRICT VALIDATION: Enforce ingestion correctness contract
            # HTML ingestion MUST produce valid text or FAIL explicitly
            if not extracted:
                raise LoadException("HTML text extraction produced empty result - no readable content found")
            
            # Validate extracted text meets minimum quality requirements
            extracted_trimmed = extracted.strip()
            if not extracted_trimmed:
                raise LoadException("HTML text extraction produced only whitespace - no readable content")
            
            # Check for visible characters (not just HTML entities or control chars)
            visible_chars = [c for c in extracted_trimmed if c.isprintable() and not c.isspace()]
            if not visible_chars:
                raise LoadException("HTML text extraction produced no visible printable characters")
            
            # MINIMUM CONTENT REQUIREMENT: HTML documents must have substantial readable content
            # Not just titles or minimal text - require at least 10 visible characters
            # This prevents ingestion of HTML files with only titles/metadata but no actual content
            if len(visible_chars) < 10:
                raise LoadException(
                    f"HTML text extraction produced insufficient content - only {len(visible_chars)} visible characters "
                    f"(minimum 10 required). Document appears to contain only titles/metadata with no substantial content."
                )
            
            # Final length validation after trimming
            if len(extracted_trimmed) == 0:
                raise LoadException("HTML text extraction validation failed - zero length after trimming")
            
            log.debug(f"HTML text extraction validation passed - {len(extracted_trimmed)} characters, {len(visible_chars)} visible")
            return extracted_trimmed
        
        except LoadException:
            # Re-raise LoadException as-is (already properly formatted)
            raise
        except Exception as e:
            # Convert any other exception to LoadException with technical details
            raise LoadException(f"HTML text extraction failed: {type(e).__name__}: {e}")
    
    def _load_text(self, data: bytes) -> Optional[str]:
        """Load plain text file."""
        try:
            # Try encodings in order
            for encoding in self.config.encoding_fallback:
                try:
                    text = data.decode(encoding)
                    return text if text.strip() else None
                except (UnicodeDecodeError, LookupError):
                    continue
            
            # If all fail, use replacement chars
            return data.decode("utf-8", errors="replace")
        
        except Exception as e:
            log.warning(f"Failed to decode text file: {e}")
            return None
    
    def _load_docx(self, data: bytes) -> Optional[str]:
        """Extract text from DOCX."""
        try:
            from docx import Document
            from io import BytesIO
        except ImportError:
            log.warning("python-docx not installed, skipping DOCX text extraction")
            return None
        
        try:
            doc = Document(BytesIO(data))
            texts = []
            
            for para in doc.paragraphs:
                if para.text.strip():
                    texts.append(para.text)
            
            return "\n".join(texts) if texts else None
        
        except Exception as e:
            log.warning(f"Failed to extract text from DOCX: {e}")
            return None
    
    def _load_markdown(self, data: bytes) -> Optional[str]:
        """
        Extract text from Markdown.
        Markdown is essentially plain text with formatting, so we just decode it.
        """
        try:
            # Try encodings in order
            for encoding in self.config.encoding_fallback:
                try:
                    text = data.decode(encoding)
                    return text if text.strip() else None
                except (UnicodeDecodeError, LookupError):
                    continue
            
            # If all fail, use replacement chars
            return data.decode("utf-8", errors="replace")
        
        except Exception as e:
            log.warning(f"Failed to decode markdown file: {e}")
            return None
    
    def _load_xml(self, data: bytes) -> Optional[str]:
        """
        Extract text from XML.
        For XML, we extract all text content while preserving structure information.
        Uses lxml parser with fallback to html.parser if needed.
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            log.warning("beautifulsoup4 not installed, skipping XML text extraction")
            return None
        
        try:
            # Decode bytes to string
            text = data.decode("utf-8", errors="replace")
            
            # Try lxml parser first (most robust for XML)
            try:
                soup = BeautifulSoup(text, "xml")
            except Exception as e:
                # Fallback to html.parser if lxml fails
                log.debug(f"lxml XML parsing failed, falling back to html.parser: {e}")
                soup = BeautifulSoup(text, "html.parser")
            
            # Extract all text content
            extracted = soup.get_text()
            
            # Clean up whitespace
            lines = [line.strip() for line in extracted.split("\n") if line.strip()]
            extracted = "\n".join(lines)
            
            return extracted if extracted.strip() else None
        
        except Exception as e:
            log.warning(f"Failed to extract text from XML: {e}")
            return None
    
    def _load_json(self, data: bytes) -> Optional[str]:
        """
        Extract text from JSON.
        For JSON, we pretty-print it to make it readable as text.
        """
        try:
            import json
            
            # Decode bytes to string
            text = data.decode("utf-8", errors="replace")
            
            # Parse and re-format JSON for readability
            try:
                parsed = json.loads(text)
                # Pretty print with indentation
                formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
                return formatted
            except json.JSONDecodeError:
                # If not valid JSON, return as plain text
                return text
        
        except Exception as e:
            log.warning(f"Failed to extract text from JSON: {e}")
            return None

"""
Core data types for the ingestion module.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Dict, Any, List
from datetime import datetime, UTC

if TYPE_CHECKING:
    from .scanner import ScanContext


@dataclass(frozen=True)
class DocumentRef:
    """
    A reference to a discovered document in the filesystem.
    
    - logical_path: virtual path (handles nested zips)
    - real_path: actual filesystem path (may be in temp dir if from zip)
    - format: file extension (lowercase: pdf, docx, html, etc.)
    - basename: filename without extension
    """
    logical_path: str
    real_path: Path
    format: str
    basename: str


@dataclass
class IDGenerationConfig:
    """Configuration for document ID generation strategies."""

    # Legacy SHA controls kept for backward compatibility
    strategy: str = "sha256-16"
    prefix: str = ""
    suffix: str = ""

    # New hash sizing controls
    hash_length_bytes: Optional[int] = None
    hash_digits: Optional[int] = None

    # New switching controls
    naming_strategy: str = "hash_only"
    incremental_prefix: str = "DOC"
    incremental_pad_digits: int = 6
    enabled_hash: bool = True
    enabled_incremental: bool = False


@dataclass(frozen=True)
class ScanResult:
    """
    Named result returned by scanner iteration.

    - context: scan context used for temp directory lifecycle
    - document: discovered document reference
    """ 
    context: ScanContext # track the temporary directories created during scanning
    document: DocumentRef


@dataclass
class DocumentMetadata: # DocumentRecord in DataCuration
    """
    Extracted and generated metadata for a document.
    """
    doc_id: str
    logical_path: str
    basename: str
    format: str
    
    # Content metrics
    extracted_text_length: int = 0
    pages_count: Optional[int] = None
    
    # Integrity
    source_file_hash: Optional[str] = None  # SHA256
    source_file_size: int = 0
    
    # Timing
    ingested_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    # Optional sidecar metadata
    sidecar_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestedDocument:
    """
    Complete representation of an ingested document after the pipeline ingestion.
    """
    metadata: DocumentMetadata
    raw_bytes: bytes
    extracted_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "doc_id": self.metadata.doc_id,
            "logical_path": self.metadata.logical_path,
            "basename": self.metadata.basename,
            "format": self.metadata.format,
            "extracted_text_length": self.metadata.extracted_text_length,
            "pages_count": self.metadata.pages_count,
            "source_file_hash": self.metadata.source_file_hash,
            "source_file_size": self.metadata.source_file_size,
            "ingested_at": self.metadata.ingested_at.isoformat(),
            "sidecar_metadata": self.metadata.sidecar_metadata,
        }


@dataclass
class AnalyzerResult:
    """
    Structured result of a single analyzer execution.
    """
    analyzer_name: str
    status: str
    payload: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize analyzer result to a dictionary."""
        return {
            "analyzer_name": self.analyzer_name,
            "status": self.status,
            "payload": self.payload,
            "warnings": self.warnings,
            "errors": self.errors,
            "metrics": self.metrics,
        }


@dataclass
class IngestManifest:
    """
    Summary of an ingestion run.
    """
    # Mapping of logical_path → doc_id for successful ingestions
    ingested: Dict[str, str] = field(default_factory=dict)
    
    # Mapping of logical_path → error message for failures
    errors: Dict[str, str] = field(default_factory=dict)
    
    # Timing information
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: Optional[datetime] = None
    
    # Per-document warnings: logical_path → list of reason strings
    warnings: Dict[str, List[str]] = field(default_factory=dict)
    
    # Deduplication tracking
    duplicates_found: int = 0
    
    @property
    def total_warnings(self) -> int:
        """Total number of warning entries across all documents."""
        return sum(len(v) for v in self.warnings.values())
    
    @property
    def total_input(self) -> int:
        """Total documents found."""
        return len(self.ingested) + len(self.errors)
    
    @property
    def success_rate(self) -> float:
        """Percentage of successfully ingested documents."""
        total = self.total_input
        return (len(self.ingested) / total * 100) if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "ingested": self.ingested,
            "errors": self.errors,
            "warnings": self.warnings,
            "summary": {
                "total_input": self.total_input,
                "successfully_ingested": len(self.ingested),
                "failed": len(self.errors),
                "total_warnings": self.total_warnings,
                "duplicates_found": self.duplicates_found,
                "success_rate": self.success_rate,
            },
            "timestamps": {
                "started_at": self.started_at.isoformat(),
                "completed_at": self.completed_at.isoformat() if self.completed_at else None,
                "duration_seconds": (
                    (self.completed_at - self.started_at).total_seconds()
                    if self.completed_at
                    else None
                ),
            },
        }


class IngestException(Exception):
    """Base exception for ingestion errors."""
    pass


class AnalyzerException(IngestException):
    """Base exception for analyzer-related failures."""
    pass


class AnalyzerConfigurationException(AnalyzerException):
    """Raised when analyzer configuration is invalid."""
    pass


class AnalyzerInputException(AnalyzerException):
    """Raised when an analyzer receives an invalid document/input."""
    pass


class AnalyzerExecutionException(AnalyzerException):
    """Raised when analyzer execution fails after configuration is accepted."""
    pass


class ScanException(IngestException):
    """Exception during document discovery."""
    pass


class LoadException(IngestException):
    """Exception during document loading/normalization."""
    pass


class PersistenceException(IngestException):
    """Exception during document storage."""
    pass


class InvalidIDGenerationConfig(IngestException):
    """Raised when ID generation configuration parameters are invalid."""
    pass


class IDGenerationException(IngestException):
    """Raised when runtime ID generation fails."""
    pass

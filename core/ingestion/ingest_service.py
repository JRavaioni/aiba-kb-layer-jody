"""
Main ingestion orchestrator.
Coordinates scanning, loading, analysis, and persistence.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional, TYPE_CHECKING
import logging
import hashlib
from datetime import datetime, UTC
from contextvars import ContextVar

from .config import IngestConfig
from .scanner import DocumentScanner
from .loader import DocumentLoader
from .sidecar import MetadataLoader
from .id_generator import IDGeneratorFactory
from .analyzers import AnalyzerPipeline
from .backends import PersistenceBackendFactory
from .types import (
    IngestedDocument,
    AnalyzerConfigurationException,
    AnalyzerExecutionException,
    AnalyzerInputException,
    DocumentMetadata,
    IngestManifest,
    IngestException,
    LoadException,
    IDGenerationException,
)

if TYPE_CHECKING:
    from .id_generator import IDGenerator
    from .backends import PersistenceBackend

log = logging.getLogger(__name__)
PIPELINE_WARNING_KEY = "__pipeline__"
_CURRENT_DOC_LOGICAL_PATH: ContextVar[Optional[str]] = ContextVar(
    "ingest_current_doc_logical_path",
    default=None,
)


class _ManifestWarningHandler(logging.Handler):
    """Collect WARNING logs and persist detailed reasons into ingest manifest."""

    def __init__(self, manifest: IngestManifest):
        super().__init__(level=logging.WARNING)
        self._manifest = manifest

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno < logging.WARNING:
            return

        reason = record.getMessage().strip()
        if not reason:
            return

        logical_path = _CURRENT_DOC_LOGICAL_PATH.get() or PIPELINE_WARNING_KEY
        warning_list = self._manifest.warnings.setdefault(logical_path, [])
        if reason not in warning_list:
            warning_list.append(reason)


class IngestService:
    """
    Main ingestion service
    """
    
    def __init__(self, config: IngestConfig, output_dir: Path):
        """
        Initialize ingestion service.
        
        Args:
            config: Ingestion configuration
            output_dir: Output directory for persisted documents
        """
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Validate config
        errors = config.validate()
        if errors:
            raise IngestException(f"Invalid configuration: {errors}")
        
        # Initialize components
        self.scanner = DocumentScanner(config.input, config.zip_extraction)
        self.loader = DocumentLoader(config.loader)
        
        # Configure sidecar metadata base paths
        # Include output directory for internal ingestion output
        # Additional base paths can be configured for external document sources
        sidecar_base_paths = [output_dir]  # Start with internal output directory
        if config.metadata.base_paths:
            # Add any additional configured base paths
            for path_str in config.metadata.base_paths:
                if path_str != ".":  # Skip default placeholder
                    sidecar_base_paths.append(Path(path_str))
        
        self.metadata_loader = MetadataLoader(config.metadata, sidecar_base_paths)
        self.id_generator = IDGeneratorFactory.create(config.id_generation)
        self.analyzer_pipeline = AnalyzerPipeline(config.analyzers)
        self.persistence = None
        if config.output.backend != "custom":
            self.persistence = PersistenceBackendFactory.create(config.output, output_dir)
        
        log.info(f"Initialized IngestService with output_dir={output_dir}, sidecar_base_paths={[str(p) for p in sidecar_base_paths]}")

    def set_id_generator(self, generator: IDGenerator) -> None:
        """Inject custom ID generator after service construction."""
        self.id_generator = generator

    def set_persistence_backend(self, backend: PersistenceBackend) -> None:
        """Inject custom persistence backend after service construction."""
        self.persistence = backend
    
    def ingest(
        self,
        input_dir: Path,
        temp_root_dir: Optional[Path] = None,
    ) -> IngestManifest:
        """
        Execute ingestion pipeline.
        
        Scans input_dir, loads documents, extracts metadata/text,
        applies analyzers, and persists to output_dir.
        
        Args:
            input_dir: Directory containing documents to ingest
            temp_root_dir: Root for temporary directories (default: system temp)
        
        Returns:
            IngestManifest with results
        """
        input_dir = Path(input_dir)
        if self.id_generator is None:
            raise IngestException("ID generator not configured")
        if self.persistence is None:
            raise IngestException("Persistence backend not configured")

        manifest = IngestManifest()
        scan_context = None
        
        log.info(f"Starting ingestion from {input_dir}")

        resolved_temp_root_dir = self._resolve_temp_root_dir(temp_root_dir)
        if resolved_temp_root_dir is not None:
            log.info(f"ZIP extraction temp root: {resolved_temp_root_dir}")
        else:
            log.info("ZIP extraction temp root: system temporary directory")
        
        warning_handler = _ManifestWarningHandler(manifest)
        warning_handler.setFormatter(logging.Formatter("%(message)s"))
        ingest_logger = logging.getLogger("core.ingestion")
        ingest_logger.addHandler(warning_handler)

        try:
            # Scan for documents
            for scan_result in self.scanner.scan(input_dir, resolved_temp_root_dir):
                scan_context = scan_result.context
                doc_ref = scan_result.document
                token = _CURRENT_DOC_LOGICAL_PATH.set(doc_ref.logical_path)
                try:
                    log.debug(f"Processing: {doc_ref.logical_path}")
                    
                    # Load document
                    loaded = self.loader.load(doc_ref)
                    
                    # Validate text extraction for other supported formats (warnings only for now)
                    text_extraction_required = doc_ref.format in ['txt', 'md', 'html', 'htm', 'xml', 'json']
                    if text_extraction_required and not loaded.extracted_text:
                        warning_reason = (
                            f"Text extraction produced no usable text for {doc_ref.logical_path} "
                            f"({doc_ref.format}); file_size_bytes={len(loaded.raw_bytes)} "
                            f"and extracted content is empty or whitespace"
                        )
                        log.warning(warning_reason)
                        # For now, continue processing but mark as warning
                        # Could be changed to raise exception for strict validation
                    
                    # Generate deterministic/document-local ID according to configured strategy.
                    source_file_hash = self._compute_hash(loaded.raw_bytes)
                    doc_id = self.id_generator.generate(loaded.raw_bytes)
                    
                    # Load sidecar metadata
                    sidecar_data = self.metadata_loader.load(doc_ref.real_path)
                    
                    # Create metadata
                    metadata = DocumentMetadata(
                        doc_id=doc_id,
                        logical_path=doc_ref.logical_path,
                        basename=doc_ref.basename,
                        format=doc_ref.format,
                        extracted_text_length=loaded.text_length,
                        pages_count=loaded.pages_count,
                        source_file_hash=source_file_hash,
                        source_file_size=len(loaded.raw_bytes),
                        sidecar_metadata=sidecar_data or {},
                    )
                    
                    # Create document
                    document = IngestedDocument(
                        metadata=metadata,
                        raw_bytes=loaded.raw_bytes,
                        extracted_text=loaded.extracted_text,
                    )
                    
                    # Run internal non-parsing text validation without persisting analyzer output.
                    self.analyzer_pipeline.run(document)

                    # Keep metadata aligned with analyzer-updated text.
                    document.metadata.extracted_text_length = len(document.extracted_text) if document.extracted_text else 0
                    
                    # Persist
                    self.persistence.persist(document, self.config.output)
                    
                    manifest.ingested[doc_ref.logical_path] = doc_id
                    log.info(f"Ingested: {doc_ref.logical_path} → {doc_id}")
                
                except LoadException as e:
                    log.error(f"Failed to load {doc_ref.logical_path}: {e}")
                    manifest.errors[doc_ref.logical_path] = str(e)

                except (AnalyzerConfigurationException, AnalyzerInputException, AnalyzerExecutionException) as e:
                    log.error(f"Failed to ingest {doc_ref.logical_path}: {e}", exc_info=True)
                    manifest.errors[doc_ref.logical_path] = str(e)

                except IDGenerationException as e:
                    log.error(f"Failed to generate ID for {doc_ref.logical_path}: {e}", exc_info=True)
                    manifest.errors[doc_ref.logical_path] = str(e)

                except IngestException:
                    raise
                
                except Exception as e:
                    log.error(f"Failed to ingest {doc_ref.logical_path}: {e}", exc_info=True)
                    manifest.errors[doc_ref.logical_path] = str(e)

                finally:
                    _CURRENT_DOC_LOGICAL_PATH.reset(token)
        
        except IngestException as e:
            log.error(f"Ingestion failed: {e}", exc_info=True)
            raise
        
        finally:
            ingest_logger.removeHandler(warning_handler)
            # Clean up scanner temp dirs once the scan has completed.
            if scan_context is not None:
                scan_context.cleanup()

            # Complete manifest
            manifest.completed_at = datetime.now(UTC)
            
            # Save manifest
            try:
                self.persistence.save_manifest(manifest, self.config.output)
            except Exception as e:
                log.error(f"Failed to save manifest: {e}")
        
        # Log summary
        log.info(
            f"Ingestion complete. "
            f"Success: {len(manifest.ingested)}, "
            f"Errors: {len(manifest.errors)}, "
            f"Success rate: {manifest.success_rate:.1f}%"
        )
        
        return manifest
    
    @staticmethod
    def _compute_hash(data: bytes, algorithm: str = "sha256") -> str:
        """
        Compute hash of data.
        
        Args:
            data: Data to hash
            algorithm: Hash algorithm (default: sha256)
        
        Returns:
            Hex digest
        """
        h = hashlib.new(algorithm)
        h.update(data)
        return h.hexdigest()

    def _resolve_temp_root_dir(self, temp_root_dir: Optional[Path]) -> Optional[Path]:
        """Resolve temporary root with explicit override first, then ZIP configuration."""
        if temp_root_dir is not None:
            return Path(temp_root_dir)

        if self.config.zip_extraction.temp_dir:
            return Path(self.config.zip_extraction.temp_dir)

        return None

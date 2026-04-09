"""
Main ingestion orchestrator.
Coordinates scanning, loading, analysis, and persistence.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import logging
import hashlib
from datetime import datetime, UTC

from .config import IngestConfig
from .scanner import DocumentScanner
from .loader import DocumentLoader
from .sidecar import MetadataLoader
from .id_generator import IDGeneratorFactory
from .analyzers import AnalyzerPipeline
from .backends import PersistenceBackendFactory
from .types import (
    IngestedDocument,
    DocumentMetadata,
    IngestManifest,
    IngestException,
    LoadException,
)

log = logging.getLogger(__name__)


class IngestService:
    """
    Main ingestion service with STRICT correctness enforcement.
    
    INGESTION CORRECTNESS PRINCIPLES:
    - Ingestion phase is responsible for data validation and quality gates
    - Invalid or corrupted documents MUST fail ingestion explicitly
    - No partial success allowed - document either ingests completely or fails
    - Fail fast prevents downstream processing of invalid data
    - Correctness takes priority over completeness
    
    HTML INGESTION CONTRACT:
    - HTML documents MUST produce valid extracted text (>0 length, visible chars)
    - Empty or invalid text extraction = ingestion failure for that document
    - No fallback outputs, no invented content, no silent degradation
    - Each document fails individually (other documents can still succeed)
    
    WHY FAILING FAST IS MANDATORY:
    - Prevents corrupted data from entering downstream processing
    - Ensures search/indexing operates on valid content only
    - Maintains data integrity across the entire pipeline
    - Forces explicit handling of extraction failures rather than hiding them
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
        self.persistence = PersistenceBackendFactory.create(config.output, output_dir)
        
        log.info(f"Initialized IngestService with output_dir={output_dir}, sidecar_base_paths={[str(p) for p in sidecar_base_paths]}")
    
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
        manifest = IngestManifest()
        
        log.info(f"Starting ingestion from {input_dir}")
        
        try:
            # Scan for documents
            for ctx, doc_ref in self.scanner.scan(input_dir, temp_root_dir):
                try:
                    log.debug(f"Processing: {doc_ref.logical_path}")
                    
                    # Load document
                    loaded = self.loader.load(doc_ref)
                    
                    # STRICT VALIDATION: Enforce ingestion correctness for text-extractable formats
                    # HTML documents MUST have valid extracted text or ingestion FAILS for that document
                    # This prevents partial success and ensures downstream processing gets valid data
                    if doc_ref.format in ['html', 'htm']:
                        if not loaded.extracted_text or not loaded.extracted_text.strip():
                            raise LoadException(
                                f"HTML document {doc_ref.logical_path} failed strict text extraction validation - "
                                "no readable content extracted. Ingestion cannot proceed for this document."
                            )
                        # Additional validation: ensure text has visible characters
                        visible_chars = [c for c in loaded.extracted_text if c.isprintable() and not c.isspace()]
                        if not visible_chars:
                            raise LoadException(
                                f"HTML document {doc_ref.logical_path} contains no visible printable characters - "
                                "ingestion failed for data quality reasons."
                            )
                    
                    # Validate text extraction for other supported formats (warnings only for now)
                    text_extraction_required = doc_ref.format in ['txt', 'md']
                    if text_extraction_required and not loaded.extracted_text:
                        log.warning(f"Text extraction failed for {doc_ref.logical_path} ({doc_ref.format})")
                        # For now, continue processing but mark as warning
                        # Could be changed to raise exception for strict validation
                    
                    # Generate deterministic ID
                    doc_id = self.id_generator.generate(loaded.raw_bytes)
                    
                    # Generate deterministic ID
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
                        source_file_hash=self._compute_hash(loaded.raw_bytes),
                        source_file_size=len(loaded.raw_bytes),
                        sidecar_metadata=sidecar_data or {},
                    )
                    
                    # Create document
                    document = IngestedDocument(
                        metadata=metadata,
                        raw_bytes=loaded.raw_bytes,
                        extracted_text=loaded.extracted_text,
                    )
                    
                    # Run analyzers
                    document.analyzer_output = self.analyzer_pipeline.run(document)
                    
                    # Persist
                    self.persistence.persist(document, self.config.output)
                    
                    manifest.ingested[doc_ref.logical_path] = doc_id
                    log.info(f"Ingested: {doc_ref.logical_path} → {doc_id}")
                
                except LoadException as e:
                    log.error(f"Failed to load {doc_ref.logical_path}: {e}")
                    manifest.errors[doc_ref.logical_path] = str(e)
                
                except Exception as e:
                    log.error(f"Failed to ingest {doc_ref.logical_path}: {e}", exc_info=True)
                    manifest.errors[doc_ref.logical_path] = str(e)
                
                finally:
                    # Clean up temporary directories
                    ctx.cleanup()
        
        except IngestException as e:
            log.error(f"Ingestion failed: {e}", exc_info=True)
            raise
        
        finally:
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

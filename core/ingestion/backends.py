"""
Persistence backends for ingested documents.
Pluggable interface allows different storage strategies.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any
import json
import logging

from .types import IngestedDocument, IngestManifest, PersistenceException
from .config import OutputConfig

log = logging.getLogger(__name__)


class PersistenceBackend(ABC):
    """Base class for document persistence."""
    
    @abstractmethod
    def persist(self, document: IngestedDocument, output_config: OutputConfig) -> str:
        """
        Persist a document.
        
        Args:
            document: Ingested document to persist
            output_config: Output configuration
        
        Returns:
            Storage identifier/path
        """
        pass
    
    @abstractmethod
    def save_manifest(self, manifest: IngestManifest, output_config: OutputConfig) -> None:
        """
        Save ingestion manifest.
        
        Args:
            manifest: Manifest to save
            output_config: Output configuration
        """
        pass


class FilesystemBackend(PersistenceBackend):
    """
    Filesystem-based persistence.
    Stores documents in local directory structure.
    """
    
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
    
    def persist(self, document: IngestedDocument, output_config: OutputConfig) -> str:
        """
        Persist document to filesystem.
        
        Creates directory structure:
        {output_dir}/{doc_id}/
            document.{format}
            metadata.json
            extracted.txt (if available)
        
        Args:
            document: Document to persist
            output_config: Output configuration
        
        Returns:
            Relative path to document directory
        """
        fs_config = output_config.filesystem
        
        # Create output directory
        # Parse dir_pattern for variables
        dir_name = fs_config.dir_pattern.replace("{doc_id}", document.metadata.doc_id)
        doc_dir = self.output_dir / dir_name
        doc_dir.mkdir(parents=True, exist_ok=True)
        
        # Persist artifacts based on config
        if output_config.artifacts_original_file:
            extension = f".{document.metadata.format}" if fs_config.preserve_extension and document.metadata.format else ""
            original_filename = f"{document.metadata.doc_id}{extension}"
            original_path = doc_dir / original_filename
            original_path.write_bytes(document.raw_bytes)
            log.debug(f"Persisted original file: {original_path}")

        if output_config.artifacts_extracted_text and document.extracted_text:
            # Save extracted text
            text_path = doc_dir / "extracted.txt"
            text_path.write_text(document.extracted_text, encoding="utf-8")
            log.debug(f"Persisted extracted text: {text_path}")
        
        if output_config.artifacts_document_metadata or output_config.artifacts_sidecar_metadata:
            # Save metadata as: sc_<FULL_DOCUMENT_ID>.json
            # INGESTION REQUIREMENT: Sidecar metadata must follow naming convention
            metadata_dict = document.metadata.__dict__.copy()
            
            # Convert datetime to ISO format
            if hasattr(document.metadata.ingested_at, 'isoformat'):
                metadata_dict['ingested_at'] = document.metadata.ingested_at.isoformat()
            
            meta_filename = f"sc_{document.metadata.doc_id}.json"
            meta_path = doc_dir / meta_filename
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata_dict, f, indent=2, default=str)
            log.debug(f"Persisted sidecar metadata: {meta_path}")
        
        # Create related documents index: rd_<FULL_DOCUMENT_ID>.json
        if output_config.artifacts_related_index:
            self._create_related_documents_index(doc_dir, document)
        
        # Validate required artifacts were created
        self._validate_artifacts(doc_dir, document, output_config)
        
        return str(doc_dir.relative_to(self.output_dir))
    
    # fondamentalmente non fa nulla visto che non so come implementare la ricerca delle relations
    def _create_related_documents_index(self, doc_dir: Path, document: IngestedDocument) -> None:
        """
        Create related documents index for the current document.
        
        INGESTION REQUIREMENT: Related documents index must be created
        Format: rd_<FULL_DOCUMENT_ID>.json
        Contains list of related document references with relationship types
        
        Args:
            doc_dir: Document directory
            document: Ingested document
        """
        from .related_indexes import RelatedDocumentsIndexer
        
        # Create indexer and generate related documents
        indexer = RelatedDocumentsIndexer()
        related_docs = indexer.find_related_documents(document)
        
        # Save as rd_<FULL_DOCUMENT_ID>.json
        rd_filename = f"rd_{document.metadata.doc_id}.json"
        rd_path = doc_dir / rd_filename
        
        with open(rd_path, "w", encoding="utf-8") as f:
            json.dump(related_docs, f, indent=2, default=str)
        
        log.debug(f"Created related documents index: {rd_path} with {len(related_docs)} relations")
    
    # function called after persist, it validate that all required artifacts were created with correct naming convention
    # check if sidecar metadata exists with correct naming: sc_<FULL_DOCUMENT_ID>.json
    # check if related documents index exists with correct naming: rd_<FULL_DOCUMENT_ID>.json
    # check if extracted text exists if the format is text-extractable and artifacts_extracted

    def _validate_artifacts(
        self,
        doc_dir: Path,
        document: IngestedDocument,
        output_config: OutputConfig
    ) -> None:
        """
        Validate that required artifacts were created with correct naming.
        
        INGESTION REQUIREMENT: Strict validation of output composition
        - Original file: <FULL_DOCUMENT_ID>.<extension>
        - Sidecar metadata: sc_<FULL_DOCUMENT_ID>.json
        - Related documents: rd_<FULL_DOCUMENT_ID>.json
        
        Args:
            doc_dir: Document directory
            document: Ingested document
            output_config: Output configuration
        """
        issues = []
        
        # Check sidecar metadata with new naming: sc_<FULL_DOCUMENT_ID>.json
        if output_config.artifacts_document_metadata or output_config.artifacts_sidecar_metadata:
            expected_meta_filename = f"sc_{document.metadata.doc_id}.json"
            meta_path = doc_dir / expected_meta_filename
            if not meta_path.exists():
                issues.append(f"Missing sidecar metadata: {expected_meta_filename}")

        if output_config.artifacts_original_file:
            extension = f".{document.metadata.format}" if output_config.filesystem.preserve_extension and document.metadata.format else ""
            expected_original_filename = f"{document.metadata.doc_id}{extension}"
            original_path = doc_dir / expected_original_filename
            if not original_path.exists():
                issues.append(f"Missing original file: {expected_original_filename}")
        
        # Check related documents index: rd_<FULL_DOCUMENT_ID>.json
        if output_config.artifacts_related_index:
            expected_rd_filename = f"rd_{document.metadata.doc_id}.json"
            rd_path = doc_dir / expected_rd_filename
            if not rd_path.exists():
                issues.append(f"Missing related documents index: {expected_rd_filename}")
        
        # Check extracted text (should exist for text-extractable formats)
        if output_config.artifacts_extracted_text:
            text_path = doc_dir / "extracted.txt"
            if document.extracted_text and not text_path.exists():
                issues.append("Missing extracted.txt despite having extracted text")
            elif not document.extracted_text and document.metadata.format in ['txt', 'md', 'html', 'htm']:
                log.warning(
                    "Missing extracted text for %s format on document %s",
                    document.metadata.format,
                    document.metadata.doc_id,
                )
        
        if issues:
            issue_text = "; ".join(issues)
            log.error(f"Artifact validation failed for {document.metadata.doc_id}: {issue_text}")
            raise PersistenceException(f"Incomplete document artifacts: {issue_text}")
        
        log.debug(f"Artifact validation passed for {document.metadata.doc_id}")
    
    # save the manifest json
    def save_manifest(self, manifest: IngestManifest, output_config: OutputConfig) -> None:
        """
        Save ingestion manifest to JSON.
        
        Args:
            manifest: Manifest to save
            output_config: Output configuration
        """
        if not output_config.filesystem.create_manifest:
            return
        
        manifest_path = self.output_dir / output_config.filesystem.manifest_filename
        
        manifest_dict = manifest.to_dict()
        
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_dict, f, indent=2)
        
        log.info(f"Saved manifest: {manifest_path}")

# create the backend based on the config
# here the backend is just the component that saves the ingested documents

class PersistenceBackendFactory:
    """Factory for creating persistence backends."""
    
    _backends: Dict[str, type] = {
        "filesystem": FilesystemBackend,
    }
    
    @classmethod
    def register(cls, name: str, backend_class: type) -> None:
        """Register a custom backend."""
        cls._backends[name] = backend_class
    
    @classmethod
    def create(
        cls,
        config: OutputConfig,
        output_dir: Path,
    ) -> PersistenceBackend:
        """
        Create persistence backend based on config.
        
        Args:
            config: Output configuration
            output_dir: Output directory
        
        Returns:
            Configured persistence backend
        
        Raises:
            ValueError: If backend type not found
        """
        backend_type = config.backend
        
        if backend_type == "custom":
            raise ValueError(
                "Custom backend must be provided at runtime. "
                "Use PersistenceBackendFactory.register() to add custom backends."
            )
        
        if backend_type not in cls._backends:
            raise ValueError(
                f"Unknown persistence backend: {backend_type}. "
                f"Available: {list(cls._backends.keys())}"
            )
        
        backend_class = cls._backends[backend_type]
        return backend_class(output_dir)

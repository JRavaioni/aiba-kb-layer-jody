"""Unit tests for persistence backends."""

from datetime import UTC, datetime
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.backends import FilesystemBackend, PersistenceBackendFactory
from core.ingestion.config import OutputConfig
from core.ingestion.types import DocumentMetadata, IngestManifest, IngestedDocument


def _doc(fmt: str = "txt", text: str | None = "hello") -> IngestedDocument:
    metadata = DocumentMetadata(
        doc_id="abc123def4567890",
        logical_path=f"in/sample.{fmt}",
        basename="sample",
        format=fmt,
        extracted_text_length=len(text) if text else 0,
        ingested_at=datetime.now(UTC),
    )
    return IngestedDocument(
        metadata=metadata,
        raw_bytes=b"raw-content",
        extracted_text=text,
        analyzer_output={"text_extractor": {"status": "success"}},
    )


def test_filesystem_backend_persist_writes_required_artifacts(tmp_path: Path):
    backend = FilesystemBackend(tmp_path)
    output_config = OutputConfig()

    relative_dir = backend.persist(_doc(), output_config)
    doc_dir = tmp_path / relative_dir

    assert doc_dir.exists()
    assert (doc_dir / "extracted.txt").exists()
    assert (doc_dir / "sc_abc123def4567890.json").exists()
    assert (doc_dir / "rd_abc123def4567890.json").exists()


def test_filesystem_backend_allows_missing_text_with_warning(tmp_path: Path):
    backend = FilesystemBackend(tmp_path)
    output_config = OutputConfig()

    relative_dir = backend.persist(_doc(fmt="txt", text=None), output_config)
    doc_dir = tmp_path / relative_dir

    assert doc_dir.exists()
    assert not (doc_dir / "extracted.txt").exists()
    assert (doc_dir / "sc_abc123def4567890.json").exists()


def test_save_manifest_respects_create_manifest_flag(tmp_path: Path):
    backend = FilesystemBackend(tmp_path)
    output_config = OutputConfig()
    output_config.filesystem.create_manifest = False

    manifest = IngestManifest(ingested={"a.txt": "id1"}, errors={})
    backend.save_manifest(manifest, output_config)

    assert not (tmp_path / output_config.filesystem.manifest_filename).exists()


def test_backend_factory_creates_filesystem_backend(tmp_path: Path):
    config = OutputConfig(backend="filesystem")
    backend = PersistenceBackendFactory.create(config, tmp_path)
    assert isinstance(backend, FilesystemBackend)


def test_backend_factory_unknown_backend_raises(tmp_path: Path):
    config = OutputConfig(backend="unknown_backend")
    with pytest.raises(ValueError):
        PersistenceBackendFactory.create(config, tmp_path)

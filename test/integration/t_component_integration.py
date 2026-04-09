"""Integration tests for interactions between ingestion components."""

from datetime import UTC, datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.config import IDGenerationConfig, IngestConfig, LoaderConfig, OutputConfig
from core.ingestion.id_generator import IDGeneratorFactory
from core.ingestion.ingest_service import IngestService
from core.ingestion.loader import DocumentLoader
from core.ingestion.scanner import DocumentScanner
from core.ingestion.backends import FilesystemBackend
from core.ingestion.types import DocumentMetadata, DocumentRef, IngestedDocument


def test_scanner_loader_integration_reads_discovered_documents(tmp_path: Path):
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    (input_dir / "a.txt").write_text("hello", encoding="utf-8")
    (input_dir / "b.json").write_text('{"x": 1}', encoding="utf-8")

    config = IngestConfig()
    config.input.supported_formats = ["txt", "json"]
    scanner = DocumentScanner(config.input, config.zip_extraction)
    loader = DocumentLoader(LoaderConfig())

    docs = [result.document for result in scanner.scan(input_dir)]
    assert len(docs) == 2

    loaded = [loader.load(doc_ref) for doc_ref in docs]
    assert all(item.raw_bytes for item in loaded)
    assert all(item.extracted_text is not None for item in loaded)


def test_loader_id_backend_integration_persists_under_generated_id(tmp_path: Path):
    input_file = tmp_path / "sample.txt"
    input_file.write_text("payload", encoding="utf-8")

    file_ref = DocumentRef(
        logical_path="sample.txt",
        real_path=input_file,
        format="txt",
        basename="sample",
    )

    loaded = DocumentLoader(LoaderConfig()).load(file_ref)
    generator = IDGeneratorFactory.create(IDGenerationConfig(strategy="sha256-16", prefix="", suffix=""))
    doc_id = generator.generate(loaded.raw_bytes)

    metadata = DocumentMetadata(
        doc_id=doc_id,
        logical_path=file_ref.logical_path,
        basename=file_ref.basename,
        format=file_ref.format,
        extracted_text_length=loaded.text_length,
        source_file_size=len(loaded.raw_bytes),
        ingested_at=datetime.now(UTC),
    )
    document = IngestedDocument(metadata=metadata, raw_bytes=loaded.raw_bytes, extracted_text=loaded.extracted_text)

    backend = FilesystemBackend(tmp_path / "out")
    backend.persist(document, OutputConfig())

    assert (tmp_path / "out" / doc_id).exists()


def test_config_service_integration_applies_runtime_configuration(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    (input_dir / "doc.txt").write_text("hello integration", encoding="utf-8")

    config = IngestConfig.from_dict(
        {
            "input": {"dirs": [str(input_dir)], "supported_formats": ["txt"]},
            "metadata": {"enabled": False},
            "analyzers": {"enabled": True, "pipeline": [{"name": "text_extractor", "enabled": True, "config": {"min_length": 1}}]},
        }
    )

    service = IngestService(config, output_dir)
    manifest = service.ingest(input_dir)

    assert len(manifest.ingested) == 1
    assert manifest.errors == {}
    assert (output_dir / "manifest.json").exists()


def test_metadata_sidecar_integration_persists_sidecar_data(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()

    (input_dir / "contract.txt").write_text("content", encoding="utf-8")
    (input_dir / "contract.json").write_text('{"owner": "team-a", "priority": 1}', encoding="utf-8")

    config = IngestConfig.from_dict(
        {
            "input": {"dirs": [str(input_dir)], "supported_formats": ["txt"]},
            "metadata": {
                "enabled": True,
                "base_paths": [str(input_dir)],
                "search_strategies": [{"name": "by_name", "description": "exact", "rule": "{basename}.json"}],
            },
            "analyzers": {"enabled": False, "pipeline": []},
        }
    )

    service = IngestService(config, output_dir)
    manifest = service.ingest(input_dir)

    doc_id = next(iter(manifest.ingested.values()))
    sidecar_path = output_dir / doc_id / f"sc_{doc_id}.json"
    content = sidecar_path.read_text(encoding="utf-8")

    assert "team-a" in content
    assert "priority" in content

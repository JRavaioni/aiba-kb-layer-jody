"""E2E tests for nested ZIP handling and batch resilience."""

from io import BytesIO
from pathlib import Path
import zipfile
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.config import IngestConfig
from core.ingestion.ingest_service import IngestService


def _service_for(input_dir: Path, output_dir: Path) -> IngestService:
    config = IngestConfig()
    config.input.dirs = [str(input_dir)]
    config.input.supported_formats = ["txt", "zip"]
    config.zip_extraction.enabled = True
    config.zip_extraction.max_archive_depth = 5
    config.analyzers.enabled = False
    config.analyzers.pipeline = []
    return IngestService(config, output_dir)


def test_ingest_nested_zip_extracts_inner_and_outer_documents(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()

    inner_bytes = BytesIO()
    with zipfile.ZipFile(inner_bytes, "w") as inner_zip:
        inner_zip.writestr("inner.txt", "nested data")

    outer_zip_path = input_dir / "outer.zip"
    with zipfile.ZipFile(outer_zip_path, "w") as outer_zip:
        outer_zip.writestr("inner.zip", inner_bytes.getvalue())
        outer_zip.writestr("root.txt", "root data")

    manifest = _service_for(input_dir, output_dir).ingest(input_dir)

    assert len(manifest.ingested) == 2
    assert manifest.errors == {}
    assert any("outer/inner/inner.txt" in logical for logical in manifest.ingested)
    assert any("outer/root.txt" in logical for logical in manifest.ingested)


def test_ingest_continues_when_one_document_fails(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()

    (input_dir / "ok.txt").write_text("valid content", encoding="utf-8")
    # Empty/whitespace txt now logs a warning but does not fail ingestion.
    (input_dir / "bad.txt").write_text("   \n  ", encoding="utf-8")

    manifest = _service_for(input_dir, output_dir).ingest(input_dir)

    assert len(manifest.ingested) == 2
    assert len(manifest.errors) == 0
    assert "ok.txt" in manifest.ingested
    assert "bad.txt" in manifest.ingested
    assert (output_dir / "manifest.json").exists()

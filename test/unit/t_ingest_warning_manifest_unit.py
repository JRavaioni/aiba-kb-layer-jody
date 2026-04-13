"""Unit tests for warning reason propagation into ingest manifest."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.config import IngestConfig
from core.ingestion.ingest_service import IngestService, PIPELINE_WARNING_KEY


def _service_for(input_dir: Path, output_dir: Path) -> IngestService:
    config = IngestConfig()
    config.input.dirs = [str(input_dir)]
    config.input.supported_formats = ["txt"]
    config.input.max_depth = 10
    config.zip_extraction.enabled = False
    config.analyzers.enabled = False
    config.analyzers.pipeline = []
    return IngestService(config, output_dir)


def test_manifest_contains_detailed_reason_for_empty_text_warning(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()

    empty_txt = input_dir / "warning_case.txt"
    empty_txt.write_text("   \n  ", encoding="utf-8")

    manifest = _service_for(input_dir, output_dir).ingest(input_dir)

    assert "warning_case.txt" in manifest.warnings
    reason = manifest.warnings["warning_case.txt"][0].lower()
    assert "warning_case.txt" in reason
    assert "file_size_bytes=" in reason
    assert "empty or whitespace" in reason


def test_manifest_collects_loader_warning_reason(monkeypatch, tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()

    txt_file = input_dir / "broken_decode.txt"
    txt_file.write_text("valid text", encoding="utf-8")

    service = _service_for(input_dir, output_dir)

    def _raise_decode_error(_data: bytes) -> str:
        raise ValueError("synthetic decode failure")

    monkeypatch.setattr(service.loader, "_load_text", _raise_decode_error)

    manifest = service.ingest(input_dir)

    assert "broken_decode.txt" in manifest.warnings
    reasons = "\n".join(manifest.warnings["broken_decode.txt"]).lower()
    assert "failed to extract text from broken_decode.txt" in reasons
    assert "synthetic decode failure" in reasons


def test_manifest_collects_pipeline_level_warning_reasons(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    nested = input_dir / "level1"
    nested.mkdir(parents=True)
    (nested / "ignored.txt").write_text("hello", encoding="utf-8")

    service = _service_for(input_dir, output_dir)
    service.config.input.max_depth = 0

    manifest = service.ingest(input_dir)

    assert PIPELINE_WARNING_KEY in manifest.warnings
    pipeline_reasons = "\n".join(manifest.warnings[PIPELINE_WARNING_KEY]).lower()
    assert "maximum depth" in pipeline_reasons

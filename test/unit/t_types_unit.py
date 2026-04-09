"""Unit tests for ingestion core datatypes."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.types import AnalyzerResult, DocumentMetadata, IngestManifest, IngestedDocument


def test_ingested_document_to_dict_contains_expected_fields():
    now = datetime.now(UTC)
    metadata = DocumentMetadata(
        doc_id="doc1",
        logical_path="a/b.txt",
        basename="b",
        format="txt",
        extracted_text_length=5,
        ingested_at=now,
        sidecar_metadata={"k": "v"},
    )
    doc = IngestedDocument(
        metadata=metadata,
        raw_bytes=b"hello",
        extracted_text="hello",
        analyzer_output={"text_extractor": {"status": "success"}},
    )

    data = doc.to_dict()
    assert data["doc_id"] == "doc1"
    assert data["logical_path"] == "a/b.txt"
    assert data["sidecar_metadata"] == {"k": "v"}
    assert "text_extractor" in data["analyzer_output"]


def test_analyzer_result_to_dict_roundtrip_shape():
    result = AnalyzerResult(
        analyzer_name="json_formatter",
        status="success",
        payload={"formatted": True},
        warnings=["w1"],
        errors=[],
        metrics={"duration_seconds": 0.01},
    )
    as_dict = result.to_dict()

    assert as_dict["analyzer_name"] == "json_formatter"
    assert as_dict["status"] == "success"
    assert as_dict["payload"]["formatted"] is True
    assert as_dict["warnings"] == ["w1"]


def test_manifest_summary_and_timestamps_are_computed():
    started = datetime.now(UTC)
    completed = started + timedelta(seconds=3)
    manifest = IngestManifest(
        ingested={"ok.txt": "id1", "ok2.txt": "id2"},
        errors={"bad.txt": "boom"},
        started_at=started,
        completed_at=completed,
        duplicates_found=1,
    )

    payload = manifest.to_dict()
    assert payload["summary"]["total_input"] == 3
    assert payload["summary"]["successfully_ingested"] == 2
    assert payload["summary"]["failed"] == 1
    assert payload["summary"]["duplicates_found"] == 1
    assert payload["summary"]["success_rate"] > 0
    assert payload["timestamps"]["duration_seconds"] == 3.0

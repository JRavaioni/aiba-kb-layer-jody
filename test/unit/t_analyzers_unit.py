"""Unit tests for non-parsing analyzer implementations."""

from datetime import UTC, datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.analyzers import AnalyzerPipeline, TextExtractorAnalyzer
from core.ingestion.config import AnalyzerConfig
from core.ingestion.types import DocumentMetadata, IngestedDocument


def _document(fmt: str, text: str | None) -> IngestedDocument:
    metadata = DocumentMetadata(
        doc_id="unit_doc",
        logical_path=f"unit/test.{fmt}",
        basename="test",
        format=fmt,
        extracted_text_length=len(text) if text else 0,
        ingested_at=datetime.now(UTC),
    )
    return IngestedDocument(metadata=metadata, raw_bytes=(text or "").encode("utf-8"), extracted_text=text)


def test_text_extractor_removes_null_bytes_when_enabled():
    analyzer = TextExtractorAnalyzer({"min_length": 1, "remove_nulls": True})
    doc = _document("txt", "abc\x00def")

    result = analyzer.analyze(doc)

    assert result.status == "success"
    assert result.payload["null_bytes_removed"] == 1
    assert doc.extracted_text == "abcdef"


def test_text_extractor_marks_short_text_as_invalid():
    analyzer = TextExtractorAnalyzer({"min_length": 10, "remove_nulls": False})
    doc = _document("txt", "short")

    result = analyzer.analyze(doc)

    assert result.status == "success"
    assert result.payload["text_valid"] is False
    assert "below minimum" in result.payload["validation_message"]


def test_pipeline_unknown_parsing_analyzer_is_skipped():
    pipeline = AnalyzerPipeline(
        AnalyzerConfig(
            enabled=True,
            pipeline=[{"name": "unsupported_analyzer", "enabled": True, "config": {}}],
            on_analyzer_error="skip",
        )
    )
    doc = _document("html", "<html><body>Hello</body></html>")

    result = pipeline.run(doc)
    assert result["unsupported_analyzer"]["status"] == "skipped"
    assert "Unknown analyzer" in result["unsupported_analyzer"]["warnings"][0]


def test_pipeline_disabled_returns_empty_results():
    pipeline = AnalyzerPipeline(AnalyzerConfig(enabled=False, pipeline=[]))
    doc = _document("txt", "plain text")
    assert pipeline.run(doc) == {}

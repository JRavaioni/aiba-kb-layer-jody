"""Unit tests for analyzer pipeline behavior without parsing analyzers."""

from datetime import UTC, datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.analyzers import AnalyzerPipeline
from core.ingestion.config import AnalyzerConfig
from core.ingestion.types import DocumentMetadata, IngestedDocument


def _doc(fmt: str, text: str | None) -> IngestedDocument:
    metadata = DocumentMetadata(
        doc_id="doc_switch",
        logical_path=f"tests/doc.{fmt}",
        basename="doc",
        format=fmt,
        extracted_text_length=len(text) if text else 0,
        ingested_at=datetime.now(UTC),
    )
    return IngestedDocument(metadata=metadata, raw_bytes=(text or "").encode("utf-8"), extracted_text=text)


def test_removed_parsing_analyzer_is_reported_as_unknown() -> None:
    pipeline = AnalyzerPipeline(
        AnalyzerConfig(
            enabled=True,
            pipeline=[
                {"name": "removed_parser", "enabled": True, "config": {"remove_scripts": True, "strip_whitespace": True}},
                {"name": "text_extractor", "enabled": True, "config": {"min_length": 1, "remove_nulls": True}},
            ],
            on_analyzer_error="skip",
        )
    )

    html_raw = "<html><body><p>Hello</p><script>bad()</script></body></html>"
    doc = _doc("html", html_raw)

    result = pipeline.run(doc)

    assert result["removed_parser"]["status"] == "skipped"
    assert "unknown analyzer" in result["removed_parser"]["warnings"][0].lower()
    assert doc.extracted_text == html_raw

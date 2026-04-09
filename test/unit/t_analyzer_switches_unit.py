"""Unit tests for analyzer-level feature switches."""

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


def test_html_parser_skipped_when_global_switch_off() -> None:
    pipeline = AnalyzerPipeline(
        AnalyzerConfig(
            enabled=True,
            html_parsing_enabled=False,
            pipeline=[
                {"name": "html_parser", "enabled": True, "config": {"remove_scripts": True, "strip_whitespace": True}},
                {"name": "text_extractor", "enabled": True, "config": {"min_length": 1, "remove_nulls": True}},
            ],
            on_analyzer_error="skip",
        )
    )

    html_raw = "<html><body><p>Hello</p><script>bad()</script></body></html>"
    doc = _doc("html", html_raw)

    result = pipeline.run(doc)

    assert result["html_parser"]["status"] == "skipped"
    assert "disabled" in result["html_parser"]["warnings"][0].lower()
    assert doc.extracted_text == html_raw

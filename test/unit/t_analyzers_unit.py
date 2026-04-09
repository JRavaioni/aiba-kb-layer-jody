"""Unit tests for analyzer implementations introduced by parsing refactor."""

from datetime import UTC, datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.analyzers import HtmlParserAnalyzer, JsonFormatterAnalyzer, XmlParserAnalyzer
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


def test_html_parser_extracts_visible_text():
    analyzer = HtmlParserAnalyzer({"remove_scripts": True, "strip_whitespace": True})
    doc = _document("html", "<html><body><h1>Title</h1><script>bad()</script><p>Body</p></body></html>")

    result = analyzer.analyze(doc)

    assert result.status == "success"
    assert doc.extracted_text is not None
    assert "Title" in doc.extracted_text
    assert "Body" in doc.extracted_text
    assert "bad()" not in doc.extracted_text


def test_xml_parser_flattens_text_content():
    analyzer = XmlParserAnalyzer({"parser": "xml", "strip_whitespace": True})
    doc = _document("xml", "<root><a>Hello</a><b>World</b></root>")

    result = analyzer.analyze(doc)

    assert result.status == "success"
    assert doc.extracted_text is not None
    assert "Hello" in doc.extracted_text
    assert "World" in doc.extracted_text


def test_json_formatter_pretty_prints_valid_json():
    analyzer = JsonFormatterAnalyzer({"indent": 2, "ensure_ascii": False})
    doc = _document("json", '{"a":1,"b":2}')

    result = analyzer.analyze(doc)

    assert result.status == "success"
    assert doc.extracted_text is not None
    assert "\n" in doc.extracted_text
    assert '  "a": 1' in doc.extracted_text


def test_json_formatter_warns_on_invalid_json():
    analyzer = JsonFormatterAnalyzer({"indent": 2, "ensure_ascii": False})
    doc = _document("json", '{"a":}')

    result = analyzer.analyze(doc)

    assert result.status == "success"
    assert result.payload["formatted"] is False
    assert len(result.warnings) == 1

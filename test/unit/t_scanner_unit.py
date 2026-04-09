"""Unit tests for filesystem/zip scanning behavior."""

from pathlib import Path
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.config import InputConfig, ZipExtractionConfig
from core.ingestion.scanner import DocumentScanner
from core.ingestion.types import ScanException


def _collect_logical_paths(scanner: DocumentScanner, root: Path) -> list[str]:
    return [result.document.logical_path for result in scanner.scan(root)]


def test_scan_flat_directory_yields_only_supported_formats(tmp_path: Path):
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.html").write_text("<p>beta</p>", encoding="utf-8")
    (tmp_path / "c.bin").write_bytes(b"\x00\x01")

    scanner = DocumentScanner(
        InputConfig(supported_formats=["txt", "html"]),
        ZipExtractionConfig(enabled=False),
    )

    paths = sorted(_collect_logical_paths(scanner, tmp_path))
    assert paths == ["a.txt", "b.html"]


def test_scan_respects_max_depth(tmp_path: Path):
    (tmp_path / "root.txt").write_text("r", encoding="utf-8")
    (tmp_path / "d1").mkdir()
    (tmp_path / "d1" / "level1.txt").write_text("l1", encoding="utf-8")
    (tmp_path / "d1" / "d2").mkdir()
    (tmp_path / "d1" / "d2" / "level2.txt").write_text("l2", encoding="utf-8")

    scanner = DocumentScanner(
        InputConfig(supported_formats=["txt"], max_depth=1),
        ZipExtractionConfig(enabled=False),
    )

    paths = sorted(_collect_logical_paths(scanner, tmp_path))
    assert paths == ["d1/level1.txt", "root.txt"]


def test_scan_skips_excluded_directory(tmp_path: Path):
    included = tmp_path / "ok"
    excluded = tmp_path / "skipme"
    included.mkdir()
    excluded.mkdir()
    (included / "good.txt").write_text("ok", encoding="utf-8")
    (excluded / "bad.txt").write_text("no", encoding="utf-8")

    scanner = DocumentScanner(
        InputConfig(
            supported_formats=["txt"],
            exclude_paths=[str(excluded)],
        ),
        ZipExtractionConfig(enabled=False),
    )

    paths = _collect_logical_paths(scanner, tmp_path)
    assert paths == ["ok/good.txt"]


def test_scan_zip_extracts_and_preserves_logical_prefix(tmp_path: Path):
    zip_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("inside.txt", "hello")
        zf.writestr("nested/page.html", "<html><body>x</body></html>")

    scanner = DocumentScanner(
        InputConfig(supported_formats=["txt", "html"]),
        ZipExtractionConfig(enabled=True, max_archive_depth=3),
    )

    paths = sorted(_collect_logical_paths(scanner, tmp_path))
    assert "bundle/inside.txt" in paths
    assert "bundle/nested/page.html" in paths


def test_scan_missing_input_dir_raises(tmp_path: Path):
    scanner = DocumentScanner(InputConfig(supported_formats=["txt"]), ZipExtractionConfig())
    with pytest.raises(ScanException):
        list(scanner.scan(tmp_path / "does_not_exist"))

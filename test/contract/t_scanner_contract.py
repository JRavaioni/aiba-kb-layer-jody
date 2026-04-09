"""Contract tests for scanner invariants and robustness."""

from pathlib import Path
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.config import InputConfig, ZipExtractionConfig
from core.ingestion.scanner import DocumentScanner


def _collect_paths(scanner: DocumentScanner, root: Path) -> list[str]:
    return [result.document.logical_path for result in scanner.scan(root)]


def test_scanner_symlink_to_file_is_handled(tmp_path: Path):
    target = tmp_path / "real.txt"
    target.write_text("ok", encoding="utf-8")
    link = tmp_path / "link.txt"

    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Symlink not supported in this environment")

    scanner = DocumentScanner(
        InputConfig(supported_formats=["txt"]),
        ZipExtractionConfig(enabled=False),
    )
    paths = sorted(_collect_paths(scanner, tmp_path))

    assert "real.txt" in paths
    assert "link.txt" in paths


def test_scanner_permission_error_is_non_fatal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    (tmp_path / "ok.txt").write_text("ok", encoding="utf-8")

    original_iterdir = Path.iterdir

    def _iterdir(self):
        if self == blocked:
            raise PermissionError("denied")
        return original_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", _iterdir)

    scanner = DocumentScanner(
        InputConfig(supported_formats=["txt"]),
        ZipExtractionConfig(enabled=False),
    )
    paths = _collect_paths(scanner, tmp_path)

    # Scanner should continue despite one unreadable directory.
    assert paths == ["ok.txt"]


def test_zip_scanning_respects_depth_limit(tmp_path: Path):
    zip_path = tmp_path / "docs.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("inside.txt", "hello from zip")

    scanner = DocumentScanner(
        InputConfig(supported_formats=["txt"], max_depth=0),
        ZipExtractionConfig(enabled=True, max_archive_depth=10),
    )

    # The zip itself is at depth 0, extracted contents would be scanned at depth 1,
    # so with max_depth=0 no inner document should be emitted.
    paths = _collect_paths(scanner, tmp_path)
    assert paths == []

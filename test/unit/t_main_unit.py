"""Unit tests for CLI entry point in main.py."""

from datetime import UTC, datetime
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import main as main_module
from core.ingestion.config import IngestConfig
from core.ingestion.types import IngestManifest


class _FakeService:
    def __init__(self, manifest: IngestManifest):
        self._manifest = manifest
        self.calls: list[Path] = []

    def ingest(self, input_path: Path) -> IngestManifest:
        self.calls.append(Path(input_path))
        return self._manifest


def test_main_exits_zero_on_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "a.txt").write_text("ok", encoding="utf-8")

    config = IngestConfig()
    config.input.dirs = [str(input_dir)]
    manifest = IngestManifest(ingested={"a.txt": "id1"}, errors={}, completed_at=datetime.now(UTC))
    fake_service = _FakeService(manifest)

    monkeypatch.setattr(main_module.IngestConfig, "from_yaml", lambda _path: config)
    monkeypatch.setattr(main_module, "create_ingest_service", lambda _c, _o: fake_service)
    monkeypatch.setattr(sys, "argv", ["main.py", "--config", "x.yaml", "--output", str(tmp_path / "out")])

    with pytest.raises(SystemExit) as exc:
        main_module.main()

    assert exc.value.code == 0
    assert fake_service.calls == [input_dir]


def test_main_exits_one_if_no_valid_input_dirs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    config = IngestConfig()
    config.input.dirs = [str(tmp_path / "missing")]
    fake_service = _FakeService(IngestManifest())

    monkeypatch.setattr(main_module.IngestConfig, "from_yaml", lambda _path: config)
    monkeypatch.setattr(main_module, "create_ingest_service", lambda _c, _o: fake_service)
    monkeypatch.setattr(sys, "argv", ["main.py", "--config", "x.yaml", "--output", str(tmp_path / "out")])

    with pytest.raises(SystemExit) as exc:
        main_module.main()

    assert exc.value.code == 1
    assert fake_service.calls == []


def test_main_exits_one_when_manifest_has_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    config = IngestConfig()
    config.input.dirs = [str(input_dir)]
    manifest = IngestManifest(
        ingested={"ok.txt": "id1"},
        errors={"bad.pdf": "cannot parse"},
        completed_at=datetime.now(UTC),
    )
    fake_service = _FakeService(manifest)

    monkeypatch.setattr(main_module.IngestConfig, "from_yaml", lambda _path: config)
    monkeypatch.setattr(main_module, "create_ingest_service", lambda _c, _o: fake_service)
    monkeypatch.setattr(sys, "argv", ["main.py", "--config", "x.yaml", "--output", str(tmp_path / "out")])

    with pytest.raises(SystemExit) as exc:
        main_module.main()

    assert exc.value.code == 1


def test_main_exits_one_on_missing_config_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    def _raise_missing(_path):
        raise FileNotFoundError("missing file")

    monkeypatch.setattr(main_module.IngestConfig, "from_yaml", _raise_missing)
    monkeypatch.setattr(sys, "argv", ["main.py", "--config", "missing.yaml", "--output", str(tmp_path / "out")])

    with pytest.raises(SystemExit) as exc:
        main_module.main()

    assert exc.value.code == 1

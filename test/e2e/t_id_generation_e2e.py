"""End-to-end tests for configurable ID generation strategies."""

import json
from pathlib import Path
import re

from core.ingestion.config import IngestConfig
from core.ingestion.ingest_service import IngestService


def _base_config(input_dir: Path, strategy: str) -> IngestConfig:
    config = IngestConfig.from_dict(
        {
            "input": {
                "dirs": [str(input_dir)],
                "supported_formats": ["txt"],
            },
            "id_generation": {
                "hash_length_bytes": 16,
                "naming_strategy": strategy,
                "incremental_prefix": "DOC",
                "incremental_pad_digits": 6,
                "enabled_hash": True,
                "enabled_incremental": strategy != "hash_only",
            },
            "metadata": {"enabled": False},
            "analyzers": {"enabled": False, "pipeline": []},
        }
    )
    return config


def _assert_doc_artifacts(output_dir: Path, doc_id: str, extension: str = "txt") -> None:
    doc_dir = output_dir / doc_id
    assert doc_dir.exists()

    original = doc_dir / f"{doc_id}.{extension}"
    sidecar = doc_dir / f"sc_{doc_id}.json"
    related = doc_dir / f"rd_{doc_id}.json"
    extracted = doc_dir / "extracted.txt"

    assert original.exists()
    assert sidecar.exists()
    assert related.exists()
    assert extracted.exists()

    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    assert metadata["doc_id"] == doc_id


def test_pipeline_hash_only_strategy(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    (input_dir / "a.txt").write_text("hello hash", encoding="utf-8")

    service = IngestService(_base_config(input_dir, "hash_only"), output_dir)
    manifest = service.ingest(input_dir)

    doc_id = next(iter(manifest.ingested.values()))
    assert re.fullmatch(r"[0-9a-f]{32}", doc_id)
    _assert_doc_artifacts(output_dir, doc_id)


def test_pipeline_incremental_only_strategy(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    (input_dir / "a.txt").write_text("hello incremental", encoding="utf-8")

    config = _base_config(input_dir, "incremental_only")
    config.id_generation.enabled_hash = False
    config.id_generation.enabled_incremental = True

    service = IngestService(config, output_dir)
    manifest = service.ingest(input_dir)

    doc_id = next(iter(manifest.ingested.values()))
    assert doc_id == "DOC_000001"
    _assert_doc_artifacts(output_dir, doc_id)


def test_pipeline_hash_then_incremental_strategy(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    (input_dir / "a.txt").write_text("hybrid hash first", encoding="utf-8")

    service = IngestService(_base_config(input_dir, "hash_then_incremental"), output_dir)
    manifest = service.ingest(input_dir)

    doc_id = next(iter(manifest.ingested.values()))
    assert re.fullmatch(r"[0-9a-f]{32}", doc_id)
    _assert_doc_artifacts(output_dir, doc_id)


def test_pipeline_incremental_then_hash_strategy(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    (input_dir / "a.txt").write_text("hybrid incremental first", encoding="utf-8")

    service = IngestService(_base_config(input_dir, "incremental_then_hash"), output_dir)
    manifest = service.ingest(input_dir)

    doc_id = next(iter(manifest.ingested.values()))
    assert doc_id == "DOC_000001"
    _assert_doc_artifacts(output_dir, doc_id)


def test_strategy_switching_during_ingestion_runs(tmp_path: Path):
    input_hash = tmp_path / "in_hash"
    input_inc = tmp_path / "in_inc"
    output_dir = tmp_path / "out"
    input_hash.mkdir()
    input_inc.mkdir()

    (input_hash / "a.txt").write_text("same pipeline different strategy A", encoding="utf-8")
    (input_inc / "b.txt").write_text("same pipeline different strategy B", encoding="utf-8")

    hash_service = IngestService(_base_config(input_hash, "hash_only"), output_dir)
    hash_manifest = hash_service.ingest(input_hash)
    hash_doc_id = next(iter(hash_manifest.ingested.values()))

    inc_config = _base_config(input_inc, "incremental_only")
    inc_config.id_generation.enabled_hash = False
    inc_config.id_generation.enabled_incremental = True
    incremental_service = IngestService(inc_config, output_dir)
    incremental_manifest = incremental_service.ingest(input_inc)
    incremental_doc_id = next(iter(incremental_manifest.ingested.values()))

    assert re.fullmatch(r"[0-9a-f]{32}", hash_doc_id)
    assert incremental_doc_id == "DOC_000001"
    _assert_doc_artifacts(output_dir, hash_doc_id)
    _assert_doc_artifacts(output_dir, incremental_doc_id)

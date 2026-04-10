"""Unit tests for configuration parsing and validation."""

from pathlib import Path
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.config import IngestConfig


def test_default_config_is_valid():
    config = IngestConfig()
    assert config.validate() == []


def test_from_dict_normalizes_supported_formats_case():
    config = IngestConfig.from_dict(
        {
            "input": {
                "supported_formats": ["TXT", "Html", "JSON"],
            }
        }
    )

    assert config.input.supported_formats == ["txt", "html", "json"]


def test_from_yaml_requires_ingest_root(tmp_path: Path):
    cfg = tmp_path / "bad.yaml"
    cfg.write_text("input:\n  dirs: ['x']\n", encoding="utf-8")

    with pytest.raises(ValueError):
        IngestConfig.from_yaml(cfg)


def test_from_yaml_loads_ingest_section(tmp_path: Path):
    cfg = tmp_path / "ok.yaml"
    content = {
        "ingest": {
            "input": {"dirs": ["my_input"], "supported_formats": ["txt"]},
            "analyzers": {"enabled": True, "pipeline": []},
        }
    }
    cfg.write_text(yaml.safe_dump(content), encoding="utf-8")

    config = IngestConfig.from_yaml(cfg)
    assert config.input.dirs == ["my_input"]
    assert config.analyzers.enabled is True


def test_from_dict_loads_zip_extraction_temp_dir():
    config = IngestConfig.from_dict(
        {
            "zip_extraction": {
                "enabled": True,
                "temp_dir": "custom/tmp/zip-root",
            }
        }
    )

    assert config.zip_extraction.temp_dir == "custom/tmp/zip-root"


def test_validate_rejects_blank_zip_temp_dir():
    config = IngestConfig.from_dict(
        {
            "zip_extraction": {
                "temp_dir": "   ",
            }
        }
    )

    errors = config.validate()
    assert any("zip_extraction.temp_dir must be a non-empty string or null" in err for err in errors)


def test_validate_rejects_zip_temp_dir_pointing_to_file(tmp_path: Path):
    temp_file = tmp_path / "not-a-dir.txt"
    temp_file.write_text("x", encoding="utf-8")

    config = IngestConfig.from_dict(
        {
            "zip_extraction": {
                "temp_dir": str(temp_file),
            }
        }
    )

    errors = config.validate()
    assert any("zip_extraction.temp_dir must point to a directory, not a file" in err for err in errors)


def test_validate_rejects_non_list_pipeline():
    config = IngestConfig.from_dict(
        {
            "analyzers": {
                "pipeline": {"name": "text_extractor"},
            }
        }
    )

    errors = config.validate()
    assert any("analyzers.pipeline must be a list" in err for err in errors)


def test_validate_rejects_non_dict_pipeline_entry():
    config = IngestConfig.from_dict(
        {
            "analyzers": {
                "pipeline": ["text_extractor"],
            }
        }
    )

    errors = config.validate()
    assert any("analyzers.pipeline[0] must be a dictionary" in err for err in errors)


def test_set_updates_nested_value_with_dot_notation():
    config = IngestConfig()
    config.set("input.max_depth", 42)
    assert config.input.max_depth == 42

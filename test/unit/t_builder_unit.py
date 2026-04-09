"""Unit tests for IngestBuilder behavior."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.builder import IngestBuilder, create_ingest_service
from core.ingestion.config import IngestConfig
from core.ingestion.id_generator import UUID4IDGenerator
from core.ingestion.backends import FilesystemBackend
from core.ingestion.ingest_service import IngestService


def _minimal_config(input_dir: Path) -> dict:
    return {
        "input": {"dirs": [str(input_dir)], "supported_formats": ["txt"]},
        "output": {"backend": "filesystem"},
        "analyzers": {"enabled": True, "pipeline": []},
    }


def test_builder_requires_output_dir(tmp_path: Path):
    builder = IngestBuilder.from_dict(_minimal_config(tmp_path))
    with pytest.raises(ValueError):
        builder.build()


def test_builder_with_config_value_updates_nested_field(tmp_path: Path):
    builder = IngestBuilder.from_dict(_minimal_config(tmp_path))
    builder.with_config_value("input.max_depth", 3)
    assert builder.config.input.max_depth == 3


def test_builder_enable_analyzers_switch(tmp_path: Path):
    builder = IngestBuilder.from_dict(_minimal_config(tmp_path))
    builder.enable_analyzers(False)
    assert builder.config.analyzers.enabled is False


def test_builder_custom_components_update_strategy_fields(tmp_path: Path):
    builder = IngestBuilder.from_dict(_minimal_config(tmp_path))
    builder.with_id_generator(UUID4IDGenerator(builder.config.id_generation))
    builder.with_backend(FilesystemBackend(tmp_path))

    assert builder.config.id_generation.strategy == "custom"
    assert builder.config.output.backend == "custom"


def test_builder_build_returns_ingest_service(tmp_path: Path):
    (tmp_path / "in").mkdir()
    config_dict = _minimal_config(tmp_path / "in")

    service = IngestBuilder.from_dict(config_dict).with_output_dir(tmp_path / "out").build()
    assert isinstance(service, IngestService)
    assert (tmp_path / "out").exists()


def test_create_ingest_service_from_yaml(tmp_path: Path):
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    config_path = tmp_path / "ingest.yaml"
    config = IngestConfig.from_dict(_minimal_config(input_dir))

    # Write config using ingest root expected by from_yaml.
    config_yaml = {
        "ingest": {
            "input": {
                "dirs": config.input.dirs,
                "supported_formats": config.input.supported_formats,
                "max_depth": config.input.max_depth,
                "exclude_paths": config.input.exclude_paths,
            },
            "output": {"backend": config.output.backend},
            "analyzers": {"enabled": True, "pipeline": []},
        }
    }

    import yaml

    config_path.write_text(yaml.safe_dump(config_yaml), encoding="utf-8")

    service = create_ingest_service(config_path, tmp_path / "out")
    assert isinstance(service, IngestService)

"""Contract tests for YAML/dict configuration parsing and validation."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.config import IngestConfig


class TestYamlConfig:
    def test_valid_config_from_dict(self):
        config = IngestConfig.from_dict(
            {
                "input": {"dirs": ["ingestion_test_data/raw"]},
                "id_generation": {"strategy": "sha256-16"},
                "output": {"backend": "filesystem"},
                "analyzers": {"enabled": True, "pipeline": []},
            }
        )

        errors = config.validate()
        assert errors == []
        assert config.id_generation.strategy == "sha256-16"

    def test_invalid_id_generation_strategy_fails_validation(self):
        config = IngestConfig.from_dict(
            {
                "id_generation": {"strategy": "sha256_first_16"},
                "analyzers": {"enabled": True, "pipeline": []},
            }
        )

        errors = config.validate()
        assert any("id_generation.strategy" in e for e in errors)

    def test_duplicate_analyzer_names_fail_validation(self):
        config = IngestConfig.from_dict(
            {
                "analyzers": {
                    "enabled": True,
                    "pipeline": [
                        {"name": "text_extractor", "enabled": True, "config": {}},
                        {"name": "text_extractor", "enabled": True, "config": {}},
                    ],
                }
            }
        )

        errors = config.validate()
        assert any("Duplicate analyzer name" in e for e in errors)

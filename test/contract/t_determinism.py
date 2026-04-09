"""Contract tests for deterministic ID generation behavior."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.config import IDGenerationConfig
from core.ingestion.id_generator import IDGeneratorFactory


class TestDeterminism:
    def test_sha256_16_is_deterministic(self):
        generator = IDGeneratorFactory.create(
            IDGenerationConfig(strategy="sha256-16", prefix="doc_", suffix="")
        )

        content = b"This is a deterministic payload"
        assert generator.generate(content) == generator.generate(content)

    def test_same_content_same_id(self):
        generator = IDGeneratorFactory.create(
            IDGenerationConfig(strategy="sha256-16", prefix="doc_", suffix="")
        )

        content = b"Identical content"
        id_a = generator.generate(content)
        id_b = generator.generate(content)

        assert id_a == id_b

    def test_different_content_different_id(self):
        generator = IDGeneratorFactory.create(
            IDGenerationConfig(strategy="sha256-16", prefix="doc_", suffix="")
        )

        assert generator.generate(b"payload A") != generator.generate(b"payload B")

    def test_id_format_sha256_16(self):
        generator = IDGeneratorFactory.create(
            IDGenerationConfig(strategy="sha256-16", prefix="doc_", suffix="")
        )

        doc_id = generator.generate(b"format check")
        assert doc_id.startswith("doc_")

        hash_part = doc_id.removeprefix("doc_")
        assert len(hash_part) == 16
        int(hash_part, 16)  # must be valid hex

    def test_invalid_strategy_raises(self):
        with pytest.raises(ValueError):
            IDGeneratorFactory.create(IDGenerationConfig(strategy="sha256_first_16"))

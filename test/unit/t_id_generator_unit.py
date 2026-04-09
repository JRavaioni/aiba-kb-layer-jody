"""Unit tests for ID generation strategies and edge cases."""

from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.config import IDGenerationConfig
from core.ingestion.id_generator import IDGeneratorFactory


def test_sha256_16_deterministic_and_length():
    cfg = IDGenerationConfig(strategy="sha256-16", prefix="", suffix="")
    gen = IDGeneratorFactory.create(cfg)

    doc_id_1 = gen.generate(b"same-bytes")
    doc_id_2 = gen.generate(b"same-bytes")

    assert doc_id_1 == doc_id_2
    assert len(doc_id_1) == 16
    assert re.fullmatch(r"[0-9a-f]{16}", doc_id_1)


def test_sha256_32_uses_full_hexdigest():
    cfg = IDGenerationConfig(strategy="sha256-32", prefix="", suffix="")
    gen = IDGeneratorFactory.create(cfg)

    doc_id = gen.generate(b"payload")
    assert len(doc_id) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", doc_id)


def test_prefix_suffix_are_preserved():
    cfg = IDGenerationConfig(strategy="sha256-16", prefix="pre_", suffix="_suf")
    gen = IDGeneratorFactory.create(cfg)

    doc_id = gen.generate(b"x")
    assert doc_id.startswith("pre_")
    assert doc_id.endswith("_suf")


def test_uuid4_generator_produces_non_deterministic_values():
    cfg = IDGenerationConfig(strategy="uuid4", prefix="", suffix="")
    gen = IDGeneratorFactory.create(cfg)

    id1 = gen.generate(b"same-input")
    id2 = gen.generate(b"same-input")
    assert id1 != id2
    assert len(id1) == 16
    assert len(id2) == 16


def test_invalid_strategy_raises_value_error():
    cfg = IDGenerationConfig(strategy="not-supported")
    with pytest.raises(ValueError):
        IDGeneratorFactory.create(cfg)


def test_empty_and_large_payloads_supported():
    cfg = IDGenerationConfig(strategy="sha256-16", prefix="", suffix="")
    gen = IDGeneratorFactory.create(cfg)

    empty_id = gen.generate(b"")
    large_id = gen.generate(b"a" * (5 * 1024 * 1024))

    assert len(empty_id) == 16
    assert len(large_id) == 16
    assert empty_id != large_id

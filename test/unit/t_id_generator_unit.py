"""Unit tests for configurable ID generation strategies."""

from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.config import IDGenerationConfig
from core.ingestion.config import IngestConfig
from core.ingestion.id_generator import IDGeneratorFactory
from core.ingestion.types import InvalidIDGenerationConfig


@pytest.mark.parametrize("hash_bytes, expected_hex_len", [(8, 16), (16, 32), (32, 64)])
def test_hash_only_strategy_supports_multiple_lengths(hash_bytes: int, expected_hex_len: int):
    gen = IDGeneratorFactory.create(
        IDGenerationConfig(
            hash_length_bytes=hash_bytes,
            naming_strategy="hash_only",
            enabled_hash=True,
            enabled_incremental=False,
        )
    )
    doc_id = gen.generate(b"hash-payload")
    assert len(doc_id) == expected_hex_len
    assert re.fullmatch(r"[0-9a-f]+", doc_id)


def test_incremental_only_uses_prefix_and_padding():
    gen = IDGeneratorFactory.create(
        IDGenerationConfig(
            naming_strategy="incremental_only",
            incremental_prefix="FILE",
            incremental_pad_digits=4,
            enabled_hash=False,
            enabled_incremental=True,
        )
    )
    assert gen.generate(b"a") == "FILE_0001"
    assert gen.generate(b"b") == "FILE_0002"


def test_hash_then_incremental_fallback_behavior():
    cfg = IDGenerationConfig(
        naming_strategy="hash_then_incremental",
        enabled_hash=True,
        enabled_incremental=True,
        incremental_prefix="DOC",
        incremental_pad_digits=3,
        hash_length_bytes=8,
    )
    gen = IDGeneratorFactory.create(cfg)
    out = gen.generate(b"same")
    assert re.fullmatch(r"[0-9a-f]{16}", out)


def test_incremental_then_hash_fallback_behavior():
    cfg = IDGenerationConfig(
        naming_strategy="incremental_then_hash",
        enabled_hash=True,
        enabled_incremental=True,
        incremental_prefix="DOC",
        incremental_pad_digits=3,
        hash_length_bytes=8,
    )
    gen = IDGeneratorFactory.create(cfg)
    assert gen.generate(b"x") == "DOC_001"
    assert gen.generate(b"y") == "DOC_002"


def test_validation_errors_for_invalid_parameters():
    with pytest.raises(InvalidIDGenerationConfig):
        IDGeneratorFactory.create(
            IDGenerationConfig(
                hash_length_bytes=3,
                naming_strategy="hash_only",
                enabled_hash=True,
            )
        )

    with pytest.raises(InvalidIDGenerationConfig):
        IDGeneratorFactory.create(
            IDGenerationConfig(
                naming_strategy="incremental_only",
                incremental_pad_digits=11,
                enabled_hash=False,
                enabled_incremental=True,
            )
        )

    with pytest.raises(InvalidIDGenerationConfig):
        IDGeneratorFactory.create(
            IDGenerationConfig(
                naming_strategy="hash_only",
                enabled_hash=False,
                enabled_incremental=False,
            )
        )


def test_hash_determinism_same_input_same_id():
    gen = IDGeneratorFactory.create(
        IDGenerationConfig(
            hash_length_bytes=16,
            naming_strategy="hash_only",
            enabled_hash=True,
            enabled_incremental=False,
        )
    )
    payload = b"deterministic"
    assert gen.generate(payload) == gen.generate(payload)


def test_incrementality_increases_sequentially():
    gen = IDGeneratorFactory.create(
        IDGenerationConfig(
            naming_strategy="incremental_only",
            incremental_prefix="DOC",
            incremental_pad_digits=6,
            enabled_hash=False,
            enabled_incremental=True,
        )
    )
    assert gen.generate(b"same") == "DOC_000001"
    assert gen.generate(b"same") == "DOC_000002"
    assert gen.generate(b"same") == "DOC_000003"


def test_hash_collisions_avoidance_for_different_documents():
    gen = IDGeneratorFactory.create(
        IDGenerationConfig(
            hash_length_bytes=16,
            naming_strategy="hash_only",
            enabled_hash=True,
            enabled_incremental=False,
        )
    )
    assert gen.generate(b"payload-a") != gen.generate(b"payload-b")


def test_legacy_sha_strategy_prefix_suffix_are_preserved():
    gen = IDGeneratorFactory.create(
        IDGenerationConfig(
            strategy="sha256-16",
            prefix="doc_",
            suffix="_v1",
            hash_digits=None,
            hash_length_bytes=None,
            naming_strategy="hash_only",
            enabled_hash=True,
            enabled_incremental=False,
        )
    )
    doc_id = gen.generate(b"legacy-compatible")
    assert doc_id.startswith("doc_")
    assert doc_id.endswith("_v1")


def test_sha256_32_strategy_generates_32_hex_digits_when_no_override():
    gen = IDGeneratorFactory.create(
        IDGenerationConfig(
            strategy="sha256-32",
            hash_digits=None,
            hash_length_bytes=None,
            naming_strategy="hash_only",
            enabled_hash=True,
            enabled_incremental=False,
        )
    )
    doc_id = gen.generate(b"strategy-size")
    assert re.fullmatch(r"[0-9a-f]{32}", doc_id)


def test_warning_when_both_hash_digits_and_hash_length_bytes_are_set(caplog):
    with caplog.at_level("WARNING"):
        IngestConfig.from_dict(
            {
                "id_generation": {
                    "strategy": "sha256-16",
                    "hash_digits": 24,
                    "hash_length_bytes": 12,
                    "naming_strategy": "hash_only",
                    "enabled_hash": True,
                    "enabled_incremental": False,
                }
            }
        )
    assert "both hash_digits and hash_length_bytes are set" in caplog.text


def test_warning_when_hash_digits_overrides_strategy(caplog):
    with caplog.at_level("WARNING"):
        IngestConfig.from_dict(
            {
                "id_generation": {
                    "strategy": "sha256-32",
                    "hash_digits": 20,
                    "naming_strategy": "hash_only",
                    "enabled_hash": True,
                    "enabled_incremental": False,
                }
            }
        )
    assert "hash_digits is set; strategy-derived hash length is overridden" in caplog.text

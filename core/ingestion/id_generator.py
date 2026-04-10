"""
Document ID generation strategies.
Implements deterministic and non-deterministic ID generation.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
import hashlib
import logging
import threading
from typing import Type

from .types import IDGenerationConfig, IDGenerationException, InvalidIDGenerationConfig

log = logging.getLogger(__name__)


class IDGenerator(ABC):
    """Base class for ID generation strategies."""
    
    @abstractmethod
    def generate(self, file_bytes: bytes) -> str:
        """Generate an ID from file bytes."""
        pass


class SHA256IDGenerator(IDGenerator):
    """Backward-compatible alias for hash-based ID generation."""
    
    def __init__(self, config: IDGenerationConfig):
        self._delegate = HashIDGenerator(config)
    
    def generate(self, file_bytes: bytes) -> str:
        """Generate SHA256-based ID."""
        return self._delegate.generate(file_bytes)


class UUID4IDGenerator(IDGenerator):
    """Backward-compatible generator kept for tests/custom usage."""
    
    def __init__(self, config: IDGenerationConfig):
        self.config = config
        self._counter = 0
        self._lock = threading.Lock()
    
    def generate(self, file_bytes: bytes) -> str:
        """Generate non-deterministic style ID for backward compatibility."""
        with self._lock:
            self._counter += 1
            digest = hashlib.sha256(file_bytes + str(self._counter).encode("utf-8")).hexdigest()
            digits = self.config.hash_digits
            if digits is None:
                if self.config.hash_length_bytes is not None:
                    digits = max(8, min(64, self.config.hash_length_bytes * 2))
                else:
                    digits = 16
            return digest[:digits]


class HashIDGenerator(IDGenerator):
    """Generate deterministic IDs from SHA256 hash truncated by byte length."""

    def __init__(self, config: IDGenerationConfig):
        self.config = config

    def _resolve_hash_digits(self) -> int:
        # Precedence order: hash_digits > hash_length_bytes > strategy default.
        if self.config.hash_digits is not None:
            return self.config.hash_digits
        if self.config.hash_length_bytes is not None:
            return self.config.hash_length_bytes * 2
        if self.config.strategy == "sha256-32":
            return 32
        return 16

    def generate(self, file_bytes: bytes) -> str:
        try:
            full_hash = hashlib.sha256(file_bytes).hexdigest()
            digits = self._resolve_hash_digits()
            hash_part = full_hash[:digits]
            out = f"{self.config.prefix}{hash_part}{self.config.suffix}"
            log.debug("Generated hash ID=%s (digits=%d)", out, digits)
            return out
        except Exception as exc:
            raise IDGenerationException(f"Failed to generate hash ID: {exc}") from exc


class IncrementalIDGenerator(IDGenerator):
    """Generate sequential IDs with prefix and zero-padding."""

    def __init__(self, prefix: str = "DOC", pad_digits: int = 6):
        self.prefix = prefix
        self.pad_digits = pad_digits
        self._counter = 0
        self._lock = threading.Lock()

    def generate(self, file_bytes: bytes) -> str:
        try:
            with self._lock:
                self._counter += 1
                number = f"{self._counter:0{self.pad_digits}d}"
            generated = f"{self.prefix}_{number}" if self.prefix else number
            log.debug("Generated incremental ID=%s", generated)
            return generated
        except Exception as exc:
            raise IDGenerationException(f"Failed to generate incremental ID: {exc}") from exc


class CompoundIDGenerator(IDGenerator):
    """Try one generator first, then fallback to a second one."""

    def __init__(self, primary: IDGenerator, fallback: IDGenerator):
        self.primary = primary
        self.fallback = fallback

    def generate(self, file_bytes: bytes) -> str:
        try:
            return self.primary.generate(file_bytes)
        except Exception as primary_exc:
            log.warning("Primary ID strategy failed, using fallback: %s", primary_exc)
            try:
                return self.fallback.generate(file_bytes)
            except Exception as fallback_exc:
                raise IDGenerationException(
                    f"Both ID generation strategies failed. Primary: {primary_exc}; Fallback: {fallback_exc}"
                ) from fallback_exc


class IDGeneratorFactory:
    """Factory for creating ID generators."""

    _generators: dict[str, Type[IDGenerator]] = {}
    
    @classmethod
    def register(cls, strategy: str, generator_class: Type[IDGenerator]) -> None:
        """Register a custom ID generator."""
        cls._generators[strategy] = generator_class
    
    @classmethod
    def create(cls, config: IDGenerationConfig) -> IDGenerator:
        """Create an ID generator based on naming strategy and enabled flags."""
        try:
            cls._validate_config(config)
        except InvalidIDGenerationConfig as exc:
            log.error("Invalid ID generation configuration: %s", exc)
            raise

        hash_generator = HashIDGenerator(config)
        incremental_generator = IncrementalIDGenerator(
            prefix=config.incremental_prefix,
            pad_digits=config.incremental_pad_digits,
        )

        strategy = config.naming_strategy

        if strategy == "hash_only":
            return hash_generator
        if strategy == "incremental_only":
            return incremental_generator
        if strategy == "hash_then_incremental":
            return CompoundIDGenerator(primary=hash_generator, fallback=incremental_generator)
        if strategy == "incremental_then_hash":
            return CompoundIDGenerator(primary=incremental_generator, fallback=hash_generator)

        if strategy in cls._generators:
            return cls._generators[strategy](config)

        log.error("Unsupported naming_strategy configured: %s", strategy)
        raise InvalidIDGenerationConfig(
            f"Unknown naming_strategy: {strategy}. "
            "Supported values: hash_only, incremental_only, hash_then_incremental, incremental_then_hash"
        )

    @staticmethod
    def _validate_config(config: IDGenerationConfig) -> None:
        if not config.enabled_hash and not config.enabled_incremental:
            raise InvalidIDGenerationConfig(
                "Invalid ID generation configuration: both enabled_hash and enabled_incremental are false"
            )

        if config.strategy not in {"sha256-16", "sha256-32"}:
            raise InvalidIDGenerationConfig("strategy must be one of: sha256-16, sha256-32")

        if config.hash_length_bytes is not None:
            if config.hash_length_bytes < 4 or config.hash_length_bytes > 32:
                raise InvalidIDGenerationConfig("hash_length_bytes must be between 4 and 32")

        if config.hash_digits is not None:
            if config.hash_digits < 8 or config.hash_digits > 64:
                raise InvalidIDGenerationConfig("hash_digits must be between 8 and 64")
            if config.hash_digits % 2 != 0:
                raise InvalidIDGenerationConfig("hash_digits must be an even number")

        if config.incremental_pad_digits < 1 or config.incremental_pad_digits > 10:
            raise InvalidIDGenerationConfig("incremental_pad_digits must be between 1 and 10")

        combined_strategies = {"hash_then_incremental", "incremental_then_hash"}
        if config.naming_strategy in combined_strategies:
            if not config.enabled_hash or not config.enabled_incremental:
                raise InvalidIDGenerationConfig(
                    f"{config.naming_strategy} requires both enabled_hash and enabled_incremental to be true"
                )

        if config.naming_strategy == "hash_only" and not config.enabled_hash:
            raise InvalidIDGenerationConfig("hash_only requires enabled_hash=true")

        if config.naming_strategy == "incremental_only" and not config.enabled_incremental:
            raise InvalidIDGenerationConfig("incremental_only requires enabled_incremental=true")

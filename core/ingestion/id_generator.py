"""
Document ID generation strategies.
Implements deterministic and non-deterministic ID generation.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
import hashlib
import uuid
from typing import Type

from .config import IDGenerationConfig


class IDGenerator(ABC):
    """Base class for ID generation strategies."""
    
    @abstractmethod
    def generate(self, file_bytes: bytes) -> str:
        """Generate an ID from file bytes."""
        pass


class SHA256IDGenerator(IDGenerator):
    """Generate IDs from SHA256 hash of file bytes."""
    
    def __init__(self, config: IDGenerationConfig):
        self.config = config
    
    def generate(self, file_bytes: bytes) -> str:
        """Generate SHA256-based ID."""
        if self.config.strategy == "sha256-32":
            # Full 32-character SHA256
            hash_val = hashlib.sha256(file_bytes).hexdigest()
        else:
            # First 16 characters (default)
            hash_val = hashlib.sha256(file_bytes).hexdigest()[:16]
        
        return f"{self.config.prefix}{hash_val}{self.config.suffix}"


class UUID4IDGenerator(IDGenerator):
    """Generate IDs from random UUID4."""
    
    def __init__(self, config: IDGenerationConfig):
        self.config = config
    
    def generate(self, file_bytes: bytes) -> str:
        """Generate random UUID4-based ID (NOT deterministic)."""
        id_val = str(uuid.uuid4()).replace("-", "")[:16]
        return f"{self.config.prefix}{id_val}{self.config.suffix}"


class IDGeneratorFactory:
    """Factory for creating ID generators."""
    
    _generators: dict[str, Type[IDGenerator]] = {
        "sha256-16": SHA256IDGenerator,
        "sha256-32": SHA256IDGenerator,
        "uuid4": UUID4IDGenerator,
    }
    
    @classmethod
    def register(cls, strategy: str, generator_class: Type[IDGenerator]) -> None:
        """Register a custom ID generator."""
        cls._generators[strategy] = generator_class
    
    @classmethod
    def create(cls, config: IDGenerationConfig) -> IDGenerator:
        """Create an ID generator based on config strategy."""
        strategy = config.strategy
        
        if strategy == "custom":
            raise ValueError(
                "Custom ID generator must be provided at runtime. "
                "Use IDGeneratorFactory.register() to add custom strategies."
            )
        
        if strategy not in cls._generators:
            raise ValueError(
                f"Unknown ID generation strategy: {strategy}. "
                f"Available: {list(cls._generators.keys())}"
            )
        
        generator_class = cls._generators[strategy]
        return generator_class(config)

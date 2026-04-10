"""
Builder pattern for IngestService construction.
Simplifies configuration and instantiation.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional, Type

from .config import IngestConfig
from .ingest_service import IngestService
from .id_generator import IDGenerator
from .backends import PersistenceBackend
from .analyzers import Analyzer


class IngestBuilder:
    """
    Builder for constructing IngestService instances.
    """
    
    def __init__(self, config: IngestConfig):
        self.config = config
        self._output_dir: Optional[Path] = None
        self._custom_id_generator: Optional[IDGenerator] = None
        self._custom_backend: Optional[PersistenceBackend] = None
    
    @classmethod
    def from_config(cls, config_path: Path | str) -> IngestBuilder:
        """
        Create builder from YAML config file.
        
        Args:
            config_path: Path to YAML configuration file
        
        Returns:
            Configured IngestBuilder
        """
        config = IngestConfig.from_yaml(Path(config_path))
        return cls(config)
    
    @classmethod
    def from_dict(cls, config_dict: dict) -> IngestBuilder:
        """
        Create builder from configuration dictionary.
        
        Args:
            config_dict: Configuration dictionary (format: {"ingest": {...}})
        
        Returns:
            Configured IngestBuilder
        """
        config = IngestConfig.from_dict(config_dict)
        return cls(config)
    
    @classmethod
    def default(cls) -> IngestBuilder:
        """
        Create builder with default configuration.
        
        Returns:
            IngestBuilder with defaults
        """
        config = IngestConfig()
        return cls(config)
    
    def with_output_dir(self, output_dir: Path | str) -> IngestBuilder:
        """
        Set output directory.
        
        Args:
            output_dir: Output directory path
        
        Returns:
            Self for chaining
        """
        self._output_dir = Path(output_dir)
        return self
    
    def with_config_value(self, key_path: str, value) -> IngestBuilder:
        """
        Set a configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path (e.g., "input.max_depth")
            value: Value to set
        
        Returns:
            Self for chaining
        """
        self.config.set(key_path, value)
        return self
    
    def with_id_generator(self, generator: IDGenerator) -> IngestBuilder:
        """
        Provide custom ID generator.
        
        Args:
            generator: IDGenerator instance
        
        Returns:
            Self for chaining
        """
        self._custom_id_generator = generator
        # Update config strategy to custom
        self.config.id_generation.strategy = "custom"
        return self
    
    def with_backend(self, backend: PersistenceBackend) -> IngestBuilder:
        """
        Provide custom persistence backend.
        
        Args:
            backend: PersistenceBackend instance
        
        Returns:
            Self for chaining
        """
        self._custom_backend = backend
        # Update config backend to custom
        self.config.output.backend = "custom"
        return self
    
    def enable_analyzers(self, enabled: bool = True) -> IngestBuilder:
        """
        Enable or disable analyzer pipeline.
        
        Args:
            enabled: Whether to enable analyzers
        
        Returns:
            Self for chaining
        """
        self.config.analyzers.enabled = enabled
        return self
    
    def build(self) -> IngestService:
        """
        Build IngestService instance.
        
        Returns:
            Configured IngestService
        
        Raises:
            ValueError: If required configuration is missing
        """
        if not self._output_dir:
            raise ValueError("Output directory not set. Use with_output_dir()")
        
        service = IngestService(self.config, self._output_dir)

        if self._custom_id_generator is not None:
            service.set_id_generator(self._custom_id_generator)

        if self._custom_backend is not None:
            service.set_persistence_backend(self._custom_backend)
        
        return service


# Convenience function
def create_ingest_service(
    config_path: Path | str,
    output_dir: Path | str,
) -> IngestService:
    """
    Create IngestService from configuration file and output directory.
    
    Args:
        config_path: Path to YAML configuration
        output_dir: Output directory
    
    Returns:
        Configured IngestService
    
    Example:
        ```python
        service = create_ingest_service(
            "config/ingest.yaml",
            "output/"
        )
        manifest = service.ingest("input/")
        ```
    """
    return (
        IngestBuilder.from_config(config_path)
        .with_output_dir(output_dir)
        .build()
    )

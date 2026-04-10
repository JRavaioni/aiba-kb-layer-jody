"""
Configuration loading and validation for ingestion module.
Schema is defined in docs/ingest-config-schema.md
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

from .types import IDGenerationConfig, InvalidIDGenerationConfig

try:
    import yaml
except ImportError:
    raise ImportError("PyYAML is required. Install with: pip install pyyaml")

log = logging.getLogger(__name__)


@dataclass
class InputConfig:
    """Input discovery configuration."""
    dirs: List[str] = field(default_factory=lambda: ["ingestion_test_data/raw"])
    supported_formats: List[str] = field(default_factory=lambda: ["pdf", "docx", "html", "txt"])
    max_depth: int = 10
    exclude_paths: List[str] = field(default_factory=list)
    
    def normalize_formats(self) -> None:
        """Convert formats to lowercase."""
        self.supported_formats = [f.lower() for f in self.supported_formats]


@dataclass
class ZipExtractionConfig:
    """ZIP archive handling configuration."""
    enabled: bool = True
    max_archive_depth: int = 3
    exclude_patterns_in_archive: List[str] = field(default_factory=list)
    temp_dir: Optional[str] = None


@dataclass
class LoaderConfig:
    """Document loading and text extraction configuration."""
    encoding_fallback: List[str] = field(default_factory=lambda: ["utf-8", "latin-1", "cp1252"])
    max_text_length: int = 1000000  # Max chars to extract
    
    # Format-specific
    pdf_extract_text: bool = True
    pdf_max_pages: int = 0


@dataclass
class MetadataSearchStrategy:
    """Single metadata search strategy."""
    name: str
    description: str
    rule: str


@dataclass
class MetadataConfig:
    """Sidecar metadata handling configuration."""
    enabled: bool = True
    base_paths: List[str] = field(default_factory=lambda: ["."])  # Base directories for sidecar discovery
    search_strategies: List[MetadataSearchStrategy] = field(default_factory=lambda: [
        MetadataSearchStrategy("by_name", "exact filename match", "{basename}.json"),
        MetadataSearchStrategy("in_directory", "any json in same dir", "*.json"),
        MetadataSearchStrategy("in_parent", "parent dir if attachments", "parent_if_attachments"),
    ])
    format: str = "json"  # Only JSON supported currently
    validation_enabled: bool = False


@dataclass
class FilesystemBackendConfig:
    """Filesystem backend configuration."""
    dir_pattern: str = "{doc_id}"
    preserve_extension: bool = True
    create_manifest: bool = True
    manifest_filename: str = "manifest.json"


@dataclass
class OutputConfig:
    """Output/persistence configuration."""
    backend: str = "filesystem"  # filesystem, database, custom
    filesystem: FilesystemBackendConfig = field(default_factory=FilesystemBackendConfig)


@dataclass
class AnalyzerConfig:
    """Analyzer pipeline configuration."""
    enabled: bool = True
    pipeline: List[Dict[str, Any]] = field(default_factory=lambda: [
        {"name": "text_extractor", "enabled": True, "config": {"min_length": 10, "remove_nulls": True}}
    ])
    on_analyzer_error: str = "skip"  # skip, fail_document, fail_all


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    file: Optional[str] = None
    include_timings: bool = False


@dataclass
class IngestConfig:
    """Complete ingestion configuration."""
    input: InputConfig = field(default_factory=InputConfig)
    zip_extraction: ZipExtractionConfig = field(default_factory=ZipExtractionConfig)
    id_generation: IDGenerationConfig = field(default_factory=IDGenerationConfig)
    loader: LoaderConfig = field(default_factory=LoaderConfig)
    metadata: MetadataConfig = field(default_factory=MetadataConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    analyzers: AnalyzerConfig = field(default_factory=AnalyzerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    @classmethod
    def from_yaml(cls, yaml_path: Path) -> IngestConfig:
        """Load configuration from YAML file."""
        yaml_path = Path(yaml_path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {yaml_path}")
        
        log.info(f"Loading ingestion config from {yaml_path}")
        
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)
        
        if not data or "ingest" not in data:
            raise ValueError("YAML must have 'ingest' root key")
        
        return cls.from_dict(data["ingest"])
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> IngestConfig:
        """Load configuration from dictionary."""
        # Normalize and validate
        config = cls()
        
        # Input config
        if "input" in data:
            input_data = data["input"]
            config.input = InputConfig(
                dirs=input_data.get("dirs", config.input.dirs),
                supported_formats=input_data.get("supported_formats", config.input.supported_formats),
                max_depth=input_data.get("max_depth", config.input.max_depth),
                exclude_paths=input_data.get("exclude_paths", config.input.exclude_paths),
            )
            config.input.normalize_formats()
        
        # ZIP extraction
        if "zip_extraction" in data:
            zip_data = data["zip_extraction"]
            config.zip_extraction = ZipExtractionConfig(
                enabled=zip_data.get("enabled", config.zip_extraction.enabled),
                max_archive_depth=zip_data.get("max_archive_depth", config.zip_extraction.max_archive_depth),
                exclude_patterns_in_archive=zip_data.get("exclude_patterns_in_archive", []),
                temp_dir=zip_data.get("temp_dir", config.zip_extraction.temp_dir),
            )
        
        # ID generation
        if "id_generation" in data:
            id_data = data["id_generation"]
            config.id_generation = cls._parse_id_generation_config(id_data)
        
        # Loader
        if "loader" in data:
            loader_data = data["loader"]
            config.loader = LoaderConfig(
                encoding_fallback=loader_data.get("encoding_fallback", config.loader.encoding_fallback),
                max_text_length=loader_data.get("max_text_length", config.loader.max_text_length),
                pdf_extract_text=loader_data.get("pdf", {}).get("extract_text", True),
                pdf_max_pages=loader_data.get("pdf", {}).get("max_pages", 0),
            )
        
        # Metadata
        if "metadata" in data:
            meta_data = data["metadata"]
            strategies = []
            if "search_strategies" in meta_data:
                for strat in meta_data["search_strategies"]:
                    if isinstance(strat, dict):
                        strategies.append(MetadataSearchStrategy(
                            name=strat.get("name", ""),
                            description=strat.get("description", ""),
                            rule=strat.get("rule", ""),
                        ))
            
            config.metadata = MetadataConfig(
                enabled=meta_data.get("enabled", config.metadata.enabled),
                base_paths=meta_data.get("base_paths", config.metadata.base_paths),
                search_strategies=strategies or config.metadata.search_strategies,
                format=meta_data.get("format", config.metadata.format),
                validation_enabled=meta_data.get("validation_enabled", False),
            )
        
        # Output
        if "output" in data:
            output_data = data["output"]
            fs_config = FilesystemBackendConfig()
            if "filesystem" in output_data:
                fs_data = output_data["filesystem"]
                fs_config = FilesystemBackendConfig(
                    dir_pattern=fs_data.get("dir_pattern", fs_config.dir_pattern),
                    preserve_extension=fs_data.get("preserve_extension", fs_config.preserve_extension),
                    create_manifest=fs_data.get("create_manifest", fs_config.create_manifest),
                    manifest_filename=fs_data.get("manifest_filename", fs_config.manifest_filename),
                )
            
            config.output = OutputConfig(
                backend=output_data.get("backend", config.output.backend),
                filesystem=fs_config,
            )
        
        # Analyzers
        if "analyzers" in data:
            analyzer_data = data["analyzers"]
            config.analyzers = AnalyzerConfig(
                enabled=analyzer_data.get("enabled", config.analyzers.enabled),
                pipeline=analyzer_data.get("pipeline", []),
                on_analyzer_error=analyzer_data.get("on_analyzer_error", "skip"),
            )
        
        # Logging
        if "logging" in data:
            log_data = data["logging"]
            config.logging = LoggingConfig(
                level=log_data.get("level", config.logging.level),
                file=log_data.get("file"),
                include_timings=log_data.get("include_timings", False),
            )
        
        cls._validate_id_generation_config(config.id_generation)
        
        return config

    @staticmethod
    def _parse_id_generation_config(id_data: Dict[str, Any]) -> IDGenerationConfig:
        """Parse ID generation settings, supporting both new and legacy keys."""
        strategy = id_data.get("strategy", "sha256-16")
        prefix = id_data.get("prefix", "")
        suffix = id_data.get("suffix", "")

        hash_length_bytes = id_data.get("hash_length_bytes")
        hash_digits = id_data.get("hash_digits")

        naming_strategy = id_data.get("naming_strategy", "hash_only")
        incremental_prefix = id_data.get("incremental_prefix", "DOC")
        incremental_pad_digits = id_data.get("incremental_pad_digits", 6)
        enabled_hash = id_data.get("enabled_hash", True)
        enabled_incremental = id_data.get("enabled_incremental", False)

        # If no explicit limit is provided, derive digit count from legacy strategy.
        if hash_digits is None and hash_length_bytes is None:
            if strategy == "sha256-16":
                hash_digits = 16
            elif strategy == "sha256-32":
                hash_digits = 32

        return IDGenerationConfig(
            strategy=strategy,
            prefix=prefix,
            suffix=suffix,
            hash_length_bytes=hash_length_bytes,
            hash_digits=hash_digits,
            naming_strategy=naming_strategy,
            incremental_prefix=incremental_prefix,
            incremental_pad_digits=incremental_pad_digits,
            enabled_hash=enabled_hash,
            enabled_incremental=enabled_incremental,
        )

    @staticmethod
    def _validate_id_generation_config(config: IDGenerationConfig) -> None:
        def fail(message: str) -> None:
            log.error("Invalid id_generation configuration: %s", message)
            raise InvalidIDGenerationConfig(message)

        # Non-blocking precedence warnings for potentially ambiguous hash sizing config.
        if config.hash_digits is not None and config.hash_length_bytes is not None:
            log.warning(
                "id_generation: both hash_digits and hash_length_bytes are set; "
                "hash_digits takes precedence"
            )
        elif config.hash_digits is not None:
            log.warning(
                "id_generation: hash_digits is set; strategy-derived hash length is overridden"
            )
        elif config.hash_length_bytes is not None:
            log.warning(
                "id_generation: hash_length_bytes is set; strategy-derived hash length is overridden"
            )

        if not isinstance(config.enabled_hash, bool):
            fail("enabled_hash must be a boolean")
        if not isinstance(config.enabled_incremental, bool):
            fail("enabled_incremental must be a boolean")

        if not config.enabled_hash and not config.enabled_incremental:
            fail("both enabled_hash and enabled_incremental are false")

        if config.strategy not in {"sha256-16", "sha256-32"}:
            fail("strategy must be one of: sha256-16, sha256-32")

        if config.hash_length_bytes is not None:
            if not isinstance(config.hash_length_bytes, int):
                fail("hash_length_bytes must be an integer")
            if config.hash_length_bytes < 4 or config.hash_length_bytes > 32:
                fail("hash_length_bytes must be between 4 and 32")

        if config.hash_digits is not None:
            if not isinstance(config.hash_digits, int):
                fail("hash_digits must be an integer")
            if config.hash_digits < 8 or config.hash_digits > 64:
                fail("hash_digits must be between 8 and 64")
            if config.hash_digits % 2 != 0:
                fail("hash_digits must be an even number")

        if not isinstance(config.incremental_pad_digits, int):
            fail("incremental_pad_digits must be an integer")
        if config.incremental_pad_digits < 1 or config.incremental_pad_digits > 10:
            fail("incremental_pad_digits must be between 1 and 10")

        allowed_strategies = {
            "hash_only",
            "incremental_only",
            "hash_then_incremental",
            "incremental_then_hash",
        }
        if config.naming_strategy not in allowed_strategies:
            fail(
                f"Invalid naming_strategy: {config.naming_strategy}. "
                f"Allowed values: {sorted(allowed_strategies)}"
            )

        if config.naming_strategy == "hash_only" and not config.enabled_hash:
            fail("naming_strategy=hash_only requires enabled_hash=true")

        if config.naming_strategy == "incremental_only" and not config.enabled_incremental:
            fail("naming_strategy=incremental_only requires enabled_incremental=true")

        if config.naming_strategy in {"hash_then_incremental", "incremental_then_hash"}:
            if not (config.enabled_hash and config.enabled_incremental):
                fail(
                    f"naming_strategy={config.naming_strategy} requires enabled_hash=true and enabled_incremental=true"
                )
    
    def validate(self) -> List[str]:
        """Validate configuration. Returns list of errors (empty if valid)."""
        errors = []

        try:
            self._validate_id_generation_config(self.id_generation)
        except InvalidIDGenerationConfig as exc:
            errors.append(str(exc))
        
        if self.output.backend not in ["filesystem", "database", "custom"]:
            errors.append(f"Invalid output.backend: {self.output.backend}")

        if self.zip_extraction.temp_dir is not None:
            if not isinstance(self.zip_extraction.temp_dir, str) or not self.zip_extraction.temp_dir.strip():
                errors.append("zip_extraction.temp_dir must be a non-empty string or null")
            else:
                temp_dir_path = Path(self.zip_extraction.temp_dir)
                if temp_dir_path.exists() and not temp_dir_path.is_dir():
                    errors.append("zip_extraction.temp_dir must point to a directory, not a file")
        
        if self.analyzers.on_analyzer_error not in ["skip", "fail_document", "fail_all"]:
            errors.append(f"Invalid analyzers.on_analyzer_error: {self.analyzers.on_analyzer_error}")

        if not isinstance(self.analyzers.pipeline, list):
            errors.append("analyzers.pipeline must be a list")
        else:
            seen_analyzers = set()
            for index, analyzer_entry in enumerate(self.analyzers.pipeline):
                if not isinstance(analyzer_entry, dict):
                    errors.append(f"analyzers.pipeline[{index}] must be a dictionary")
                    continue

                name = analyzer_entry.get("name")
                if not isinstance(name, str) or not name.strip():
                    errors.append(f"analyzers.pipeline[{index}].name must be a non-empty string")
                elif name in seen_analyzers:
                    errors.append(f"Duplicate analyzer name in pipeline: {name}")
                else:
                    seen_analyzers.add(name)

                if "enabled" in analyzer_entry and not isinstance(analyzer_entry["enabled"], bool):
                    errors.append(f"analyzers.pipeline[{index}].enabled must be a boolean")

                if "config" in analyzer_entry and not isinstance(analyzer_entry["config"], dict):
                    errors.append(f"analyzers.pipeline[{index}].config must be a dictionary")
        
        if self.logging.level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            errors.append(f"Invalid logging.level: {self.logging.level}")
        
        return errors

    def set(self, key_path: str, value: Any) -> None:
        """
        Set a config value using dot notation.
        Example: config.set("input.max_depth", 20)
        """
        parts = key_path.split(".")
        obj = self
        
        for part in parts[:-1]:
            obj = getattr(obj, part)
        
        setattr(obj, parts[-1], value)

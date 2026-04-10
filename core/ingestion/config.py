"""
Configuration loading and validation for ingestion module.
Schema is defined in docs/ingest-config-schema.md
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

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


@dataclass
class IDGenerationConfig:
    """Document ID generation configuration."""
    strategy: str = "sha256-16"  # sha256-16, sha256-32, uuid4, custom
    prefix: str = "doc_"
    suffix: str = ""


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
    
    # Artifacts to persist
    artifacts_original_file: bool = True
    artifacts_extracted_text: bool = True
    artifacts_document_metadata: bool = True
    artifacts_sidecar_metadata: bool = True
    artifacts_related_index: bool = True


@dataclass
class AnalyzerConfig:
    """Analyzer pipeline configuration."""
    enabled: bool = True
    html_parsing_enabled: bool = True
    pipeline: List[Dict[str, Any]] = field(default_factory=list)
    on_analyzer_error: str = "skip"  # skip, fail_document, fail_all


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    file: Optional[str] = None
    include_timings: bool = False


@dataclass
class AdvancedConfig:
    """Advanced/performance configuration."""
    temp_dir: Optional[str] = None
    max_files: int = 0
    num_workers: int = 1
    streaming_mode: bool = False


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
    advanced: AdvancedConfig = field(default_factory=AdvancedConfig)
    
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
            )
        
        # ID generation
        if "id_generation" in data:
            id_data = data["id_generation"]
            config.id_generation = IDGenerationConfig(
                strategy=id_data.get("strategy", config.id_generation.strategy),
                prefix=id_data.get("prefix", config.id_generation.prefix),
                suffix=id_data.get("suffix", config.id_generation.suffix),
            )
        
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
            
            artifacts_data = output_data.get("artifacts", {})
            config.output = OutputConfig(
                backend=output_data.get("backend", config.output.backend),
                filesystem=fs_config,
                artifacts_original_file=artifacts_data.get("original_file", True),
                artifacts_extracted_text=artifacts_data.get("extracted_text", True),
                artifacts_document_metadata=artifacts_data.get("document_metadata", True),
                artifacts_sidecar_metadata=artifacts_data.get("sidecar_metadata", True),
                artifacts_related_index=artifacts_data.get("related_index", True),
            )
        
        # Analyzers
        if "analyzers" in data:
            analyzer_data = data["analyzers"]
            config.analyzers = AnalyzerConfig(
                enabled=analyzer_data.get("enabled", config.analyzers.enabled),
                html_parsing_enabled=analyzer_data.get("html_parsing_enabled", config.analyzers.html_parsing_enabled),
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
        
        # Advanced
        if "advanced" in data:
            adv_data = data["advanced"]
            config.advanced = AdvancedConfig(
                temp_dir=adv_data.get("temp_dir"),
                max_files=adv_data.get("max_files", 0),
                num_workers=adv_data.get("num_workers", 1),
                streaming_mode=adv_data.get("streaming_mode", False),
            )
        
        return config
    
    def validate(self) -> List[str]:
        """Validate configuration. Returns list of errors (empty if valid)."""
        errors = []
        
        if self.id_generation.strategy not in ["sha256-16", "sha256-32", "uuid4", "custom"]:
            errors.append(f"Invalid id_generation.strategy: {self.id_generation.strategy}")
        
        if self.output.backend not in ["filesystem", "database", "custom"]:
            errors.append(f"Invalid output.backend: {self.output.backend}")
        
        if self.analyzers.on_analyzer_error not in ["skip", "fail_document", "fail_all"]:
            errors.append(f"Invalid analyzers.on_analyzer_error: {self.analyzers.on_analyzer_error}")

        if not isinstance(self.analyzers.html_parsing_enabled, bool):
            errors.append("analyzers.html_parsing_enabled must be a boolean")

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

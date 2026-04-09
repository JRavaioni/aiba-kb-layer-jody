"""
Pipeline Ingestion Module - Public API

This module provides a complete document ingestion system:
- Filesystem scanning with ZIP support
- Multi-format document loading and text extraction
- Deterministic document ID generation
- Metadata discovery and parsing
- Optional analyzer pipeline
- Pluggable persistence backends
- Configuration-driven behavior
"""

from .config import IngestConfig
from .types import (
    DocumentRef,
    DocumentMetadata,
    IngestedDocument,
    IngestManifest,
    AnalyzerResult,
    IngestException,
    AnalyzerException,
    AnalyzerConfigurationException,
    AnalyzerInputException,
    AnalyzerExecutionException,
    LoadException,
    ScanException,
    PersistenceException,
)
from .ingest_service import IngestService
from .builder import IngestBuilder, create_ingest_service
from .id_generator import (
    IDGenerator,
    IDGeneratorFactory,
    SHA256IDGenerator,
    UUID4IDGenerator,
)
from .backends import (
    PersistenceBackend,
    FilesystemBackend,
    PersistenceBackendFactory,
)
from .analyzers import (
    Analyzer,
    TextExtractorAnalyzer,
    AnalyzerPipeline,
    AnalyzerFactory,
    HtmlParserAnalyzer,
    XmlParserAnalyzer,
    JsonFormatterAnalyzer,
)

__all__ = [
    # Configuration
    "IngestConfig",
    
    # Core types
    "DocumentRef",
    "DocumentMetadata",
    "IngestedDocument",
    "IngestManifest",
    "AnalyzerResult",
    
    # Exceptions
    "IngestException",
    "AnalyzerException",
    "AnalyzerConfigurationException",
    "AnalyzerInputException",
    "AnalyzerExecutionException",
    "LoadException",
    "ScanException",
    "PersistenceException",
    
    # Main service
    "IngestService",
    
    # Builder (recommended way to create service)
    "IngestBuilder",
    "create_ingest_service",
    
    # ID generation
    "IDGenerator",
    "IDGeneratorFactory",
    "SHA256IDGenerator",
    "UUID4IDGenerator",
    
    # Persistence
    "PersistenceBackend",
    "FilesystemBackend",
    "PersistenceBackendFactory",
    
    # Analysis
    "Analyzer",
    "TextExtractorAnalyzer",
    "AnalyzerPipeline",
    "AnalyzerFactory",
    "HtmlParserAnalyzer",
    "XmlParserAnalyzer",
    "JsonFormatterAnalyzer",
]

__version__ = "1.0.0"
__doc__ = """
### Quick Start

```python
from core.ingestion import create_ingest_service
from pathlib import Path

# Create service from config and output directory
service = create_ingest_service(
    config_path="config/ingest.yaml",
    output_dir="output/"
)

# Run ingestion
manifest = service.ingest(
    input_dir="input/",
)

# Check results
print(f"Ingested: {len(manifest.ingested)}")
print(f"Errors: {len(manifest.errors)}")
```

### Key Components

1. **IngestService** - Main orchestrator
2. **IngestBuilder** - Factory for service creation
3. **DocumentScanner** - Filesystem scanning + ZIP extraction
4. **DocumentLoader** - Multi-format text extraction
5. **MetadataLoader** - Sidecar metadata discovery
6. **IDGenerator** - Deterministic ID generation
7. **AnalyzerPipeline** - Optional document processing
8. **PersistenceBackend** - Pluggable storage

### Configuration

All behavior is controlled via YAML configuration:

```yaml
ingest:
  input:
    supported_formats: [pdf, docx, html, txt]
    max_depth: 10
  zip_extraction:
    enabled: true
    max_archive_depth: 3
  id_generation:
    strategy: sha256-16
    prefix: "doc_"
  output:
    backend: filesystem
```

See `docs/ingest-config-schema.md` for complete schema.

### Extending

Register custom implementations:

```python
# Custom ID generator
class MyIDGenerator(IDGenerator):
    def generate(self, file_bytes: bytes) -> str:
        return f"custom_{hash(file_bytes)}"

IDGeneratorFactory.register("custom", MyIDGenerator)

# Custom analyzer
class MyAnalyzer(Analyzer):
    def analyze(self, document: IngestedDocument) -> dict:
        return {"custom": True}

AnalyzerFactory.register("my_analyzer", MyAnalyzer)

# Custom backend
class MyBackend(PersistenceBackend):
    def persist(self, document: IngestedDocument, config):
        pass
    def save_manifest(self, manifest, config):
        pass

PersistenceBackendFactory.register("custom", MyBackend)
```
"""

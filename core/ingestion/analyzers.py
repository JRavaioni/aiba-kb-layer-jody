"""
Analyzer interface and implementations.
Optional processing plugins that enhance ingested documents.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from time import perf_counter
from typing import Dict, Any, cast
import json
import logging

from .types import IngestedDocument
from .types import (
    AnalyzerConfigurationException,
    AnalyzerExecutionException,
    AnalyzerInputException,
    AnalyzerResult,
)
from .config import AnalyzerConfig

log = logging.getLogger(__name__)


class Analyzer(ABC):
    """Base class for document analyzers."""
    
    @abstractmethod
    def analyze(self, document: IngestedDocument) -> AnalyzerResult:
        """
        Analyze a document.
        
        Args:
            document: Document to analyze
        
        Returns:
            Structured analysis result
        
        Raises:
            Exception: If analysis fails
        """
        pass


class TextExtractorAnalyzer(Analyzer):
    """
    Verifies and post-processes text extraction.
    Can validate minimum text lengths, remove nulls, etc.
    """
    
    def __init__(self, config: Dict[str, Any]):
        if not isinstance(config, dict):
            raise AnalyzerConfigurationException(
                "Analyzer config for 'text_extractor' must be a dictionary"
            )

        self.min_length = config.get("min_length", 10)
        self.remove_nulls = config.get("remove_nulls", True)

        if not isinstance(self.min_length, int) or self.min_length < 0:
            raise AnalyzerConfigurationException(
                "Analyzer config 'min_length' must be a non-negative integer"
            )

        if not isinstance(self.remove_nulls, bool):
            raise AnalyzerConfigurationException(
                "Analyzer config 'remove_nulls' must be a boolean"
            )
    
    def analyze(self, document: IngestedDocument) -> AnalyzerResult:
        """
        Validate and process extracted text.
        
        Args:
            document: Document with extracted text
        
        Returns:
            Analysis results
        """
        if not isinstance(document, IngestedDocument):
            raise AnalyzerInputException(
                "TextExtractorAnalyzer expects an IngestedDocument instance"
            )

        payload = {
            "text_length": document.metadata.extracted_text_length,
            "text_valid": False,
            "validation_message": "",
            "null_bytes_removed": 0,
        }
        warnings: list[str] = []
        
        if not document.extracted_text:
            payload["validation_message"] = "No extracted text"
            return AnalyzerResult(
                analyzer_name="text_extractor",
                status="success",
                payload=payload,
                warnings=warnings,
            )
        
        text = document.extracted_text
        
        # Remove null bytes if configured
        if self.remove_nulls:
            null_bytes_removed = text.count("\x00")
            if null_bytes_removed > 0:
                text = text.replace("\x00", "")
                document.extracted_text = text
                payload["null_bytes_removed"] = null_bytes_removed
            payload["text_length"] = len(text)
        
        # Check minimum length
        if len(text) < self.min_length:
            payload["validation_message"] = (
                f"Text length {len(text)} below minimum {self.min_length}"
            )
            return AnalyzerResult(
                analyzer_name="text_extractor",
                status="success",
                payload=payload,
                warnings=warnings,
            )
        
        payload["text_valid"] = True
        payload["validation_message"] = "Text extraction valid"
        
        return AnalyzerResult(
            analyzer_name="text_extractor",
            status="success",
            payload=payload,
            warnings=warnings,
        )


class HtmlParserAnalyzer(Analyzer):
    """Parse raw HTML into readable text for downstream analyzers."""
    # parsing post-ingestion: delete script/style, extract text, strip whitespace
    def __init__(self, config: Dict[str, Any]):
        if not isinstance(config, dict):
            raise AnalyzerConfigurationException(
                "Analyzer config for 'html_parser' must be a dictionary"
            )

        self.remove_scripts = config.get("remove_scripts", True)
        self.strip_whitespace = config.get("strip_whitespace", True)

        if not isinstance(self.remove_scripts, bool):
            raise AnalyzerConfigurationException(
                "Analyzer config 'remove_scripts' must be a boolean"
            )
        if not isinstance(self.strip_whitespace, bool):
            raise AnalyzerConfigurationException(
                "Analyzer config 'strip_whitespace' must be a boolean"
            )

    def analyze(self, document: IngestedDocument) -> AnalyzerResult:
        if document.metadata.format not in ["html", "htm"]:
            return AnalyzerResult(
                analyzer_name="html_parser",
                status="skipped",
                payload={"reason": "format_not_html"},
            )

        if not document.extracted_text:
            return AnalyzerResult(
                analyzer_name="html_parser",
                status="success",
                payload={"text_length": 0, "parsed": False},
                warnings=["No source text to parse"],
            )

        try:
            from bs4 import BeautifulSoup
        except ImportError as e:
            raise AnalyzerExecutionException(f"beautifulsoup4 not installed: {e}")

        soup = BeautifulSoup(document.extracted_text, "html.parser")
        removed_count = 0
        if self.remove_scripts:
            targets = soup.find_all(["script", "style"])
            removed_count = len(targets)
            for node in targets:
                node.decompose()

        parsed_text = soup.get_text()
        if self.strip_whitespace:
            lines = [line.strip() for line in parsed_text.split("\n") if line.strip()]
            parsed_text = "\n".join(lines)

        document.extracted_text = parsed_text.strip() if parsed_text and parsed_text.strip() else None

        return AnalyzerResult(
            analyzer_name="html_parser",
            status="success",
            payload={
                "parsed": True,
                "removed_script_style_count": removed_count,
                "text_length": len(document.extracted_text) if document.extracted_text else 0,
            },
        )


class XmlParserAnalyzer(Analyzer):
    """Parse raw XML into readable text for downstream analyzers."""

    def __init__(self, config: Dict[str, Any]):
        if not isinstance(config, dict):
            raise AnalyzerConfigurationException(
                "Analyzer config for 'xml_parser' must be a dictionary"
            )

        parser_name = config.get("parser", "xml")
        self.parser = parser_name if parser_name in ["xml", "html.parser"] else "xml"
        self.strip_whitespace = config.get("strip_whitespace", True)

        if not isinstance(self.strip_whitespace, bool):
            raise AnalyzerConfigurationException(
                "Analyzer config 'strip_whitespace' must be a boolean"
            )

    def analyze(self, document: IngestedDocument) -> AnalyzerResult:
        if document.metadata.format != "xml":
            return AnalyzerResult(
                analyzer_name="xml_parser",
                status="skipped",
                payload={"reason": "format_not_xml"},
            )

        if not document.extracted_text:
            return AnalyzerResult(
                analyzer_name="xml_parser",
                status="success",
                payload={"text_length": 0, "parsed": False},
                warnings=["No source text to parse"],
            )

        try:
            from bs4 import BeautifulSoup
        except ImportError as e:
            raise AnalyzerExecutionException(f"beautifulsoup4 not installed: {e}")

        soup = BeautifulSoup(document.extracted_text, self.parser)
        parsed_text = soup.get_text()
        if self.strip_whitespace:
            lines = [line.strip() for line in parsed_text.split("\n") if line.strip()]
            parsed_text = "\n".join(lines)

        document.extracted_text = parsed_text.strip() if parsed_text and parsed_text.strip() else None

        return AnalyzerResult(
            analyzer_name="xml_parser",
            status="success",
            payload={
                "parsed": True,
                "text_length": len(document.extracted_text) if document.extracted_text else 0,
            },
        )


class JsonFormatterAnalyzer(Analyzer):
    """Format JSON text to a deterministic pretty-printed representation."""
    # check the format, if not json skip
    # if the json is valid, pretty print it with configured indent (configuration can be find the ingest.yaml file)
    # if the json is invalid, return a warning but do not fail the analyzer
    def __init__(self, config: Dict[str, Any]):
        if not isinstance(config, dict):
            raise AnalyzerConfigurationException(
                "Analyzer config for 'json_formatter' must be a dictionary"
            )

        self.indent = config.get("indent", 2)
        self.ensure_ascii = config.get("ensure_ascii", False)

        if not isinstance(self.indent, int) or self.indent < 0:
            raise AnalyzerConfigurationException(
                "Analyzer config 'indent' must be a non-negative integer"
            )
        if not isinstance(self.ensure_ascii, bool):
            raise AnalyzerConfigurationException(
                "Analyzer config 'ensure_ascii' must be a boolean"
            )

    def analyze(self, document: IngestedDocument) -> AnalyzerResult:
        if document.metadata.format != "json":
            return AnalyzerResult(
                analyzer_name="json_formatter",
                status="skipped",
                payload={"reason": "format_not_json"},
            )

        if not document.extracted_text:
            return AnalyzerResult(
                analyzer_name="json_formatter",
                status="success",
                payload={"formatted": False, "text_length": 0},
                warnings=["No source text to format"],
            )

        try:
            parsed = json.loads(document.extracted_text)
        except json.JSONDecodeError as e:
            return AnalyzerResult(
                analyzer_name="json_formatter",
                status="success",
                payload={"formatted": False, "text_length": len(document.extracted_text)},
                warnings=[f"Invalid JSON source: {e}"],
            )

        formatted = json.dumps(parsed, indent=self.indent, ensure_ascii=self.ensure_ascii)
        document.extracted_text = formatted

        return AnalyzerResult(
            analyzer_name="json_formatter",
            status="success",
            payload={"formatted": True, "text_length": len(formatted)},
        )


class AnalyzerPipeline:
    """
    Executes a pipeline of analyzers in sequence.
    """
    
    def __init__(self, config: AnalyzerConfig):
        self.config = config
        self.analyzers: Dict[str, type[Analyzer] | Analyzer] = {}
        
        # Register built-in analyzers
        self._register_builtin_analyzers()
        self._validate_pipeline_definition()
    
    def _register_builtin_analyzers(self) -> None:
        """Register built-in analyzers."""
        self._register_analyzer("html_parser", HtmlParserAnalyzer)
        self._register_analyzer("xml_parser", XmlParserAnalyzer)
        self._register_analyzer("json_formatter", JsonFormatterAnalyzer)
        self._register_analyzer("text_extractor", TextExtractorAnalyzer)
    
    def _register_analyzer(self, name: str, analyzer_class: type) -> None:
        """Register an analyzer class."""
        # Store class for lazy instantiation
        self.analyzers[name] = analyzer_class

    def _validate_pipeline_definition(self) -> None:
        """Validate analyzer pipeline shape and deterministic keying."""
        if not isinstance(self.config.pipeline, list):
            raise AnalyzerConfigurationException(
                "Analyzer pipeline must be a list of analyzer definitions"
            )

        seen_names: set[str] = set()
        for index, analyzer_config in enumerate(self.config.pipeline):
            if not isinstance(analyzer_config, dict):
                raise AnalyzerConfigurationException(
                    f"Analyzer pipeline entry at index {index} must be a dictionary"
                )

            name = analyzer_config.get("name")
            if not isinstance(name, str) or not name.strip():
                raise AnalyzerConfigurationException(
                    f"Analyzer pipeline entry at index {index} must have a non-empty string 'name'"
                )

            if name in seen_names:
                raise AnalyzerConfigurationException(
                    f"Duplicate analyzer name in pipeline: {name}"
                )
            seen_names.add(name)

            if "enabled" in analyzer_config and not isinstance(analyzer_config["enabled"], bool):
                raise AnalyzerConfigurationException(
                    f"Analyzer '{name}' field 'enabled' must be a boolean"
                )

            if "config" in analyzer_config and not isinstance(analyzer_config["config"], dict):
                raise AnalyzerConfigurationException(
                    f"Analyzer '{name}' field 'config' must be a dictionary"
                )

    @staticmethod
    def _base_metrics(document: IngestedDocument, duration_seconds: float) -> Dict[str, Any]:
        """Create standard observability metrics for analyzer executions."""
        return {
            "duration_seconds": round(duration_seconds, 6),
            "document_id": document.metadata.doc_id,
            "logical_path": document.metadata.logical_path,
            "format": document.metadata.format,
            "extracted_text_length": document.metadata.extracted_text_length,
        }

    @staticmethod
    def _coerce_result(name: str, raw_result: Any) -> AnalyzerResult:
        """Normalize analyzer outputs to AnalyzerResult for backward compatibility."""
        if isinstance(raw_result, AnalyzerResult):
            return raw_result

        if isinstance(raw_result, dict):
            return AnalyzerResult(
                analyzer_name=name,
                status="success",
                payload=raw_result,
            )

        raise AnalyzerExecutionException(
            f"Analyzer '{name}' returned unsupported result type: {type(raw_result).__name__}"
        )
    
    def run(self, document: IngestedDocument) -> Dict[str, Any]:
        """
        Run analyzer pipeline on document.
        
        Args:
            document: Document to analyze
        
        Returns:
            Combined analysis results
        """
        if not self.config.enabled:
            return {}

        if not isinstance(document, IngestedDocument):
            raise AnalyzerInputException("AnalyzerPipeline expects an IngestedDocument instance")
        
        results = {}
        
        for analyzer_config in self.config.pipeline:
            name_value = analyzer_config.get("name")
            if not isinstance(name_value, str):
                raise AnalyzerConfigurationException(
                    "Analyzer pipeline entry missing valid 'name' during execution"
                )
            name = name_value
            enabled = analyzer_config.get("enabled", True)

            # Global switch: allow turning HTML parsing on/off from YAML without
            # editing the pipeline list.
            if name == "html_parser" and not self.config.html_parsing_enabled:
                results[name] = AnalyzerResult(
                    analyzer_name=name,
                    status="skipped",
                    warnings=["HTML parsing disabled by analyzers.html_parsing_enabled=false"],
                    metrics=self._base_metrics(document, 0.0),
                ).to_dict()
                continue
            
            if not enabled:
                results[name] = AnalyzerResult(
                    analyzer_name=name,
                    status="skipped",
                    warnings=["Analyzer disabled by configuration"],
                    metrics=self._base_metrics(document, 0.0),
                ).to_dict()
                continue
            
            if name not in self.analyzers:
                result = AnalyzerResult(
                    analyzer_name=name,
                    status="skipped",
                    warnings=[f"Unknown analyzer: {name}"],
                    metrics=self._base_metrics(document, 0.0),
                )
                results[name] = result.to_dict()
                log.warning(
                    "Unknown analyzer '%s' skipped for document '%s'",
                    name,
                    document.metadata.logical_path,
                )
                continue
            
            started_at = perf_counter()
            try:
                # Instantiate analyzer if it's a class
                analyzer_class = self.analyzers[name]
                if isinstance(analyzer_class, type):
                    analyzer_type = cast(Any, analyzer_class)
                    analyzer = analyzer_type(analyzer_config.get("config", {}))
                else:
                    analyzer = analyzer_class
                
                # Run analyzer
                analyzer_result = self._coerce_result(name, analyzer.analyze(document))
                duration_seconds = perf_counter() - started_at
                analyzer_result.metrics.update(self._base_metrics(document, duration_seconds))
                results[name] = analyzer_result.to_dict()
                
                log.debug(
                    "Analyzer '%s' completed for document '%s' in %.6fs with status '%s'",
                    name,
                    document.metadata.logical_path,
                    duration_seconds,
                    analyzer_result.status,
                )
            
            except Exception as e:
                duration_seconds = perf_counter() - started_at
                if isinstance(e, (AnalyzerConfigurationException, AnalyzerInputException, AnalyzerExecutionException)):
                    analyzer_error = e
                else:
                    analyzer_error = AnalyzerExecutionException(str(e))

                result = AnalyzerResult(
                    analyzer_name=name,
                    status="failed",
                    errors=[str(analyzer_error)],
                    metrics=self._base_metrics(document, duration_seconds),
                )
                results[name] = result.to_dict()

                log.error(
                    "Analyzer '%s' failed for document '%s' in %.6fs: %s",
                    name,
                    document.metadata.logical_path,
                    duration_seconds,
                    analyzer_error,
                )
                
                if self.config.on_analyzer_error == "fail_document":
                    raise analyzer_error
                elif self.config.on_analyzer_error == "fail_all":
                    raise analyzer_error
                # else: skip and continue
        
        return results

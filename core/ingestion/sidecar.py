"""
Sidecar metadata discovery and loading.
Finds and parses metadata files paired with documents.

INGESTION RESPONSIBILITY:
- Sidecar discovery happens during INGESTION phase
- Supports both internal ingestion output and external document directories
- Deterministic metadata association based on configurable base paths
- No business logic interpretation of metadata content
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
import logging
import fnmatch

from .config import MetadataConfig

log = logging.getLogger(__name__)


class MetadataLoader:
    """
    Load metadata from sidecar files paired with documents.
    
    CONFIGURABLE BASE PATHS:
    - Supports internal ingestion output directories
    - Supports external pre-ingested document directories
    - Base paths defined in YAML configuration
    - Deterministic behavior regardless of source
    """
    
    def __init__(self, config: MetadataConfig, base_paths: List[Path]):
        """
        Initialize with configurable base paths.
        
        Args:
            config: Metadata configuration from YAML
            base_paths: List of base directories to search for sidecar files
                       Can include internal ingestion output and external directories
        """
        self.config = config
        self.base_paths = [Path(p) for p in base_paths]
        
        log.info(f"Initialized MetadataLoader with {len(base_paths)} base paths: {[str(p) for p in base_paths]}")
    
    def load(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Discover and load metadata for a document.
        
        Searches all configured base paths using defined strategies.
        First successful match is returned.
        
        Args:
            file_path: Path to document file (may be relative to base paths)
        
        Returns:
            Parsed metadata dict or None if not found
        """
        if not self.config.enabled:
            return None
        
        file_path = Path(file_path)
        
        # Try each base path
        for base_path in self.base_paths:
            metadata = self._load_from_base_path(file_path, base_path)
            if metadata:
                log.debug(f"Loaded metadata for {file_path} from base path {base_path}")
                return metadata
        
        log.debug(f"No metadata found for {file_path} in any base path")
        return None
    
    def _load_from_base_path(self, file_path: Path, base_path: Path) -> Optional[Dict[str, Any]]:
        """
        Load metadata from a specific base path.
        
        Args:
            file_path: Document file path
            base_path: Base directory to search
            
        Returns:
            Parsed metadata or None
        """
        # Determine relative path from base for strategy application
        try:
            if file_path.is_absolute() and file_path.is_relative_to(base_path):
                relative_path = file_path.relative_to(base_path)
                search_dir = base_path
                basename = relative_path.stem
            else:
                # For external documents, use the file's directory
                search_dir = file_path.parent
                basename = file_path.stem
        except ValueError:
            # Paths not related, use file's directory
            search_dir = file_path.parent
            basename = file_path.stem
        
        # Apply search strategies in configured base path
        for strategy in self.config.search_strategies:
            metadata = self._apply_strategy(strategy.rule, basename, search_dir)
            if metadata:
                log.debug(f"Loaded metadata using strategy '{strategy.name}' from {search_dir}")
                return metadata
        
        return None
        
        log.debug(f"No metadata found for {file_path}")
        return None
    
    def _apply_strategy(
        self,
        rule: str,
        basename: str,
        directory: Path,
    ) -> Optional[Dict[str, Any]]:
        """
        Apply a single search strategy.
        
        Args:
            rule: Strategy rule (e.g., "{basename}.json", "*.json", "parent_if_attachments")
            basename: Filename stem
            directory: Directory containing document
        
        Returns:
            Parsed metadata or None
        """
        # Strategy: exact name match
        if rule == "{basename}.json":
            # Try exact match first
            metadata_path = directory / f"{basename}.json"
            metadata = self._parse_json(metadata_path)
            if metadata:
                return metadata
            
            # Try with _metadata suffix (common pattern)
            metadata_path = directory / f"{basename}_metadata.json"
            return self._parse_json(metadata_path)
        
        # Strategy: any file matching pattern
        if rule == "*.json":
            # First try files that contain the basename (more specific matches)
            basename_lower = basename.lower()
            for file_path in directory.glob("*.json"):
                if file_path.is_file():
                    file_stem = file_path.stem.lower()
                    # Check if filename contains basename or vice versa
                    if basename_lower in file_stem or file_stem in basename_lower:
                        metadata = self._parse_json(file_path)
                        if metadata:
                            return metadata
            
            # For *.json strategy, don't fallback to random files
            # Only return metadata if there's a good match
            return None
        
        # Strategy: parent directory if in "attachments" folder
        if rule == "parent_if_attachments":
            if directory.name.lower() == "attachments":
                return self._search_directory(directory.parent, "*.json")
        
        return None
    
    def _search_directory(self, directory: Path, pattern: str) -> Optional[Dict[str, Any]]:
        """
        Search directory for files matching pattern.
        Returns metadata from first JSON found.
        
        Args:
            directory: Directory to search
            pattern: Glob pattern (e.g., "*.json")
        
        Returns:
            Parsed metadata or None
        """
        if not directory.exists():
            return None
        
        try:
            for file_path in directory.glob(pattern):
                if file_path.is_file():
                    metadata = self._parse_json(file_path)
                    if metadata:
                        return metadata
        except Exception as e:
            log.debug(f"Error searching directory {directory}: {e}")
        
        return None
    
    def _parse_json(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Parse JSON metadata file with robust error handling.
        
        Attempts multiple encoding strategies and provides detailed error logging.
        
        Args:
            file_path: Path to JSON file
        
        Returns:
            Parsed dict or None if parsing fails
        """
        if not file_path.exists():
            return None
        
        # Try multiple encodings to handle files with encoding issues
        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]
        
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                    # Try to parse JSON
                    data = json.loads(content)
                    if isinstance(data, dict):
                        if encoding != "utf-8":
                            log.debug(f"Parsed metadata file {file_path} using {encoding} encoding")
                        return data
            except json.JSONDecodeError as e:
                # Continue to next encoding or log after all attempts fail
                continue
            except UnicodeDecodeError:
                # Try next encoding
                continue
            except Exception as e:
                # For other exceptions, try next encoding
                continue
        
        # All encodings and parsing attempts failed - log details
        try:
            # Try to read raw bytes for debugging
            raw_size = file_path.stat().st_size
            log.debug(f"Invalid JSON in metadata file: {file_path} (size: {raw_size} bytes)")
        except Exception:
            log.warning(f"Invalid JSON in metadata file: {file_path}")
        
        return None

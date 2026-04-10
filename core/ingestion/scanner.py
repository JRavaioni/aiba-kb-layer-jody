"""
Document scanning and discovery from filesystem.
Handles recursive traversal, ZIP extraction, and logical path generation.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional
import tempfile
import zipfile
import logging
import shutil
import fnmatch

from .config import InputConfig, ZipExtractionConfig
from .types import DocumentRef, ScanException, ScanResult

log = logging.getLogger(__name__)


@dataclass
class ScanContext:
    """Context for tracking temporary directories created during scanning."""
    temp_dirs: List[Path]
    temp_root_dir: Optional[Path] = None
    _cleaned_up: bool = False  # Track if cleanup has been performed
    
    def cleanup(self) -> None:
        """Remove all temporary directories. Safe to call multiple times."""
        if self._cleaned_up:
            return  # Already cleaned up
        
        self._cleaned_up = True
        for temp_dir in self.temp_dirs:
            try:
                if temp_dir.exists():  # Check if directory still exists
                    shutil.rmtree(temp_dir) # delete the directory
                    log.debug(f"Cleaned up temp directory: {temp_dir}")
                else:
                    log.debug(f"Temp directory already removed: {temp_dir}")
            except Exception as e:
                log.warning(f"Failed to cleanup temp directory {temp_dir}: {e}")


class DocumentScanner:
    """
    Scans filesystem for documents.
    Handles ZIP extraction, exclusion rules, and logical path generation.
    """
    
    def __init__(
        self,
        input_config: InputConfig,
        zip_config: ZipExtractionConfig,
    ):
        self.input_config = input_config 
        self.zip_config = zip_config
        
        # Normalize format list to lowercase
        self.supported_formats = {f.lower() for f in input_config.supported_formats}
    
    def scan(
        self,
        input_dir: Path,
        temp_root_dir: Optional[Path] = None,
    ) -> Iterator[ScanResult]:
        """
        Scan input directory for documents.
        
        Yields named ScanResult items. Caller must cleanup context
        after iteration is complete or when done.
        
        Args:
            input_dir: Root directory to scan
            temp_root_dir: Root for temporary directories (default: system temp)
        
        Yields:
            ScanResult items with explicit context and document fields
        """
        # Scan input directory, if a zip file is found and zip extraction is enabled, it will be extracted in temp directory and scanned recursively.
        input_dir = Path(input_dir)
        if not input_dir.exists():
            raise ScanException(f"Input directory not found: {input_dir}")
        
        ctx = ScanContext(
            temp_dirs=[],
            temp_root_dir=Path(temp_root_dir) if temp_root_dir else None,
        )
        
        try:
            # Use generator to yield documents
            yield from self._scan_recursive(
                input_dir,
                logical_prefix="",
                depth=0,
                archive_depth=0,
                context=ctx,
            )
        except Exception as e:
            ctx.cleanup()
            raise
    
    def _scan_recursive(
        self,
        directory: Path,
        logical_prefix: str,
        depth: int,
        archive_depth: int,
        context: ScanContext,
    ) -> Iterator[ScanResult]:
        """
        Recursively scan directory for documents and ZIPs.
        
        Args:
            directory: Directory to scan
            logical_prefix: Prefix for logical paths (handles zips)
            depth: Current recursion depth
            context: Scan context for cleanup
        """
        if depth > self.input_config.max_depth:
            log.warning(f"Maximum depth {self.input_config.max_depth} reached at {directory}")
            return
        
        try:
            entries = sorted(directory.iterdir())
        except PermissionError:
            log.warning(f"Permission denied scanning {directory}")
            return
        
        for entry in entries:
            # Check exclusions
            if self._is_excluded(entry):
                log.debug(f"Excluded: {entry}")
                continue
            
            if entry.is_dir():
                # Recurse into directories
                logical_prefix_new = (
                    f"{logical_prefix}/{entry.name}" if logical_prefix
                    else entry.name
                )
                yield from self._scan_recursive(
                    entry,
                    logical_prefix_new,
                    depth + 1,
                    archive_depth,
                    context,
                )
            
            elif entry.is_file():
                # Check if it's a ZIP (and ZIP extraction enabled)
                if self.zip_config.enabled and entry.suffix.lower() == ".zip":
                    yield from self._extract_and_scan_zip(
                        entry,
                        logical_prefix,
                        depth,
                        archive_depth,
                        context,
                    )
                else:
                    # Regular document file
                    doc_ref = self._make_document_ref(entry, logical_prefix)
                    if doc_ref:
                        yield ScanResult(context=context, document=doc_ref)
    
    def _extract_and_scan_zip(
        self,
        zip_path: Path,
        logical_prefix: str,
        depth: int,
        archive_depth: int,
        context: ScanContext,
    ) -> Iterator[ScanResult]:
        """
        Extract ZIP and scan its contents.
        
        Args:
            zip_path: Path to ZIP file
            logical_prefix: Prefix for logical paths
            depth: Current recursion depth
            context: Scan context
        """
        zip_basename = zip_path.stem  # filename without .zip
        zip_logical = (
            f"{logical_prefix}/{zip_basename}" if logical_prefix
            else zip_basename
        )
        
        # Check ZIP nesting depth
        next_archive_depth = archive_depth + 1
        if next_archive_depth > self.zip_config.max_archive_depth:
            log.warning(f"ZIP nesting depth exceeded at {zip_path}")
            return
        
        try:
            with tempfile.TemporaryDirectory(
                dir=context.temp_root_dir,
                prefix="ingest_zip_",
            ) as temp_dir:
                temp_path = Path(temp_dir)
                context.temp_dirs.append(temp_path)
                
                log.info(f"Extracting ZIP: {zip_path} → {temp_path}")
                
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(temp_path)
                
                # Recursively scan extracted contents
                yield from self._scan_recursive(
                    temp_path,
                    zip_logical,
                    depth + 1,
                    next_archive_depth,
                    context,
                )
        
        except zipfile.BadZipFile:
            log.error(f"Bad ZIP file: {zip_path}")
        except Exception as e:
            log.error(f"Failed to extract ZIP {zip_path}: {e}")
    
    def _make_document_ref(self, file_path: Path, logical_prefix: str) -> Optional[DocumentRef]:
        """
        Create DocumentRef from file if it's a supported format.
        
        Args:
            file_path: Path to file
            logical_prefix: Prefix for logical path
        
        Returns:
            DocumentRef or None if format not supported
        """
        # reads the file extension and checks if it's in the supported formats list, 
        # if not returns None to skip it. If it is supported, it creates a DocumentRef
        # with the logical path, real path, format, and basename.
        format_str = file_path.suffix.lstrip(".").lower()
        
        if format_str not in self.supported_formats:
            return None
        
        basename = file_path.stem  # filename without extension
        logical_path = (
            f"{logical_prefix}/{file_path.name}" if logical_prefix
            else file_path.name
        )
        
        return DocumentRef(
            logical_path=logical_path,
            real_path=file_path,
            format=format_str,
            basename=basename,
        )
    
    def _is_excluded(self, path: Path) -> bool:
        """
        Check if path should be excluded based on config.
        
        Args:
            path: Path to check
        
        Returns:
            True if path should be excluded
        """
        if not self.input_config.exclude_paths:
            return False
        
        try:
            path_resolved = path.resolve()
        except Exception:
            path_resolved = path
        
        for exclude in self.input_config.exclude_paths:
            try:
                exclude_resolved = Path(exclude).resolve()
            except Exception:
                exclude_resolved = Path(exclude)
            
            # Exact match
            if path_resolved == exclude_resolved:
                return True
            
            # Subtree check (if exclude is a directory)
            if exclude_resolved.is_dir():
                try:
                    path_resolved.relative_to(exclude_resolved)
                    return True
                except ValueError:
                    pass
        
        return False

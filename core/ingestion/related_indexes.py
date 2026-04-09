"""
Related documents indexing for ingestion pipeline.

INGESTION RESPONSIBILITY:
- Related document discovery happens during INGESTION phase
- Identifies relationships between documents based on observable data
- Creates rd_<FULL_DOCUMENT_ID>.json index files
- Relationships must be explainable by ingestion-time observations

ANTI-HALLUCINATION RULE:
- NO invented relationships
- NO fabricated document references
- Relationships must be based on actual data observed during ingestion
- Empty relationship sets are acceptable when no relations exist
"""
from __future__ import annotations
import fnmatch
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import RelationshipsConfig
from .types import IngestedDocument

log = logging.getLogger(__name__)


class RelatedDocumentsIndexer:
    """
    Identifies and indexes relationships between documents.

    INGESTION REQUIREMENT:
    - Finds relationships based on configurable document types and metadata field rules
    - Creates rd_<FULL_DOCUMENT_ID>.json with relationship data
    - Relationships must be observable during ingestion process
    - No downstream semantic analysis or inference

    TWO-PASS DESIGN:
    - Pass 1 (per-document): ``find_related_documents()`` extracts relationship *hints*
      from each document's sidecar metadata using the configured rules.  The hints
      carry a ``related_document_reference`` (e.g. a zip filename) instead of a
      doc_id, because not all documents may have been ingested yet.
    - Pass 2 (post-ingestion): ``resolve_relationships()`` converts those references
      to actual ``related_document_id`` values using the completed manifest.
    """

    def __init__(self, config: RelationshipsConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Pass 1 – per-document hint extraction
    # ------------------------------------------------------------------

    def find_related_documents(self, document: IngestedDocument) -> List[Dict[str, Any]]:
        """
        Find relationship hints for the current document.

        INGESTION CONTRACT:
        - Relationships must be based on data available during ingestion
        - Possible relations: metadata fields referencing other documents by zip name, etc.
        - Returns empty list if no relationships found or relationships are disabled
        - NO invented or inferred relationships

        Args:
            document: Current document being processed

        Returns:
            List of hint dicts::

                [
                    {
                        "related_document_reference": "<zip-filename or other key>",
                        "relationship_type": "attachment_of | related_page | ..."
                    },
                    ...
                ]

            These hints are later resolved to ``related_document_id`` values by
            :meth:`resolve_relationships` once the full manifest is available.
        """
        if not self.config.enabled:
            return []

        relationships: List[Dict[str, Any]] = []

        # The document-type identifier is:
        # - for files extracted from a zip: the zip stem (first path segment)
        #   e.g. "ABCBDT_ATT_0_2D7F280C_0_.../metadata.json" → "ABCBDT_ATT_0_2D7F280C_0_..."
        # - for directly-scanned files: the filename itself
        parts = Path(document.metadata.logical_path).parts
        if not parts:
            log.debug(f"Empty logical path for {document.metadata.doc_id}, skipping relationship detection")
            return []
        identifier = parts[0]  # zip stem or bare filename
        sidecar = document.metadata.sidecar_metadata

        for doc_type in self.config.document_types:
            if not fnmatch.fnmatch(identifier, doc_type.filename_pattern):
                continue

            for rule in doc_type.relationship_rules:
                ref_value = self._get_nested_field(sidecar, rule.metadata_field)
                if ref_value is None:
                    continue

                if isinstance(ref_value, list):
                    for item in ref_value:
                        item_str = str(item).strip() if item else ""
                        if item_str:
                            relationships.append({
                                "related_document_reference": item_str,
                                "relationship_type": rule.relationship_type,
                            })
                else:
                    ref_str = str(ref_value).strip()
                    if ref_str:
                        relationships.append({
                            "related_document_reference": ref_str,
                            "relationship_type": rule.relationship_type,
                        })

            # Stop after the first matching document type so that a document
            # is not processed by multiple overlapping patterns.
            break

        if relationships:
            log.debug(
                f"Found {len(relationships)} relationship hint(s) for "
                f"{document.metadata.doc_id} ({identifier})"
            )
        else:
            log.debug(f"No relationship hints for {document.metadata.doc_id} ({identifier})")

        return relationships

    # ------------------------------------------------------------------
    # Pass 2 – post-ingestion reference resolution
    # ------------------------------------------------------------------

    def resolve_relationships(
        self,
        hints: List[Dict[str, Any]],
        manifest_ingested: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """
        Resolve ``related_document_reference`` values to actual doc IDs.

        A reference value is a zip filename such as
        ``"ABCBDT_ATT_0_1C7C97AC_0_20250708T131023466Z.zip"``.  The resolver
        strips the ``.zip`` extension to obtain the zip stem and then collects
        all doc IDs from the manifest whose logical-path starts with that stem
        (i.e. all files extracted from that zip).  One relationship entry is
        produced per matching doc ID.

        For references that cannot be resolved (the zip was not ingested), the
        original reference is preserved with ``"resolved": false``.

        Args:
            hints: Output of :meth:`find_related_documents` (may already be
                   partially resolved from a previous run).
            manifest_ingested: Mapping of logical_path → doc_id from the manifest.

        Returns:
            List of relationship dicts.  Resolved entries contain::

                {"related_document_id": "<doc_id>", "relationship_type": "..."}

            Unresolved entries retain the original reference::

                {"related_document_reference": "<ref>", "relationship_type": "...",
                 "resolved": false}
        """
        # Build lookup: first-path-segment (zip stem or bare filename) → [doc_id, ...]
        stem_to_doc_ids: Dict[str, List[str]] = {}
        for lp, doc_id in manifest_ingested.items():
            lp_parts = Path(lp).parts
            if not lp_parts:
                continue
            stem = lp_parts[0]
            stem_to_doc_ids.setdefault(stem, []).append(doc_id)

        resolved: List[Dict[str, Any]] = []
        for hint in hints:
            # Skip hints that are already fully resolved (idempotent)
            if "related_document_id" in hint:
                resolved.append(hint)
                continue

            ref = hint.get("related_document_reference", "")
            rel_type = hint.get("relationship_type", "")

            # Derive the zip stem from the reference value:
            # - if it ends with ".zip", strip the extension
            # - otherwise treat the whole value as a stem
            ref_path = Path(ref)
            if ref_path.suffix.lower() == ".zip":
                ref_stem = ref_path.stem
            else:
                ref_stem = ref_path.name

            matching_doc_ids = stem_to_doc_ids.get(ref_stem, [])
            if matching_doc_ids:
                for doc_id in matching_doc_ids:
                    resolved.append({
                        "related_document_id": doc_id,
                        "relationship_type": rel_type,
                    })
            else:
                # Cannot resolve – preserve the reference for downstream use
                resolved.append({
                    "related_document_reference": ref,
                    "relationship_type": rel_type,
                    "resolved": False,
                })

        return resolved

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_nested_field(self, data: Any, field_path: str) -> Optional[Any]:
        """
        Extract a value from a nested dict using dot-path notation.

        Example: ``_get_nested_field(d, "requestBody.zipName")`` is equivalent
        to ``d["requestBody"]["zipName"]`` with safe None returns.

        Args:
            data: Root object (expected to be a dict).
            field_path: Dot-separated path, e.g. ``"requestBody.zipName"``.

        Returns:
            The value at the path, or ``None`` if any segment is missing.
        """
        parts = field_path.split(".")
        current: Any = data
        for part in parts:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
            if current is None:
                return None
        return current

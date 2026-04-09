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
from typing import List, Dict, Any
import logging

from .types import IngestedDocument

log = logging.getLogger(__name__)


class RelatedDocumentsIndexer:
    """
    Identifies and indexes relationships between documents.
    
    INGESTION REQUIREMENT:
    - Finds relationships based on shared metadata, explicit references, etc.
    - Creates rd_<FULL_DOCUMENT_ID>.json with relationship data
    - Relationships must be observable during ingestion process
    - No downstream semantic analysis or inference
    """
    
    def find_related_documents(self, document: IngestedDocument) -> List[Dict[str, Any]]:
        """
        Find documents related to the current document.
        
        INGESTION CONTRACT:
        - Relationships must be based on data available during ingestion
        - Possible relations: shared metadata fields, explicit references
        - Returns empty list if no relationships found
        - NO invented or inferred relationships
        
        Args:
            document: Current document being processed
            
        Returns:
            List of relationship dictionaries with format:
            [
                {
                    "related_document_id": "full_doc_id",
                    "relationship_type": "shared_metadata|explicit_reference|etc"
                },
                ...
            ]
        """
        relationships = []
        
        # INGESTION LIMITATION: At ingestion time, we don't have access to other documents
        # to establish relationships. This indexer serves as a placeholder for future
        # relationship discovery logic that could be implemented based on:
        # - Shared metadata values
        # - Explicit document references in content
        # - File naming patterns
        # - Directory structure relationships
        
        # For now, return empty relationships list
        # This satisfies the requirement of creating rd_*.json files
        # while not inventing relationships
        
        log.debug(f"No relationships found for document {document.metadata.doc_id} (ingestion-time limitation)")
        
        return relationships
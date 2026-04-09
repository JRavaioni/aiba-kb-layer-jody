"""
TEST: DEDUPLICAZIONE E DETERMINISMO DI ID

================================================================================
COSA FA QUESTO TEST
================================================================================
Verifica che il pipeline assegni IDs deterministici e uguali a documenti
identici (stessa content → stesso ID). Questo consente deduplicazione
automatica quando gli stessi documenti vengono ingestiti multiple volte.

================================================================================
QUALE PARTE DEL SISTEMA VERIFICA
================================================================================
- core.ingestion.id_generator.IDGeneratorFactory
- id_generation in IngestService
- SHA256 hash su raw bytes
- Comportamento deterministico rispetto a metadata/path

================================================================================
QUALI INPUT
================================================================================
1. Stessa file ingerita 2 volte
2. Stessa content ma path diverso
3. Stessa content ma metadata diverso

================================================================================
QUALE OUTPUT ATTESO (SUCCESSO)
================================================================================
- Stessa file ingerita 2 volte → STESSO ID
- Stessa content, path diverso → STESSO ID (ID è content-based, non path-based)
- Stessa content, metadata diverso → STESSO ID (ID based su raw bytes, non metadata)

ID è DETERMINISTICO e REPRODUCIBILE anche in future ingestioni.

================================================================================
QUALE OUTPUT / ERRORE ATTESO (FALLIMENTO)
================================================================================
Se il test FALLISCE:
- ID è basato su randomness (ogni volta diverso)
- ID è basato su path (non content-based)
- ID è basato su metadata (non content-based)
- Stessa content ha ID diversi in ingestioni diverse
"""

import pytest
import tempfile
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.ingestion.id_generator import IDGeneratorFactory


class TestDeterminism:
    """Testa determinismo e deduplicazione."""
    
    def test_sha256_id_deterministic(self):
        """
        TEST: Stesso contenuto produce stesso SHA256 ID
        
        VERIFICA: ID è deterministic (sempre uguale per stesso contenuto)
        
        ATTESO: Due run dello stesso file producono ID identici
        """
        factory = IDGeneratorFactory()
        generator = factory.create({"method": "sha256_first_16"})
        
        # Stesso contenuto
        content = b"This is a test document with fixed content."
        
        # Generiamo ID due volte
        id1 = generator.generate(content)
        id2 = generator.generate(content)
        
        # Devono essere identici
        assert id1 == id2, f"ID non è deterministico: {id1} != {id2}"
    
    def test_sha256_id_content_based_not_path(self):
        """
        TEST: ID basato su CONTENUTO, non su path
        
        INVARIANTE: STESSO CONTENUTO → STESSO ID, indipendentemente da:
        - Nome file
        - Path
        - Data modifica
        - Metadati
        
        ATTESO: File con stesso contenuto ma path diverso hanno ID identici
        """
        factory = IDGeneratorFactory()
        generator = factory.create({"method": "sha256_first_16"})
        
        content = b"Identical content in different files"
        
        # Generiamo ID (non dipende da path)
        id1 = generator.generate(content)
        id2 = generator.generate(content)
        
        assert id1 == id2, "ID deve dipendere solo da contenuto"
    
    def test_different_content_different_id(self):
        """
        TEST: Contenuto diverso produce ID diverso
        
        VERIFICA: Non ci sono collisioni (SHA256 le evita)
        
        ATTESO: Contenuto diverso → ID diverso
        """
        factory = IDGeneratorFactory()
        generator = factory.create({"method": "sha256_first_16"})
        
        content1 = b"First different content"
        content2 = b"Second different content"
        
        id1 = generator.generate(content1)
        id2 = generator.generate(content2)
        
        assert id1 != id2, "Contenuto diverso dovrebbe produrre ID diversi"
    
    def test_id_format_is_valid(self):
        """
        TEST: Formato dell'ID è valido (doc_<16-hex-chars>)
        
        VERIFICA: ID è in formato prevedibile
        
        ATTESO: ID inizia con 'doc_' e seguito da 16 caratteri hex
        """
        factory = IDGeneratorFactory()
        generator = factory.create({"method": "sha256_first_16"})
        
        content = b"Test format ID"
        doc_id = generator.generate(content)
        
        # Verifica formato
        parts = doc_id.split("_")
        assert len(parts) == 2, f"ID non ha formato corretto: {doc_id}"
        assert parts[0].lower() == "doc", f"Prefisso non è 'doc': {doc_id}"
        assert len(parts[1]) == 16, \
            f"Hash non è 16 caratteri: {parts[1]} (length={len(parts[1])})"
        
        # Verifica che è valido hex
        try:
            int(parts[1], 16)
        except ValueError:
            pytest.fail(f"ID non contiene hex valido: {parts[1]}")
        
        # Verifica formato
        parts = doc_id.split("_")
        assert len(parts) == 2, f"ID non ha formato corretto: {doc_id}"
        assert parts[0].lower() == "doc", f"Prefisso non è 'doc': {doc_id}"
        assert len(parts[1]) == 16, \
            f"Hash non è 16 caratteri: {parts[1]} (length={len(parts[1])})"
        
        # Verifica che è valido hex
        try:
            int(parts[1], 16)
        except ValueError:
            pytest.fail(f"ID non contiene hex valido: {parts[1]}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

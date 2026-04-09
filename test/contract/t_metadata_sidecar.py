"""
TEST: GESTIONE METADATI E SIDECAR FILES

================================================================================
COSA FA QUESTO TEST
================================================================================
Verifica che il sistema trovi e carichi correttamente file di metadati
"sidecar" (file JSON paired con documenti, stesso basename).

Es: documento.pdf + documento.json → metadati associati

================================================================================
QUALE PARTE DEL SISTEMA VERIFICA
================================================================================
- core.ingestion.sidecar.MetadataLoader
- Scoperta file JSON affiancati
- Parsing JSON metadati
- Integrazione con documento
- Registrazione in output

================================================================================
QUALI INPUT
================================================================================
1. Documento + sidecar JSON valido
2. Documento senza sidecar
3. Documento + sidecar malformato
4. Documento + multipli JSON possibili

================================================================================
QUALE OUTPUT ATTESO (SUCCESSO)
================================================================================
- Documento + sidecar valido → metadati caricati nel manifest
- Documento senza sidecar → metadata=null nel manifest
- Documento + sidecar malformato → metadata=null, log warning
- Documento + multipli JSON → primeiro match appropriato selezionato

================================================================================
QUALE OUTPUT / ERRORE ATTESO (FALLIMENTO)
================================================================================
Se il test FALLISCE:
- Metadata trovato quando non dovrebbe (inventato)
- Metadata non trovato quando dovrebbe (scansione non funziona)
- Documento fallisce ingestione causa metadata invalido (no fail-fast)
"""

import pytest
import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.ingestion.sidecar import MetadataLoader
from core.ingestion.config import MetadataConfig


class TestMetadataSidecar:
    """Testa caricamento metadata sidecar."""
    
    @pytest.fixture
    def metadata_config(self):
        """Configurazione di default per metadata."""
        return MetadataConfig(
            enabled=True,
            base_paths=["."],
            search_strategies=[
                {"name": "exact_match", "rule": "{basename}.json"},
                {"name": "wildcard", "rule": "*.json"}
            ]
        )
    
    def test_find_sidecar_metadata_exact_match(self, metadata_config):
        """
        TEST: File metadata con nome esatto <basename>.json trovato
        
        VERIFICA: estratto e caricato correttamente
        
        ATTESO: Metadata dict caricato dal JSON
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Crea documento
            doc_file = tmpdir / "documento.txt"
            doc_file.write_text("Contenuto documento")
            
            # Crea sidecar metadata
            metadata_file = tmpdir / "documento.json"
            metadata_data = {"autore": "Test User", "data": "2024-01-01"}
            with open(metadata_file, "w") as f:
                json.dump(metadata_data, f)
            
            # Carica metadata
            loader = MetadataLoader(metadata_config, [tmpdir])
            loaded_metadata = loader.load(doc_file)
            
            # Verifica
            assert loaded_metadata is not None, "Metadata non caricato"
            assert loaded_metadata["autore"] == "Test User", "Autore mancante"
            assert loaded_metadata["data"] == "2024-01-01", "Data mancante"
    
    def test_no_sidecar_returns_none(self, metadata_config):
        """
        TEST: Documento senza sidecar metadata
        
        VERIFICA: Ritorna None (non inventato)
        
        ATTESO: metadata = None
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Crea documento SENZA sidecar
            doc_file = tmpdir / "documento_senza_meta.txt"
            doc_file.write_text("Contenuto documento")
            
            # Carica metadata
            loader = MetadataLoader(metadata_config, [tmpdir])
            loaded_metadata = loader.load(doc_file)
            
            # Verifica
            assert loaded_metadata is None, \
                "INVARIANTE VIOLATA: Metadata inventato quando non dovrebbe"
    
    def test_malformed_sidecar_json_fails_gracefully(self, metadata_config):
        """
        TEST: File sidecar JSON malformato (invalid JSON)
        
        VERIFICA: Non crasha loader, ritorna None
        
        ATTESO: metadata = None, logging warning
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Crea documento
            doc_file = tmpdir / "documento.txt"
            doc_file.write_text("Contenuto documento")
            
            # Crea sidecar MALFORMATO
            metadata_file = tmpdir / "documento.json"
            metadata_file.write_text("{invalid json content}")
            
            # Carica metadata
            loader = MetadataLoader(metadata_config, [tmpdir])
            loaded_metadata = loader.load(doc_file)
            
            # Deve ritornare None, non crasha
            assert loaded_metadata is None, \
                "JSON malformato dovrebbe ritornare None, non eccezione"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

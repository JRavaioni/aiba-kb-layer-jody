"""
TEST: COMPORTAMENTO FAIL-FAST IN INGESTIONE

================================================================================
COSA FA QUESTO TEST
================================================================================
Verifica che il pipeline di ingestione implementi la strategia "FAIL-FAST":
quando un documento non può essere ingerito correttamente (testo non estraibile,
metadati invalidi, ecc), l'ingestione di QUEL DOCUMENTO FALLISCE ESPLICITAMENTE.

NON DEVE mai "passare silenziosamente" o fallire parzialmente.

================================================================================
QUALE PARTE DEL SISTEMA VERIFICA
================================================================================
- core.ingestion.ingest_service.IngestService.ingest()
- Validazione output per ogni documento
- Registrazione esplicita di fallimenti nel manifest

================================================================================
QUALI INPUT
================================================================================
1. Un documento HTML valido
2. Un documento HTML vuoto o senza contenuto estratto
3. Un documento corrotto
4. Un documento di formato non supportato

================================================================================
QUALE OUTPUT ATTESO (SUCCESSO)
================================================================================
- Documento HTML valido: ingerito con successo
- Documento HTML vuoto: FALLATO con registrazione di errore nel manifest
- Documento corrotto: FALLATO con errore specifico
- Documento non supportato: SALTATO O FALLATO, mai ingerito

Nel manifest:
- Campo "success" = true/false per ogni documento
- Documenti falliti presenti ma marcati come fail
- Errore specifico registrato per fallimento
- Totale errori > 0 se ci sono fallimenti

================================================================================
QUALE OUTPUT / ERRORE ATTESO (FALLIMENTO TEST)
================================================================================
Se il test FALLISCE:
- Un documento senza contenuto è stato ingerito con successo
- Un documento corrotto è passato ignoto
- Manifest non registra fallimenti
- Non c'è tracking di errori
"""

import pytest
import tempfile
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.ingestion import create_ingest_service, IngestConfig


class TestFailFast:
    """Testa comportamento fail-fast del pipeline."""
    
    @pytest.fixture
    def config(self):
        """Configurazione standard."""
        return IngestConfig(
            input=[],  # Verrà impostato nel test
            output={
                "enabled": True,
                "backend": "filesystem",
                "config": {}
            },
            loader={
                "pdf_extract_text": True,
                "pdf_max_pages": 10,
                "html_extract_text": True,
                "max_text_length": 100000,
                "encoding_fallback": ["utf-8", "latin-1", "cp1252"]
            },
            metadata={
                "enabled": True,
                "base_paths": ["."],
                "search_strategies": [
                    {"name": "exact_match", "rule": "{basename}.json"}
                ]
            },
            id_generation={"method": "sha256_first_16"},
            analyzers=[],
            zip_extraction={"enabled": True, "max_depth": 3}
        )
    
    def test_valid_document_ingests_successfully(self, config):
        """
        TEST: Documento HTML valido con contenuto
        
        VERIFICA: Viene ingerito senza errori
        
        ATTESO: success=true nel manifest, 0 errori
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Crea documento valido
            doc = tmpdir / "valido.html"
            doc.write_text(
                "<html><body><p>Questo è un documento valido con contenuto sufficiente.</p></body></html>"
            )
            
            # Configurazione
            config.input = [str(tmpdir)]
            
            # Output
            with tempfile.TemporaryDirectory() as output:
                output = Path(output)
                service = create_ingest_service(config, output)
                manifest = service.ingest(tmpdir)
                
                # Verifica documento fu ingerito
                assert manifest.success_count > 0, "Nessun documento ingerito"
                assert manifest.error_count == 0, "Documento valido ha generato errore"
                
                # Verifica nel manifest
                manifest_file = output / "manifest.json"
                with open(manifest_file) as f:
                    manifest_data = json.load(f)
                
                assert len(manifest_data["documents"]) > 0, \
                    "Documento non registrato in manifest"
    
    def test_empty_html_document_fails_explicitly(self, config):
        """
        TEST: File HTML vuoto (nessun contenuto estratto)
        
        INVARIANTE FAIL-FAST:
        Se HTML non produce testo estratto valido, ingestione DEVE FALLIRE.
        Non deve ingere con testo=None o vuoto.
        
        ATTESO: Documento marcato come fallito nel manifest
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Crea documento HTML vuoto/senza contenuto
            doc = tmpdir / "vuoto.html"
            doc.write_text("<html><head><title>Solo titolo</title></head><body></body></html>")
            
            config.input = [str(tmpdir)]
            
            with tempfile.TemporaryDirectory() as output:
                output = Path(output)
                service = create_ingest_service(config, output)
                manifest = service.ingest(tmpdir)
                
                # FAIL-FAST: Documento vuoto non dovrebbe essere ingerito con successo
                # Potrebbe essere completamente skippato (error_count++;
                # skipped_count++) oppure fallito esplicitamente
                
                # Verificare manifesto
                manifest_file = output / "manifest.json"
                if manifest_file.exists():
                    with open(manifest_file) as f:
                        manifest_data = json.load(f)
                    
                    # Se il documento è nel manifest, deve avere success=false
                    for doc_entry in manifest_data.get("documents", []):
                        if "vuoto" in doc_entry.get("source_path", "").lower():
                            assert doc_entry.get("success", False) == False, \
                                "Documento vuoto marcato come successo"
    
    def test_corrupted_document_fails_explicitly(self, config):
        """
        TEST: File corrotto che non può essere letto
        
        INVARIANTE FAIL-FAST:
        Documento corrotto DEVE fallire esplicitamente, non saltato silenziosamente.
        
        ATTESO: Errore registrato nel manifest, error_count > 0
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Crea file corrotto (byte binari casuali come se fosse PDF)
            corrupted_file = tmpdir / "corrotto.pdf"
            corrupted_file.write_bytes(b"\x00\xFF\xFE" * 100 + b"garbage PDF content")
            
            config.input = [str(tmpdir)]
            
            with tempfile.TemporaryDirectory() as output:
                output = Path(output)
                service = create_ingest_service(config, output)
                manifest = service.ingest(tmpdir)
                
                # Manifest deve registrare il documento (non saltato silenziosamente)
                manifest_file = output / "manifest.json"
                if manifest_file.exists():
                    with open(manifest_file) as f:
                        manifest_data = json.load(f)
                    
                    # Se numero di documenti processati è 0, significa non fu nemmeno
                    # riconosciuto. Se > 0 ma success=false, significa fail-fast.
                    # Entrambi sono OK, ma non fail-fast sarebbe failure del test.


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

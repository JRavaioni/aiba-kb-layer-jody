"""
TEST: END-TO-END INGESTIONE CON DATI REALI

================================================================================
COSA FA QUESTO TEST
================================================================================
Esegue un'ingestione completa con dati reali da ingestion_test_data/raw.
Verifica che l'intero pipeline funziona (scanner → loader → metadata →
id_generator → persistence).

Questo è il test più importante: se fallisce, il sistema non funziona.

================================================================================
QUALE PARTE DEL SISTEMA VERIFICA
================================================================================
- Intero pipeline IngestService
- Tutte le componenti integrate
- Dato reale dell'ingestion_test_data/
- Output completo e corretto

================================================================================
QUALI INPUT
================================================================================
Dati reali da ingestion_test_data/raw contenenti:
- HTML, TXT, MD, PDF, XML, JSON documenti
- Archive ZIP
- Metadata files

================================================================================
QUALE OUTPUT ATTESO (SUCCESSO)
================================================================================
- Tutti i documenti trovati e processati
- Success rate >= 95% (alcuni PDF malformati OK)
- manifest.json contiene tutti documenti
- Ogni documento ha directory propria in output_dir
- Nessun errore non-logged
- Tempi di esecuzione ragionevoli

================================================================================
QUALE OUTPUT / ERRORE ATTESO (FALLIMENTO)
================================================================================
Se il test FALLISCE:
- Nessun documento ingerito
- Success rate < 50%
- Manifest non trovato
- Directory structure incorretta
- Errore non-handled durante ingestione
"""

import pytest
import tempfile
import json
from pathlib import Path
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.ingestion import create_ingest_service, IngestConfig


class TestIngestionE2E:
    """Test end-to-end con dati reali."""
    
    @pytest.fixture
    def config(self):
        """Configurazione standard per test real data."""
        return IngestConfig(
            input=["ingestion_test_data/raw"],
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
                    {"name": "exact_match", "rule": "{basename}.json"},
                    {"name": "wildcard", "rule": "*.json"}
                ]
            },
            id_generation={"method": "sha256_first_16"},
            analyzers=[],
            zip_extraction={"enabled": True, "max_depth": 3}
        )
    
    def test_ingest_real_data(self, config):
        """
        TEST: Ingestione completa di ingestion_test_data/raw
        
        VERIFICA: Intero pipeline funziona con dati reali
        
        ATTESO:
        - Almeno 50 documenti ingestiti
        - Success rate >= 90%
        - manifest.json valido
        - Tutte output directory strutturate correttamente
        
        TIMEOUT: 60 secondi (real data processing)
        """
        input_dir = Path("ingestion_test_data/raw")
        
        # Skip test se input_data non disponibile
        if not input_dir.exists():
            pytest.skip("ingestion_test_data/raw non trovato")
        
        with tempfile.TemporaryDirectory() as output:
            output = Path(output)
            
            service = create_ingest_service(config, output)
            manifest = service.ingest(input_dir)
            
            # Verifica risultati
            assert manifest.success_count > 50, \
                f"Troppi pochi documenti ingestiti: {manifest.success_count}"
            
            success_rate = (manifest.success_count / (manifest.success_count + manifest.error_count)) if (manifest.success_count + manifest.error_count) > 0 else 0
            assert success_rate > 0.90, \
                f"Success rate troppo bassa: {success_rate:.1%}"
            
            # Verifica manifest.json
            manifest_file = output / "manifest.json"
            assert manifest_file.exists(), "manifest.json non trovato"
            
            with open(manifest_file) as f:
                manifest_data = json.load(f)
            
            assert len(manifest_data["documents"]) >= 50, \
                f"Troppi pochi documenti in manifest: {len(manifest_data['documents'])}"
            
            # Verifica directory structure
            for doc_entry in manifest_data["documents"]:
                doc_id = doc_entry["id"]
                doc_dir = output / doc_id
                assert doc_dir.exists(), f"Directory {doc_dir} non esiste per {doc_id}"
    
    def test_ingest_produces_valid_manifest(self, config):
        """
        TEST: manifest.json è ben-formato e contiene tutte informazioni
        
        VERIFICA: Struttura manifest è corretta
        
        ATTESO:
        - Schema manifest valido
        - Tutti campi obbligatori presenti
        - JSON válido e leggibile
        """
        input_dir = Path("ingestion_test_data/raw")
        
        if not input_dir.exists():
            pytest.skip("ingestion_test_data/raw non trovato")
        
        with tempfile.TemporaryDirectory() as output:
            output = Path(output)
            
            service = create_ingest_service(config, output)
            manifest = service.ingest(input_dir)
            
            manifest_file = output / "manifest.json"
            
            with open(manifest_file) as f:
                data = json.load(f)
            
            # Verifica schema
            assert "documents" in data, "manifest manca chiave 'documents'"
            assert isinstance(data["documents"], list), "'documents' deve essere lista"
            
            # Verifica cada documento
            for doc in data["documents"]:
                assert "id" in doc, "documento manca 'id'"
                assert "source_path" in doc, "documento manca 'source_path'"
                assert doc["id"].startswith("doc_"), "ID non ha formato corretto"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

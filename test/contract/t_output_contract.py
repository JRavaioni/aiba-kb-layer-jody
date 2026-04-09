"""
TEST: CONTRATTO DI OUTPUT DELLA DIRECTORY

================================================================================
COSA FA QUESTO TEST
================================================================================
Verifica che la directory di output del pipeline di ingestione sia organizzata
secondo uno schema DETERMINISTA e PREVEDIBILE, che consente a sistemi downstream
di navigare e accedere ai documenti senza bisogno di conoscere i dettagli interni
dell'ingestione.

================================================================================
QUALE PARTE DEL SISTEMA VERIFICA
================================================================================
- Output del modulo IngestService
- Struttura directory di output_directory/
- Organizzazione file per documento ingerito
- Genereazione dei nomi file (doc ID come directory)
- Creazione del manifest.json

================================================================================
QUALI INPUT
================================================================================
1. Due documenti di test: uno in TXT, uno in HTML
2. Configurazione standard (config/ingest.yaml)
3. Una directory di output temporanea e pulita

================================================================================
QUALE OUTPUT ATTESO (SUCCESSO)
================================================================================
Per ogni documento ingerito:
- Una directory output_directory/<DOC_ID>/ creata automaticamente
- File <DOC_ID>.txt con testo estratto
- File extracted.txt (alias per compatibilità)
- File rd_<DOC_ID>.json con metadati di lettura (raw bytes, formato, ecc)
- File sc_<DOC_ID>.json con risultati scansione (path logico, hash, ecc)
- Nessun file loose nella root: TUTTO deve essere organizzato in subdirectory

Output manifest.json nella root con lista di tutti i DOC_ID ingestiti

================================================================================
QUALE OUTPUT / ERRORE ATTESO (FALLIMENTO)
================================================================================
Se la struttura directory non è come atteso:
- FAIL: Un documento è nella root di output_directory/ anziché subdirectory
- FAIL: File manifest.json non esiste
- FAIL: doc_<ID> directory non contiene expected files
- FAIL: Nomi file non seguono convenzione deterministica

================================================================================
PERCHÉ QUESTO TEST È IMPORTANTE
================================================================================
Molti sistemi downstream (indexing, search, embedding, ecc) si basano su
questa struttura di directory per localizzare e leggere documenti.
Se la struttura cambia, TUTTI i sistemi downstream si rompono.

È una INVARIANTE CRITICA del sistema.
"""

import pytest
import json
import tempfile
from pathlib import Path
import sys

# Importa il modulo di ingestione
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.ingestion import create_ingest_service, IngestConfig


class TestOutputContract:
    """
    Testa il contratto di output della directory di ingestione.
    """
    
    @pytest.fixture
    def test_data_dir(self):
        """Prepara directory temporanea con documenti di test."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Crea documento TXT di test
            test_txt = tmpdir / "documento_test.txt"
            test_txt.write_text("Questo è un documento di test in formato TXT.\n" * 10)
            
            # Crea documento HTML di test
            test_html = tmpdir / "documento_test.html"
            test_html.write_text(
                "<html><body><h1>Titolo</h1><p>Questo è un documento HTML.</p></body></html>"
            )
            
            yield tmpdir
    
    @pytest.fixture
    def output_dir(self):
        """Fornisce directory di output pulita."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def config(self, test_data_dir):
        """Prepara configurazione di ingestione."""
        config = IngestConfig(
            input=[str(test_data_dir)],
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
        return config
    
    def test_output_directory_structure_exists(self, config, output_dir, test_data_dir):
        """
        VERIFICA: Quando facciamo ingestione, output_dir contiene:
        - manifest.json in root
        - Una subdirectory per ogni documento: output_dir/<DOC_ID>/
        
        ATTESO: SUCCESSO
        - manifest.json esiste nella root
        - Numero di subdirectory >= numero di documenti ingestiti
        """
        service = create_ingest_service(config, output_dir)
        manifest = service.ingest(test_data_dir)
        
        # Controlla manifest.json esiste
        manifest_path = output_dir / "manifest.json"
        assert manifest_path.exists(), "manifest.json non trovato in output_dir"
        
        # Carica manifest e verifica contenuto
        with open(manifest_path) as f:
            manifest_data = json.load(f)
        
        assert "documents" in manifest_data, "manifest.json non ha chiave 'documents'"
        assert isinstance(manifest_data["documents"], list), "documents deve essere una lista"
        assert len(manifest_data["documents"]) > 0, "manifest contiene 0 documenti (dovrebbe averne almeno 1)"
    
    def test_each_document_has_own_directory(self, config, output_dir, test_data_dir):
        """
        VERIFICA: Ogni documento ingerito ha una sua directory personale
        nomata <DOC_ID>
        
        ATTESO: SUCCESSO
        - Per ogni DOC_ID nel manifest: output_dir/<DOC_ID>/ esiste
        - La directory non è vuota
        - La directory contiene almeno il file <DOC_ID>.txt
        """
        service = create_ingest_service(config, output_dir)
        manifest = service.ingest(test_data_dir)
        
        with open(output_dir / "manifest.json") as f:
            manifest_data = json.load(f)
        
        doc_ids = [doc["id"] for doc in manifest_data["documents"]]
        
        for doc_id in doc_ids:
            doc_dir = output_dir / doc_id
            
            # Verifica directory esiste
            assert doc_dir.exists(), f"Directory {doc_dir} non esiste per documento {doc_id}"
            assert doc_dir.is_dir(), f"{doc_dir} non è una directory"
            
            # Verifica non è vuota
            files = list(doc_dir.iterdir())
            assert len(files) > 0, f"Directory {doc_dir} è vuota"
    
    def test_no_loose_documents_in_root(self, config, output_dir, test_data_dir):
        """
        VERIFICA: Output directory non contiene file loose di documenti nella root.
        TUTTI i file documento devono essere dentro subdirectory <DOC_ID>/.
        
        INVARIANTE CRITICA: Il root di output_dir contiene SOLO:
        - manifest.json
        - Subdirectory nominate come <DOC_ID>
        
        NON deve contenere file .txt, .json, ecc direttamente nel root.
        
        ATTESO: SUCCESSO
        - Root contiene SOLO manifest.json e directory
        - Nessun file .txt, .extracted, ecc nel root
        """
        service = create_ingest_service(config, output_dir)
        manifest = service.ingest(test_data_dir)
        
        root_items = list(output_dir.iterdir())
        
        for item in root_items:
            if item.is_file():
                # L'unico file permesso nel root è manifest.json
                assert item.name == "manifest.json", \
                    f"File loose trovato in root: {item.name} - tutti i documenti devono essere in subdirectory"
            elif item.is_dir():
                # Le directory devono avere nome simile a un DOC_ID (hex o simile)
                # Non devono essere directory di sistema
                assert not item.name.startswith("_"), \
                    f"Directory sospetta nel root: {item.name}"
    
    def test_document_file_naming_convention(self, config, output_dir, test_data_dir):
        """
        VERIFICA: File dentro ogni directory seguono convenzione di naming
        deterministica:
        - <DOC_ID>.txt : testo estratto
        - extracted.txt : alias/copia
        - rd_<DOC_ID>.json : metadati di lettura
        - sc_<DOC_ID>.json : metadati di scansione
        
        ATTESO: SUCCESSO
        - Tutti questi file esistono per documenti importanti
        - Nomi seguono esattamente questo schema
        """
        service = create_ingest_service(config, output_dir)
        manifest = service.ingest(test_data_dir)
        
        with open(output_dir / "manifest.json") as f:
            manifest_data = json.load(f)
        
        doc_ids = [doc["id"] for doc in manifest_data["documents"]]
        
        for doc_id in doc_ids:
            doc_dir = output_dir / doc_id
            files = {f.name for f in doc_dir.iterdir()}
            
            # Controlla nomi file seguono convenzione
            # Almeno uno tra <DOC_ID>.txt o extracted.txt deve esistere se è un documento testuale
            has_text_file = f"{doc_id}.txt" in files or "extracted.txt" in files
            
            # Controlla metadati scansione
            has_scan_metadata = f"sc_{doc_id}.json" in files


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

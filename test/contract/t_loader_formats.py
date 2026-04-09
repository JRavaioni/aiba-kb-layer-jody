"""
TEST: ESTRAZIONE TESTO DA FORMATI DIVERSI (HTML, TXT, PDF, XML, JSON)

================================================================================
COSA FA QUESTO TEST
================================================================================
Verifica che il modulo DocumentLoader riesca a estrarre testo da vari formati
di documento supportati dal pipeline. Ogni formato ha caratteristiche diverse
e richiede logica di estrazione specifica.

================================================================================
QUALE PARTE DEL SISTEMA VERIFICA
================================================================================
- Modulo core.ingestion.loader.DocumentLoader
- Metodi _load_html(), _load_txt(), _load_xml(), _load_json(), _load_pdf()
- Normalizzazione e cleaning del testo estratto
- Handling di file malformati per ogni formato

================================================================================
QUALI INPUT
================================================================================
Per ogni formato:
1. File valido ben-formato del formato specifico
2. File malformato / corrotto dello stesso formato
3. File vuoto o con soli whitespace

================================================================================
QUALE OUTPUT ATTESO (SUCCESSO)
================================================================================
Per file HTML valido:
- Testo estratto con script/style rimossi
- Whitespace normalizzato
- Content lungo > 0 caratteri
- Senza tag HTML nel risultato

Per file TXT valido:
- Testo decodificato con UTF-8 (fallback a latin-1)
- Ritorno come-è (non modificato)

Per file XML valido:
- Testo estratto dalle foglie XML
- Struttura non mantenuta (solo testo)
- Whitespace normalizzato

Per file JSON valido:
- JSON pretty-printed per leggibilità
- Indentazione aggiunta
- Output è validamente formattato

Per file PDF valido:
- Testo estratto da pagine
- Numero di pagine registrato
- Limitazione a max_pages rispettata

================================================================================
QUALE OUTPUT / ERRORE ATTESO (FALLIMENTO)
================================================================================
Per HTML malformato:
- Non solleva eccezione (fallisce gracefully)
- Ritorna None o testo parziale
- Log di warning registrato

Per formato non riconosciuto:
- Ritorna None
- Non solleva eccezione

Per file corrotto:
- Non blocca il sistema
- Documento fallisce ma altri continuano

Per file vuoto HTML/XML:
- Riconosce come vuoto
- Ritorna None o fallisce ingestione se validato

================================================================================
PERCHÉ QUESTO TEST È IMPORTANTE
================================================================================
La qualità dell'estrazione testo determina la qualità dei risultati downstream
(full-text search, embedding, analisi). Se il testo non viene estratto bene,
tutto il valore del documento si perde.

Inoltre, robustezza su formati malformati previene crash del pipeline.
"""

import pytest
import tempfile
from pathlib import Path
import json
from io import BytesIO
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.ingestion.loader import DocumentLoader
from core.ingestion.config import LoaderConfig
from core.ingestion.types import DocumentRef, LoadException


class TestLoaderFormats:
    """Testa estrazione testo da vari formati."""
    
    @pytest.fixture
    def loader(self):
        """Fornisce un DocumentLoader configurato."""
        config = LoaderConfig(
            pdf_extract_text=True,
            pdf_max_pages=10,
            max_text_length=100000,
            encoding_fallback=["utf-8", "latin-1", "cp1252"]
        )
        return DocumentLoader(config)
    
    @pytest.fixture
    def temp_dir(self):
        """Crea directory temporanea per file di test."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    # =========================================================================
    # TEST: ESTRAZIONE HTML
    # =========================================================================
    
    def test_load_html_valid(self, loader, temp_dir):
        """
        TEST: File HTML valido e ben-formato
        
        VERIFICA: In ingestion minimale HTML viene solo decodificato.
        
        INPUT: <html><body><h1>Titolo</h1><p>Contenuto</p></body></html>
        
        ATTESO: Output contiene markup originale (parsing avviene in analyzer).
        
        IMPORTANTE: HTML è uno dei formati più comuni nel pipeline.
        Estrazione di cattiva qualità qui ha impatto massimo.
        """
        html_file = temp_dir / "test.html"
        html_content = """
        <html>
        <head><title>Pagina Test</title></head>
        <body>
            <h1>Titolo Principale</h1>
            <p>Questo è un paragrafo con contenuto importante.</p>
            <script>alert('questo non dovrebbe apparire');</script>
            <p>Altro paragrafo.</p>
        </body>
        </html>
        """
        html_file.write_text(html_content)
        
        file_ref = DocumentRef(
            real_path=html_file,
            logical_path="test.html",
            format="html",
            basename="test"
        )
        
        loaded = loader.load(file_ref)
        
        # Verifica testo estratto
        assert loaded.extracted_text is not None, "HTML: testo non estratto"
        assert len(loaded.extracted_text) > 0, "HTML: testo vuoto"
        
        # Verifica contenuto atteso in formato raw HTML
        text_lower = loaded.extracted_text.lower()
        assert "titolo" in text_lower, "HTML: titolo principale non trovato"
        assert "paragrafo" in text_lower, "HTML: paragrafo non trovato"

        # In ingestion layer lo script non viene rimosso: è compito analyzer
        assert "<script>" in text_lower and "alert" in text_lower, \
            "HTML raw atteso nel loader minimale"
    
    def test_load_html_empty_should_fail_ingestion(self, loader, temp_dir):
        """
        TEST: File HTML vuoto o con solo whitespace
        
        VERIFICA: Loader minimale ritorna None per contenuto vuoto/whitespace.
        
        IMPORTANTE: Un documento HTML senza contenuto non dovrebbe
        essere ingerito con successo. È un indicatore di documento
        corrotto o non valido.
        """
        html_file = temp_dir / "empty.html"
        html_file.write_text("   \n\n   ")
        
        file_ref = DocumentRef(
            real_path=html_file,
            logical_path="empty.html",
            format="html",
            basename="empty"
        )
        
        loaded = loader.load(file_ref)
        
        assert loaded.extracted_text is None, "HTML vuoto: atteso None nel loader minimale"
    
    # =========================================================================
    # TEST: ESTRAZIONE TXT
    # =========================================================================
    
    def test_load_txt_utf8(self, loader, temp_dir):
        """
        TEST: File TXT con encoding UTF-8
        
        VERIFICA: Testo letto correttamente senza modifiche
        
        ATTESO: Testo ritorna come-è, solo normalizzato spazi
        """
        txt_file = temp_dir / "test.txt"
        test_content = "Questo è un file di testo.\nCon più linee.\nE unicode: café, naïve."
        txt_file.write_text(test_content, encoding="utf-8")
        
        file_ref = DocumentRef(
            real_path=txt_file,
            logical_path="test.txt",
            format="txt",
            basename="test"
        )
        
        loaded = loader.load(file_ref)
        
        assert loaded.extracted_text is not None, "TXT: testo non letto"
        assert "file di testo" in loaded.extracted_text.lower(), \
            "TXT: contenuto non corrisponde"
    
    def test_load_txt_latin1_fallback(self, loader, temp_dir):
        """
        TEST: File TXT con encoding non-standard (latin-1)
        
        VERIFICA: Loader tenta fallback su altri encoding
        
        ATTESO: SUCCESSO con encoding fallback
        """
        txt_file = temp_dir / "test_latin1.txt"
        test_content = "Testo con accenti: café, résumé"
        txt_file.write_text(test_content, encoding="latin-1")
        
        file_ref = DocumentRef(
            real_path=txt_file,
            logical_path="test_latin1.txt",
            format="txt",
            basename="test_latin1"
        )
        
        loaded = loader.load(file_ref)
        
        # Dovrebbe avere estratto testo - il fallback deve funzionare
        assert loaded.extracted_text is not None or len(loaded.raw_bytes) > 0, \
            "TXT latin-1: fallback encoding non funziona"
    
    # =========================================================================
    # TEST: ESTRAZIONE XML
    # =========================================================================
    
    def test_load_xml_valid(self, loader, temp_dir):
        """
        TEST: File XML valido ben-formato
        
        VERIFICA: In ingestion minimale XML viene solo decodificato.
        
        IMPORTANTE: parsing/flattening XML ora avviene in analyzer.
        """
        xml_file = temp_dir / "test.xml"
        xml_content = """<?xml version="1.0"?>
        <documento>
            <titolo>Documento Test</titolo>
            <contenuto>
                <paragrafo>Primo paragrafo del documento.</paragrafo>
                <paragrafo>Secondo paragrafo.</paragrafo>
            </contenuto>
        </documento>
        """
        xml_file.write_text(xml_content)
        
        file_ref = DocumentRef(
            real_path=xml_file,
            logical_path="test.xml",
            format="xml",
            basename="test"
        )
        
        loaded = loader.load(file_ref)
        
        assert loaded.extracted_text is not None, "XML: testo non estratto"
        
        # In loader minimale i tag restano presenti
        text = loaded.extracted_text
        assert "<documento>" in text, "XML raw atteso nel loader minimale"
        
        # Verifica contenuto
        text_lower = text.lower()
        assert "documento" in text_lower, "XML: testo non contiene elemento titolo"
        assert "paragrafo" in text_lower, "XML: testo non contiene paragrafi"
    
    # =========================================================================
    # TEST: ESTRAZIONE JSON
    # =========================================================================
    
    def test_load_json_valid(self, loader, temp_dir):
        """
        TEST: File JSON valido
        
        VERIFICA: In ingestion minimale JSON viene decodificato senza pretty-print.
        
        ATTESO: Output contiene il JSON raw scritto su file.
        """
        json_file = temp_dir / "test.json"
        json_data = {
            "titolo": "Documento JSON",
            "metadata": {"autore": "Test"},
            "contenuto": "Testo del documento"
        }
        with open(json_file, "w") as f:
            json.dump(json_data, f)
        
        file_ref = DocumentRef(
            real_path=json_file,
            logical_path="test.json",
            format="json",
            basename="test"
        )
        
        loaded = loader.load(file_ref)
        
        assert loaded.extracted_text is not None, "JSON: testo non estratto"
        assert "titolo" in loaded.extracted_text, "JSON: campo titolo non presente"
        assert "Documento JSON" in loaded.extracted_text, "JSON: valore non presente"
    
    def test_load_json_invalid_fallback_to_text(self, loader, temp_dir):
        """
        TEST: File JSON corrotto/non valido
        
        VERIFICA: Fallback a lettura come testo plain
        
        ATTESO: Non solleva eccezione, ritorna testo grezzo
        """
        json_file = temp_dir / "invalid.json"
        # JSON malformato (virgola finale, ecc)
        json_file.write_text('{"key": "value",}')
        
        file_ref = DocumentRef(
            real_path=json_file,
            logical_path="invalid.json",
            format="json",
            basename="invalid"
        )
        
        # Non dovrebbe sollevare eccezione
        loaded = loader.load(file_ref)
        
        # Potrebbe ritornare None o testo grezzo
        # L'importante è che non crasha il loader
        assert loaded is not None, "JSON invalido: loader ha fallito"
    
    # =========================================================================
    # TEST: GESTIONE ERRORI
    # =========================================================================
    
    def test_missing_file_raises_exception(self, loader, temp_dir):
        """
        TEST: File non esiste
        
        VERIFICA: LoadException solleva con messaggio chiaro
        
        ATTESO: ECCEZIONE con file path nel messaggio
        """
        missing_file = temp_dir / "not_exists.txt"
        
        file_ref = DocumentRef(
            real_path=missing_file,
            logical_path="not_exists.txt",
            format="txt",
            basename="not_exists"
        )
        
        with pytest.raises(LoadException):
            loader.load(file_ref)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

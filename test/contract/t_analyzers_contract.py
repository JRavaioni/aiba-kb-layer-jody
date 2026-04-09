"""
TEST: CONTRATTO DEGLI ANALYZER

================================================================================
COSA FA QUESTO TEST
================================================================================
Verifica il contratto runtime della pipeline analyzer:
- output strutturato e serializzabile
- validazione configurazione analyzer
- gestione errori tipizzata
- comportamento deterministico dei nomi analyzer
- osservabilità minima (metriche e stato)

================================================================================
QUALE PARTE DEL SISTEMA VERIFICA
================================================================================
- core.ingestion.analyzers.AnalyzerPipeline
- core.ingestion.analyzers.TextExtractorAnalyzer
- core.ingestion.types.AnalyzerResult
- validazione config in core.ingestion.config.IngestConfig

================================================================================
QUALI INPUT UTILIZZA
================================================================================
- documenti fittizi costruiti come IngestedDocument
- configurazioni analyzer valide e invalide
- testo con null byte e testo troppo corto

================================================================================
QUALE OUTPUT È ATTESO IN CASO DI SUCCESSO
================================================================================
- ogni analyzer produce un dict con: analyzer_name, status, payload, warnings,
  errors, metrics
- configurazioni invalide vengono rifiutate con eccezione esplicita
- pipeline con nomi duplicati viene rifiutata
- le metriche minime sono sempre presenti

================================================================================
QUALE OUTPUT / ERRORE È ATTESO IN CASO DI FALLIMENTO
================================================================================
- se manca il contratto strutturato, il test fallisce
- se config invalida passa silenziosamente, il test fallisce
- se duplicate analyzer names vengono accettati, il test fallisce

================================================================================
PERCHÉ QUESTO TEST È IMPORTANTE
================================================================================
Gli analyzer sono un punto di estensione del sistema. Se il loro contratto è
ambiguo o fragile, la pipeline perde affidabilità, tracciabilità e capacità di
manutenzione.
"""

import pytest
from datetime import datetime, UTC
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.analyzers import AnalyzerPipeline, TextExtractorAnalyzer
from core.ingestion.config import AnalyzerConfig, IngestConfig
from core.ingestion.types import (
    AnalyzerConfigurationException,
    DocumentMetadata,
    IngestedDocument,
)


class TestAnalyzersContract:
    """Verifica il contratto runtime della pipeline analyzer."""

    @staticmethod
    def _document(text: str = "Testo valido per analyzer") -> IngestedDocument:
        metadata = DocumentMetadata(
            doc_id="doc_test1234567890",
            logical_path="documents/test.txt",
            basename="test",
            format="txt",
            extracted_text_length=len(text),
            source_file_size=len(text.encode("utf-8")),
            ingested_at=datetime.now(UTC),
        )
        return IngestedDocument(
            metadata=metadata,
            raw_bytes=text.encode("utf-8"),
            extracted_text=text,
        )

    def test_pipeline_returns_structured_analyzer_result(self):
        """
        VERIFICA: l'output analyzer è strutturato e contiene campi osservabili.
        """
        pipeline = AnalyzerPipeline(
            AnalyzerConfig(
                enabled=True,
                pipeline=[
                    {
                        "name": "text_extractor",
                        "enabled": True,
                        "config": {"min_length": 5, "remove_nulls": True},
                    }
                ],
                on_analyzer_error="skip",
            )
        )

        result = pipeline.run(self._document("testo con contenuto sufficiente"))

        assert "text_extractor" in result
        analyzer_result = result["text_extractor"]
        assert analyzer_result["analyzer_name"] == "text_extractor"
        assert analyzer_result["status"] == "success"
        assert "payload" in analyzer_result
        assert "warnings" in analyzer_result
        assert "errors" in analyzer_result
        assert "metrics" in analyzer_result
        assert "duration_seconds" in analyzer_result["metrics"]
        assert analyzer_result["metrics"]["logical_path"] == "documents/test.txt"

    def test_text_extractor_config_validation_is_explicit(self):
        """
        VERIFICA: configurazioni invalide non sono accettate silenziosamente.
        """
        with pytest.raises(AnalyzerConfigurationException):
            TextExtractorAnalyzer({"min_length": "10", "remove_nulls": True})

        with pytest.raises(AnalyzerConfigurationException):
            TextExtractorAnalyzer({"min_length": 10, "remove_nulls": "yes"})

    def test_duplicate_analyzer_names_are_rejected(self):
        """
        VERIFICA: nomi duplicati non sono ammessi perché il risultato finale è
        indicizzato per nome analyzer.
        """
        config = IngestConfig.from_dict(
            {
                "analyzers": {
                    "enabled": True,
                    "pipeline": [
                        {"name": "text_extractor", "enabled": True, "config": {}},
                        {"name": "text_extractor", "enabled": True, "config": {}},
                    ],
                    "on_analyzer_error": "skip",
                }
            }
        )

        errors = config.validate()
        assert any("Duplicate analyzer name in pipeline: text_extractor" in error for error in errors)

    def test_text_extractor_is_idempotent_for_null_removal(self):
        """
        VERIFICA: eseguire due volte lo stesso analyzer non degrada il testo.
        """
        analyzer = TextExtractorAnalyzer({"min_length": 1, "remove_nulls": True})
        document = self._document("abc\x00def")
        document.metadata.extracted_text_length = len(document.extracted_text or "")

        first = analyzer.analyze(document)
        document.metadata.extracted_text_length = len(document.extracted_text or "")
        second = analyzer.analyze(document)

        assert first.payload["null_bytes_removed"] == 1
        assert second.payload["null_bytes_removed"] == 0
        assert document.extracted_text == "abcdef"

    def test_unknown_analyzer_is_reported_as_skipped(self):
        """
        VERIFICA: analyzer sconosciuto non genera output ambiguo.
        """
        pipeline = AnalyzerPipeline(
            AnalyzerConfig(
                enabled=True,
                pipeline=[
                    {"name": "unknown_analyzer", "enabled": True, "config": {}}
                ],
                on_analyzer_error="skip",
            )
        )

        result = pipeline.run(self._document())
        analyzer_result = result["unknown_analyzer"]
        assert analyzer_result["status"] == "skipped"
        assert analyzer_result["warnings"]
        assert analyzer_result["errors"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

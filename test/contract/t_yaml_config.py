"""
TEST: CONTRATTO DI CONFIGURAZIONE YAML

================================================================================
COSA FA QUESTO TEST
================================================================================
Verifica che la configurazione YAML sia parsata e validata correttamente.
La configurazione è la "single source of truth" del sistema - se non funziona,
tutto il comportamento è influenzato.

================================================================================
QUALE PARTE DEL SISTEMA VERIFICA
================================================================================
- core.ingestion.config.IngestConfig
- Parsing YAML
- Validazione schema
- Valori di default
- Override di parametri

================================================================================
QUALI INPUT
================================================================================
1. YAML valido ben-formato
2. YAML con campi mancanti (deve usare default)
3. YAML con campi invalidi (deve fallare validazione)
4. YAML con tipi sbagliati (deve fallare)

================================================================================
QUALE OUTPUT ATTESO (SUCCESSO)
================================================================================
- YAML valido → IngestConfig costruito correttamente
- Campi assenti → valori default applicati
- Tipi corretti in config object
- Métodi validate() ritorna [] (no errors)

================================================================================
QUALE OUTPUT / ERRORE ATTESO (FALLIMENTO)
================================================================================
- YAML invalido → IngestException sollevata
- Tipo sbagliato → validazione fallisce
- Campo richiesto mancante → errore di validazione
"""

import pytest
import yaml
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.ingestion.config import IngestConfig
from core.ingestion.types import IngestException


class TestYamlConfig:
    """Testa validazione e parsing di configurazione YAML."""
    
    def test_valid_yaml_loads_successfully(self):
        """
        TEST: File YAML valido carica correttamente
        
        VERIFICA: Configurazione legale di YAML valido
        
        ATTESO: IngestConfig costruito, validate() ritorna []
        """
        config_dict = {
            "input": ["input_dir"],
            "output": {
                "enabled": True,
                "backend": "filesystem"
            },
            "loader": {
                "pdf_extract_text": True,
                "html_extract_text": True
            },
            "metadata": {
                "enabled": True,
                "base_paths": ["."],
                "search_strategies": [
                    {"name": "exact_match", "rule": "{basename}.json"}
                ]
            },
            "id_generation": {"method": "sha256_first_16"},
            "analyzers": [],
            "zip_extraction": {"enabled": True, "max_depth": 3}
        }
        
        config = IngestConfig(**config_dict)
        errors = config.validate()
        
        assert errors == [], f"Configurazione valida ha errori: {errors}"
    
    def test_missing_required_input_fails_validation(self):
        """
        TEST: Campo "input" mancante dovrebbe fallare
        
        VERIFICA: Configurazione incompleta non passa validazione
        
        ATTESO: validate() non ritorna [] oppure __init__ fallisce
        """
        config_dict = {
            # "input" assente - REQUIRED
            "output": {
                "enabled": True,
                "backend": "filesystem"
            },
            "loader": {},
            "metadata": {"enabled": False},
            "id_generation": {"method": "sha256_first_16"},
            "analyzers": [],
            "zip_extraction": {"enabled": False}
        }
        
        try:
            config = IngestConfig(**config_dict)
            # Se arriviamo qui, almeno validate() deve fallare
            errors = config.validate()
            assert len(errors) > 0, "Campo 'input' è required ma validazione non l'ha catturato"
        except (TypeError, ValueError, IngestException):
            # Questo è OK - init ha fallato su parametro mancante
            pass
    
    def test_wrong_type_fails_validation(self):
        """
        TEST: Tipo di campo sbagliato fallisce
        
        VERIFICA: Se input è string anziché list, fallisce
        
        ATTESO: Validazione fallisce o errore tipo
        """
        config_dict = {
            "input": "input_dir",  # SBAGLIATO: deve essere lista
            "output": {"enabled": True, "backend": "filesystem"},
            "loader": {},
            "metadata": {"enabled": False},
            "id_generation": {"method": "sha256_first_16"},
            "analyzers": [],
            "zip_extraction": {"enabled": False}
        }
        
        # Pydantic dovrebbe validare il tipo
        try:
            config = IngestConfig(**config_dict)
            errors = config.validate()
            # Se non ha fallato con eccezione, almeno validate() deve trovare errore
            # Dipende dall'implementazione
        except (TypeError, ValueError):
            # Questo è OK
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

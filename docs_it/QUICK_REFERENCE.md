# Guida di Riferimento Rapido

## Avvio Rapido (5 minuti)

### 1. Configura
Modifica `config/ingest.yaml` per definire le cartelle di input:

```yaml
ingest:
  input:
    dirs:
      - "ingestion_test_data/raw"  # La tua cartella di input
```

### 2. Avvia
```python
from core.ingestion import create_ingest_service

service = create_ingest_service("config/ingest.yaml", "output/")
manifest = service.ingest("input/")

print(f"Ingestiti: {manifest.success_rate:.1f}%")
```

### 3. Risultati
```
output/
  manifest.json
  b784e2c8dbba8d15/           # Directory per documento - ID COMPLETO
    b784e2c8dbba8d15.html     # File originale - ID COMPLETO come nome file
    sc_b784e2c8dbba8d15.json  # Metadati sidecar - prefisso sc_
    rd_b784e2c8dbba8d15.json  # Documenti correlati - prefisso rd_
```

---

## Compiti Comuni

### Estrai Testo da PDF/DOC
```yaml
ingest:
  input:
    supported_formats: [pdf, docx, doc]
  loader:
    pdf:
      extract_text: true
    docx:
      extract_text: true
```

### Estrai da ZIP
```yaml
ingest:
  zip_extraction:
    enabled: true
    max_archive_depth: 3
```

### Carica Metadati Accoppiati
```yaml
ingest:
  metadata:
    enabled: true
    search_strategies:
      - name: by_name
        rule: "{basename}.json"
```

### Usa Formato ID Personalizzato
```yaml
ingest:
  id_generation:
    strategy: sha256-16
    prefix: "my_id_"
    suffix: "_v1"
```

### Disabilita Caratteristiche
```yaml
ingest:
  zip_extraction:
    enabled: false
  metadata:
    enabled: false
  analyzers:
    enabled: false
```

### Aggiungi Validazione Testo
```yaml
ingest:
  analyzers:
    pipeline:
      - name: text_extractor
        enabled: true
        config:
          min_length: 100
          remove_nulls: true
```

---

## Notazione Punto Configurazione

```python
from core.ingestion import IngestBuilder

builder = IngestBuilder.from_config("config/ingest.yaml")
builder.set("input.max_depth", 20)
builder.set("loader.max_text_length", 500000)
builder.set("output.backend", "filesystem")
service = builder.build()
```

---

## Gestione Errori

```python
from core.ingestion import create_ingest_service

service = create_ingest_service("config/ingest.yaml", "output/")
manifest = service.ingest("input/")

# Verifica risultati
if manifest.errors:
    for path, error in manifest.errors.items():
        print(f"FALLITO: {path} - {error}")

# Verifica tasso successo
print(f"Successo: {manifest.success_rate:.1f}%")
```

---

## Estendi con Generatore ID Personalizzato

```python
from core.ingestion import IDGenerator, IDGeneratorFactory, IngestBuilder

class GeneratoreIDCompany(IDGenerator):
    def generate(self, file_bytes: bytes) -> str:
        import hashlib
        h = hashlib.sha1(file_bytes).hexdigest()[:8]
        return f"COMPANY_{h}"

IDGeneratorFactory.register("company", GeneratoreIDCompany)

# Usa in config
config = {
    "ingest": {
        "id_generation": {"strategy": "company"}
    }
}
service = IngestBuilder.from_dict(config).with_output_dir("output/").build()
```

---

## Estendi con Analizzatore Personalizzato

```python
from core.ingestion import Analyzer, AnalyzerFactory, IngestBuilder

class EstrattoreEntità(Analyzer):
    def analyze(self, document):
        # La tua logica qui
        return {"entità": ["PERSONA", "ORG"]}

AnalyzerFactory.register("entità", EstrattoreEntità)

# Usa in config
config = {
    "ingest": {
        "analyzers": {
            "pipeline": [
                {"name": "entità", "enabled": True, "config": {}}
            ]
        }
    }
}
service = IngestBuilder.from_dict(config).with_output_dir("output/").build()
```

---

## Elabora Batch Grandi

```python
from core.ingestion import create_ingest_service
import os

# Dividi input in batch
input_dirs = ["batch_001/", "batch_002/", "batch_003/"]

for batch_dir in input_dirs:
    service = create_ingest_service("config/ingest.yaml", f"output/{batch_dir}")
    manifest = service.ingest(batch_dir)
    print(f"{batch_dir}: {manifest.success_rate:.1f}%")
```

---

## Debug Configurazione

```yaml
ingest:
  logging:
    level: DEBUG
    file: logs/ingest.log
    include_timings: true
```

---

## Testa la Tua Configurazione

```python
from core.ingestion import IngestConfig

config = IngestConfig.from_yaml("config/ingest.yaml")
errors = config.validate()

if errors:
    print("Errori configurazione:")
    for error in errors:
        print(f"  - {error}")
else:
    print("Configurazione valida!")
```

---

## Formati Supportati Predefiniti

- ✅ PDF (estrazione testo)
- ✅ DOCX (estrazione testo nativa)
- ✅ DOC (supporto conversione)
- ✅ HTML/HTM (BeautifulSoup)
- ✅ TXT (testo semplice)
- ✅ ZIP (estrazione ricorsiva)

---

## Ricerca Metadati Predefinita

1. **Per Nome**: `document.pdf` → `document.json`
2. **In Directory**: Qualsiasi file `.json` nella stessa cartella
3. **In Padre**: Directory padre se cartella corrente è "attachments"

---

## Struttura Manifest Output

```json
{
  "ingested": {
    "path/to/file.pdf": "b784e2c8dbba8d15",
    "path/to/file2.docx": "xyz123..."
  },
  "errors": {
    "bad_file.pdf": "Impossibile estrarre testo"
  },
  "summary": {
    "total_input": 100,
    "successfully_ingested": 98,
    "failed": 2,
    "duplicates_found": 0,
    "success_rate": 98.0
  },
  "timestamps": {
    "started_at": "2024-01-15T10:00:00.000000",
    "completed_at": "2024-01-15T10:05:30.000000",
    "duration_seconds": 330
  }
}
```

---

## Struttura Metadati Documento

```json
{
  "doc_id": "b784e2c8dbba8d15",
  "logical_path": "subfolder/file.pdf",
  "basename": "file",
  "format": "pdf",
  "extracted_text_length": 45230,
  "pages_count": 12,
  "source_file_hash": "a1b2c3dbba8d15...",
  "source_file_size": 1024000,
  "ingested_at": "2024-01-15T10:00:30.123456",
  "sidecar_metadata": { "campo_personalizzato": "valore" },
  "analyzer_output": {
    "text_extractor": {
      "analyzer_name": "text_extractor",
      "status": "success",
      "payload": { "text_valid": true },
      "warnings": [],
      "errors": [],
      "metrics": {
        "duration_seconds": 0.000123,
        "document_id": "doc_a1b2c3d4",
        "logical_path": "subfolder/file.pdf",
        "format": "pdf",
        "extracted_text_length": 45230
      }
    }
  }
}
```

---

## File da Conoscere

| File | Scopo |
|------|---------|
| `config/ingest.yaml` | Configurazione principale |
| `core/ingestion/__init__.py` | API pubblica |
| `core/ingestion/builder.py` | Crea servizio |
| `core/ingestion/scanner.py` | Trova documenti |
| `core/ingestion/loader.py` | Estrae testo |
| `core/ingestion/sidecar.py` | Carica metadati |
| `docs/ingest-config-schema.md` | Riferimento configurazione |
| `docs/architecture.md` | Dettagli design |
| `docs/examples.md` | Esempi codice |

---

## Aiuto & Documentazione

```
Avvio Rapido    → README.md
Configurazione → docs/ingest-config-schema.md
Architettura  → docs/architecture.md
Esempi        → docs/examples.md
Riferimento API → core/ingestion/__init__.py
```

---

**Ricorda**: La configurazione è il tuo strumento principale. Inizia da lì prima di scrivere codice.
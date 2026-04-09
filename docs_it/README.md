# Pipeline di Ingestione Documenti

Un modulo di ingestione general-purpose, basato su configurazione, progettato come **primo passo di qualsiasi pipeline di dati**.

---

## 📁 Struttura del Progetto

```
pipeline-ingestion/
├── core/
│   ├── __init__.py
│   └── ingestion/                    # Modulo principale
│       ├── __init__.py              # API pubblica
│       ├── types.py                 # Tipi di dati core
│       ├── config.py                # Schema e caricamento configurazione
│       ├── scanner.py               # Scansione filesystem + ZIP
│       ├── loader.py                # Estrazione testo multi-formato
│       ├── sidecar.py               # Scoperta metadati
│       ├── id_generator.py          # Generazione ID deterministica
│       ├── analyzers.py             # Pipeline di analisi (opzionale)
│       ├── backends.py              # Persistenza (pluggabile)
│       ├── ingest_service.py        # Orchestratore principale
│       └── builder.py               # Pattern factory
│
├── config/
│   └── ingest.yaml                  # Configurazione predefinita
│
├── docs/
│   ├── ingest-config-schema.md      # Riferimento schema YAML
│   ├── architecture.md              # Decisioni di design
│   └── examples.md                  # Esempi di utilizzo
│
├── test/
│   └── unit/
│       └── test_ingestion.py        # Test unitari
│
├── README.md                         # Panoramica
├── .env.example                      # Variabili d'ambiente
└── .gitignore
```

---

## 🎯 Caratteristiche Principali

### ✅ Basato su Configurazione
- **Fonte Unica di Verità**: Tutto il comportamento è parametrizzato in YAML
- **Nessuna Logica Hardcoded**: Agnostic client, riutilizzabile tra progetti
- **Override Runtime**: Personalizzazione programmatica della configurazione

### ✅ Supporto Multi-Formato
- PDF (con estrazione testo)
- DOCX (estrazione testo nativa)
- DOC (supporto conversione)
- HTML/HTM (parsing BeautifulSoup)
- Testo semplice (fallback encoding)
- **Archivi ZIP** (estrazione ricorsiva, profondità configurabile)

### ✅ Generazione ID Flessibile
- **SHA256-16**: Deterministico, 16 caratteri leggibili
- **SHA256-32**: Unicità crittografica completa
- **UUID4**: Non-deterministico (per testing)
- **Personalizzato**: Interfaccia plugin per strategie personalizzate

### ✅ Scoperta Metadati (Sidecar)
- Corrispondenza per nome: `document.pdf` → `document.json`
- Scansione directory: Trova qualsiasi `.json` nella stessa cartella
- Directory padre: Cerca nella directory padre se in "attachments"
- Estensibile: Aggiungi strategie di ricerca personalizzate

### ✅ Architettura Plugin
- **Generatori ID Personalizzati**: Registra a runtime
- **Analizzatori Personalizzati**: Validazione testo, estrazione entità, ecc.
- **Backend Personalizzati**: Archivia su database, cloud, S3, ecc.
- **Zero Breaking Changes**: I plugin non modificano il core

### ✅ Gestione Errori Robusta
- Tracciamento errori per documento (non fallisce l'intero batch)
- Manifest dettagliato con successi e fallimenti
- Adatto per elaborazione batch su larga scala

### ✅ Pipeline Analizzatore (Opzionale)
- Post-elaborazione dei documenti
- Validazione testo, rimozione null-byte
- Estensibile: Concatena analizzatori personalizzati
- Disabilitato per default (nessun overhead)

### ✅ Struttura Output Pulita
```
output/
  manifest.json
  b784e2c8dbba8d15/           # Directory per documento - ID COMPLETO
    b784e2c8dbba8d15.html     # File originale - ID COMPLETO come nome file
    sc_b784e2c8dbba8d15.json  # Metadati sidecar - prefisso sc_
    rd_b784e2c8dbba8d15.json  # Documenti correlati - prefisso rd_
```

---

## 📖 Utilizzo

### Base (Raccomandato)
```python
from core.ingestion import create_ingest_service

# Crea e avvia
service = create_ingest_service("config/ingest.yaml", "output/")
manifest = service.ingest("input/")

print(f"Ingestiti: {len(manifest.ingested)}")
print(f"Errori: {len(manifest.errors)}")
```

### Da Riga di Comando (YAML)
```bash
# Usa le cartelle di input definite nel YAML
python main.py --config config/ingest.yaml --output output/

# Con configurazione personalizzata
python main.py --config my_config.yaml --output results/
```

### Pattern Builder (Avanzato)
```python
from core.ingestion import IngestBuilder

service = (
    IngestBuilder.from_config("config/ingest.yaml")
    .with_output_dir("output/")
    .with_config_value("input.max_depth", 20)
    .enable_analyzers(True)
    .build()
)

manifest = service.ingest("input/")
```

### Configurazione Programmatica
```python
from core.ingestion import IngestBuilder

config_dict = {
    "ingest": {
        "input": {"supported_formats": ["pdf", "docx"]},
        "id_generation": {"strategy": "sha256-16"},
        "output": {"backend": "filesystem"},
    }
}

service = (
    IngestBuilder.from_dict(config_dict)
    .with_output_dir("output/")
    .build()
)

manifest = service.ingest("input/")
```

---

## 🔧 Esempi Configurazione

### Minimale (Solo PDF)
```yaml
ingest:
  input:
    supported_formats: [pdf]
  id_generation:
    strategy: sha256-16
```

### Completo (Tutti i formati + metadati + analisi)
```yaml
ingest:
  input:
    supported_formats: [pdf, docx, doc, html, htm, txt]
    max_depth: 10
  zip_extraction:
    enabled: true
    max_archive_depth: 3
  metadata:
    enabled: true
  analyzers:
    enabled: true
```

### Modalità Compliance (Auditabile, deterministico)
```yaml
ingest:
  id_generation:
    strategy: sha256-32  # Hash completo
  loader:
    max_text_length: 500000
  logging:
    level: DEBUG
    file: logs/ingest.log
```

---

## 📊 Architettura

### Componenti Core

| Componente | Responsabilità | Config |
|-----------|-----------------|--------|
| **Scanner** | Trova documenti, estrae ZIP | `input.*`, `zip_extraction.*` |
| **Loader** | Normalizza contenuto documenti | `loader.*`, `conversion.*` |
| **MetadataLoader** | Scopre metadati accoppiati | `metadata.*` |
| **IDGenerator** | Assegna ID deterministici | `id_generation.*` |
| **AnalyzerPipeline** | Post-elaborazione opzionale | `analyzers.*` |
| **Persistence** | Archivia documenti, manifest | `output.*` |

### Flusso Dati
```
Directory Input
   ↓ Scanner
Riferimenti Documento
   ↓ Loader
Testo Estratto + Metadati
   ↓ IDGenerator
ID Documento
   ↓ AnalyzerPipeline
Risultati Analisi
   ↓ Persistence
Directory Output + Manifest
```

---

## 🧪 Testing

### Test Unitari
```bash
pytest test/unit/ -v
```

### Coverage
```bash
pytest --cov=core/ingestion test/
```

### Esempi Test Inclusi
- Strategie generazione ID
- Caricamento e validazione configurazione
- Tipi documento e serializzazione
- Pattern builder
- Scansione base

---

## 🔌 Punti Estensione

### Registra Generatore ID Personalizzato
```python
from core.ingestion import IDGenerator, IDGeneratorFactory

class MioGeneratoreID(IDGenerator):
    def generate(self, file_bytes: bytes) -> str:
        return f"custom_{hash(file_bytes)}"

IDGeneratorFactory.register("mio_strategy", MioGeneratoreID)
```

### Registra Analizzatore Personalizzato
```python
from core.ingestion import Analyzer, AnalyzerFactory

class MioAnalizzatore(Analyzer):
    def analyze(self, document):
        return {"campo_personalizzato": "valore"}

AnalyzerFactory.register("mio_analizzatore", MioAnalizzatore)
```

### Registra Backend Personalizzato
```python
from core.ingestion import PersistenceBackend, PersistenceBackendFactory

class MioBackend(PersistenceBackend):
    def persist(self, document: IngestedDocument, config):
        # Archivia su database, cloud, ecc.
        pass

PersistenceBackendFactory.register("mio_backend", MioBackend)
```

---

## 📝 Documentazione

| Documento | Scopo |
|----------|---------|
| **README.md** | Panoramica progetto, avvio rapido |
| **docs/ingest-config-schema.md** | Riferimento schema YAML completo |
| **docs/architecture.md** | Decisioni design, troubleshooting |
| **docs/examples.md** | 10+ esempi utilizzo (base ad avanzato) |

---

## ✨ Principi Design

### 1. La Configurazione è Fonte di Verità
- Nessun comportamento hardcoded
- I cambiamenti richiedono modifiche al codice

### 2. Architettura Pluggable
- Logica core è pura
- Plugin sono opzionali
- Estensibilità non richiede fork

### 3. Agnostic Client
- Nessuna assunzione Fineco/Intesa/dominio-specifica
- Funziona con qualsiasi progetto, qualsiasi organizzazione
- Riutilizzabile tra team pipeline

### 4. ID Deterministici
- Stesso documento → stesso ID (deduplicazione)
- Nessun database necessario per gestione ID
- Rilevamento diff efficiente

### 5. Gestione Errori Graziosa
- Un documento cattivo ≠ fallisce tutto
- Manifest traccia cosa ha avuto successo/fallito
- Adatto per elaborazione batch su larga scala

### 6. Dipendenze Minime
- Core: stdlib + dataclasses solo
- Opzionali: plugin portano proprie dipendenze

---

## 🚀 Prossimi Passi nella Pipeline

Dopo l'ingestione, i documenti sono pronti per:
1. **Arricchimento** - Aggiungi metadati, classificazione
2. **Elaborazione** - Trasformazioni, validazioni
3. **Indicizzazione** - Ricerca, database
4. **Distribuzione** - S3, data warehouse, API

---

**Status:** Platform v1.0 | **Concetto Centrale:** Ingestione come primo passo pipeline basato su configurazione
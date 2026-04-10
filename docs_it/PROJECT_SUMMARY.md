# RIASSUNTO CONSEGNA PROGETTO

## ✅ Completato: Modulo Ingestione Documenti General-Purpose

Un sistema di ingestione pronto per produzione, basato su configurazione YAML.

---

## 📁 Struttura Progetto

```
pipeline-ingestion/
├── core/
│   ├── __init__.py
│   └── ingestion/                    # Modulo principale
│       ├── __init__.py              # API pubblica
│       ├── types.py                 # Tipi dati core
│       ├── config.py                # Schema configurazione & caricamento
│       ├── scanner.py               # Scansione filesystem + ZIP
│       ├── loader.py                # Estrazione testo multi-formato
│       ├── sidecar.py               # Scoperta metadati
│       ├── id_generator.py          # Generazione ID deterministica
│       ├── analyzers.py             # Validazione testuale (NO parsing)
│       ├── backends.py              # Persistenza (pluggabile)
│       ├── ingest_service.py        # Orchestratore principale
│       └── builder.py               # Pattern factory
│
├── config/
│   └── ingest.yaml                  # Configurazione predefinita
│
├── docs_it/
│   ├── ingest-config-schema.md      # Riferimento schema YAML
│   ├── architecture.md              # Decisioni design
│   ├── INVARIANTI.md                # Vincoli e contratti di correttezza
│   └── PROJECT_SUMMARY.md           # Sintesi progetto e stato consegna
│
├── test/
│   ├── contract/
│   ├── e2e/
│   ├── integration/
│   └── unit/
│
├── README.md                         # Panoramica
├── .env.example                      # Variabili ambiente
└── .gitignore
```

---

## 🎯 Caratteristiche Chiave

### ✅ Basato su Configurazione
- Tutto il comportamento è parametrizzato in YAML
- **Nessuna Logica Hardcoded**: Agnostic client, riutilizzabile tra progetti

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
- Estensibile: Aggiungi strategie ricerca personalizzate

### ✅ Architettura Plugin
- **Generatori ID Personalizzati**: Registra a runtime
- **Analizzatori Built-in**: Solo validazione testo (nessun parsing/strutturazione)
- **Zero Breaking Changes**: Plugin non modificano core

### ✅ Gestione Errori Robusta
- Tracciamento errori per documento (non fallisce intero batch)
- Manifest dettagliato con successi e fallimenti
- Adatto per elaborazione batch su larga scala

### ✅ Pipeline Analizzatore - Configurabile (NO Parsing)
- Post-elaborazione documenti
- Validazione testo, rimozione null-byte
- Esegue solo analizzatori non di parsing
- Disabilitato per default (nessun overhead)

### ✅ Struttura Output
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

### Base
```python
from core.ingestion import create_ingest_service

# Crea e avvia
service = create_ingest_service("config/ingest.yaml", "output/")
manifest = service.ingest("input/")

print(f"Ingestiti: {len(manifest.ingested)}")
print(f"Errori: {len(manifest.errors)}")
```

### Pattern Builder
```python
from core.ingestion import IngestBuilder

service = (
    IngestBuilder.from_config("config/ingest.yaml")
    .with_output_dir("output/")
    .with_config_value("input.max_depth", 20)
    .with_config_value("loader.max_text_length", 500000)
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

### Completo (Tutti formati + metadati, senza parsing analyzer)
```yaml
ingest:
  input:
    supported_formats: [pdf, docx, doc, html, htm, txt]
    max_depth: 10
  zip_extraction:
    enabled: true
    max_archive_depth: 3
    temp_dir: temp/zip-work
  metadata:
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
| **Loader** | Normalizza contenuto documenti | `loader.*` |
| **MetadataLoader** | Scopre metadati accoppiati | `metadata.*` |
| **IDGenerator** | Assegna ID deterministici | `id_generation.*` |
| **Validazione Testo Base** | Controllo interno testo estratto, non configurato via YAML | interno |
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
  ↓ Validazione Testo Base (interna)
Controlli Testo
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
        import hashlib
        h = hashlib.sha256(file_bytes).hexdigest()[:8]
        return f"COMPANY_{h}"

IDGeneratorFactory.register("company", MioGeneratoreID)
```

```yaml
ingest:
  id_generation:
    strategy: company
```

### Registra Backend Personalizzato
```python
from core.ingestion import IngestedDocument, PersistenceBackend, PersistenceBackendFactory

class MioBackend(PersistenceBackend):
    def persist(self, document: IngestedDocument, config):
        # Archivia su database, cloud, ecc.
        pass

PersistenceBackendFactory.register("mio_backend", MioBackend)
```

```yaml
ingest:
  output:
    backend: mio_backend
```

---

## 📝 Documentazione

| Documento | Scopo |
|----------|---------|
| **README.md** | Panoramica progetto, avvio rapido |
| **docs_it/ingest-config-schema.md** | Riferimento schema YAML completo |
| **docs_it/architecture.md** | Design & decisioni |
| **docs_it/INVARIANTI.md** | Invarianti e contratti del sistema |
| **docs_it/PROJECT_SUMMARY.md** | Sintesi progetto e artefatti |

---

## ✨ Principi Design

### 1. Configurazione è Fonte di Verità
- Nessun comportamento hardcoded
- Cambiamenti richiedono modifiche al codice

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
- Core runtime: stdlib + PyYAML
- Opzionali per formato/funzionalita: pypdf, beautifulsoup4, python-docx, pywin32

---

## 🚀 Prossimi Passi nella Pipeline

Dopo ingestione, documenti sono pronti per:
1. **Arricchimento** - Aggiungi metadati, classificazione
2. **Elaborazione** - Trasformazioni, validazioni
3. **Indicizzazione** - Ricerca, database
4. **Distribuzione** - S3, data warehouse, API

---

## 📦 Consegne

### Codice (10 moduli)
- ✅ `types.py` - Strutture dati core
- ✅ `config.py` - Schema configurazione & caricamento
- ✅ `scanner.py` - Gestione filesystem + ZIP
- ✅ `loader.py` - Estrazione testo multi-formato
- ✅ `sidecar.py` - Scoperta metadati
- ✅ `id_generator.py` - ID deterministici/random
- ✅ `analyzers.py` - Pipeline validazione testuale (NO parsing)
- ✅ `backends.py` - Interfaccia persistenza + filesystem
- ✅ `ingest_service.py` - Orchestratore principale
- ✅ `builder.py` - Pattern factory

### Configurazione
- ✅ `config/ingest.yaml` - Configurazione predefinita

### Documentazione
- ✅ `README.md` - Panoramica & avvio rapido
- ✅ `docs_it/ingest-config-schema.md` - Schema YAML completo
- ✅ `docs_it/architecture.md` - Design & decisioni
- ✅ `docs_it/INVARIANTI.md` - Invarianti e contratti
- ✅ `docs_it/PROJECT_SUMMARY.md` - Riassunto progetto

### Testing
- ✅ `test/` - Suite contract, e2e, integration e unit

### Infrastruttura
- ✅ `.env.example` - Template variabili ambiente
- ✅ `.gitignore` - Gitignore Python standard
- ✅ `core/__init__.py` - Inizializzazione package

---

## 🎓 Lezioni Chiave (da analisi BDT)

### Pattern Estratti da Sistema Corrente
- ✅ Scanner con gestione ZIP
- ✅ Loader multi-formato
- ✅ Scoperta metadati sidecar
- ✅ Generazione ID deterministica
- ✅ Layer persistenza flessibile

### Rimosso (Client-Specifico)
- ❌ Path hardcoded Fineco/BDT
- ❌ Integrazione MongoDB
- ❌ Accoppiamento Document Intelligence
- ❌ Nomi campo dominio-specifici

### Generalizzato
- ✅ Configurazione agnostic client
- ✅ Analizzatori pluggable
- ✅ Backend pluggable
- ✅ Nessuna dipendenza database (opzionale)

---

## 📋 Checklist

- [x] Analizzato sistema ingestione corrente
- [x] Estratti pattern riutilizzabili
- [x] Rimossa logica client-specifica
- [x] Progettato schema configurazione YAML
- [x] Implementata logica ingestione core
- [x] Implementato caricamento configurazione
- [x] Implementato scanner documenti (con ZIP)
- [x] Implementato loader multi-formato
- [x] Implementato scoperta metadati
- [x] Implementato generatori ID
- [x] Implementato pipeline analizzatore
- [x] Implementato layer persistenza
- [x] Implementato orchestratore principale
- [x] Implementato pattern builder/factory
- [x] Creati test unitari
- [x] Creata documentazione completa
- [x] Creati esempi utilizzo
- [x] Struttura progetto-ready

---

## 🎯 Risultato

**Un modulo ingestione general-purpose pronto per produzione** che:
- ✅ Risolve problema ingestione una volta
- ✅ Lo risolve universalmente (qualsiasi progetto)
- ✅ Lo risolve pulitamente (basato su configurazione)
- ✅ Lo risolve estensibilmente (plugin)
- ✅ Lo risolve in sicurezza (errori graziosi)
- ✅ Lo risolve efficientemente (ID deterministici)

**Pronto per essere il primo passo di qualsiasi pipeline.**

---

**Status**: ✅ COMPLETATO
**Versione**: 1.0.0
**Data**: Aprile 2026
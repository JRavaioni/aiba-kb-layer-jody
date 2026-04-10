# Modulo Ingestione - Architettura & Design

Nota: per il nuovo sottosistema di generazione ID configurabile vedi anche `docs_it/ARCHITETTURA.md` e `docs_it/CONFIGURAZIONE_ID_GENERATION.md`.

## Panoramica

Il modulo di ingestione per standardizzare documenti da varie fonti e formati in una struttura output normalizzata.

Nota operativa: il sistema non usa piu file `.keepme` e non ne esegue autogenerazione, ne in cartelle nuove ne in cartelle gia esistenti.

### Principio Core

Tutto il comportamento di ingestione è parametrizzato in YAML. Nessuna logica client-specifica, nessun path hardcoded, nessuna assunzione dominio-specifica.

## Architettura

### Responsabilità Componenti

```
                    IngestService (Orchestratore)
                           |
        ___________|___________|___________|___________|___________
        |          |          |          |          |          |
     Scanner   Loader   MetadataLoader IDGenerator Analyzer Persistence
        |          |          |          |          |          |
     File     Estrazione Testo Sidecar JSON SHA256   Post-Elab
     ZIP     Multi-formato     Scoperta  UUID4    (Opzionale)
```

#### 1. **Scanner**
- **Responsabilità**: Scopre documenti input
- **Comportamento**:
  - Cammina ricorsivamente filesystem (rispetta `max_depth`)
  - Estrae archivi ZIP in directory temporanee
  - Applica regole esclusione
  - Genera "path logici" per documenti annidati
  - Produce oggetti `ScanResult` con campi espliciti (`context`, `document`)
- **Chiavi Config**: `input.*`, `zip_extraction.*`

#### 2. **Loader**
- **Responsabilità**: Normalizza contenuto documenti
- **Comportamento**:
  - Legge byte raw dal file
  - Estrae testo basato su formato (PDF, DOCX, HTML, TXT)
  - Gestisce fallback encoding
  - Forza limite lunghezza testo massima
  - Restituisce `LoadedDocument` con byte + testo estratto
- **Chiavi Config**: `loader.*`

#### 3. **Sidecar**
- **Responsabilità**: Scopre file metadati accoppiati
- **Comportamento**:
  - Applica strategie ricerca in ordine
  - Supporta pattern directory flessibili
  - Parsea metadati JSON
  - Restituisce `Dict[str, Any]` o None
- **Chiavi Config**: `metadata.*`
- **Esempi**:
  - `document.pdf` → `document.json` (by_name)
  - Qualsiasi `.json` nella stessa dir (in_directory)
  - Directory padre se in "attachments" (in_parent)

#### 4. **IDGenerator**
- **Responsabilità**: Produce ID documento deterministici
- **Comportamento**:
  - SHA256-based (deterministico):
    - `sha256-16`: Primi 16 caratteri hex
    - `sha256-32`: Tutti 64 caratteri hex
  - UUID4-based (non-deterministico, per testing)
  - Prefisso/suffisso configurabili
  - Stesso input produce sempre stesso ID (deduplicazione)
- **Chiavi Config**: `id_generation.*`

#### 5. **Analyzer** (Opzionale)
- **Responsabilità**: Post-elabora documenti
- **Comportamento**:
  - Esegue sequenza analizzatori built-in
  - Include esempio validazione testo
  - Può essere disabilitato
  - Strategie gestione errori (skip / fail_document / fail_all)
- **Chiavi Config**: `analyzers.*`
- **Scope**: analizzatori built-in definiti nel progetto

#### 6. **Backend** (Pluggabile)
- **Responsabilità**: Archivia documenti ingestiti
- **Comportamento**:
  - Backend filesystem (predefinito): scrive struttura directory
  - Crea directory per documento (`{doc_id}/`)
  - Persiste artefatti: originale, testo, metadati
  - Genera manifest
  - Estensibile: backend personalizzati possono archiviare su DB, cloud, ecc.
- **Chiavi Config**: `output.*`

#### 7. **IngestService** (Orchestratore)
- **Responsabilità**: Coordina intera pipeline
- **Comportamento**:
  - Scansiona → Carica → Estrae metadati → Genera ID → Analizza → Persiste
  - Gestione errori per documento (non fallisce intera run)
  - Genera manifest con risultati
  - Avvolge tutti componenti

## Flusso Dati

```
Directory Input
      ↓
  Scanner ─────→ ScanResult(context, document)
            └─ document: DocumentRef (logical_path, real_path, format, basename)
      ↓
   Loader ───────→ LoadedDocument (raw_bytes, extracted_text, pages_count)
      ↓
  Sidecar → Dict[str, Any] (metadati sidecar o vuoto)
      ↓
  IDGenerator ───→ doc_id (deterministico: "b784e2c8dbba8d15")
      ↓
  DocumentMetadata (doc_id, format, hash, text_length, sidecar_data)
      ↓
  IngestedDocument (metadata + raw_bytes + extracted_text)
      ↓
  Validazione Testo Base (interna, nessun analyzer_output persistito)
      ↓
  Persistence ────→ {output_dir}/b784e2c8dbba8d15/
                    ├── b784e2c8dbba8d15.html
                    ├── source.json
                    └── related.json
      ↓
   Manifest (mapping: logical_path → doc_id, errori, warning per documento)
```

## Design Basato su Configurazione

Tutto il comportamento è parametrizzato in YAML:

### Esempio: Cambiare Supporto Formato File

**Invece di modificare codice:**
```python
# VECCHIO (hardcoded)
SUPPORTED_FORMATS = {"pdf", "docx", "html"}
```

**Basta aggiornare YAML:**
```yaml
ingest:
  input:
    supported_formats: [pdf, docx, html, txt, xml, md, json]
```

### Esempio: Cambiare Generazione ID

**VECCHIO (hardcoded):**
```python
doc_id = f"doc_{hashlib.sha256(bytes).hexdigest()[:16]}"
```

**NUOVO (configurabile):**
```yaml
ingest:
  id_generation:
    strategy: sha256-32  # sha256-16, sha256-32, uuid4, custom
    prefix: "hash_"
```

### Esempio: Abilitare/Disabilitare Caratteristiche

```yaml
ingest:
  zip_extraction:
    enabled: false  # Disabilita supporto ZIP
    temp_dir: temp/zip-work  # Root temp dedicata per l'estrazione ZIP
  
  metadata:
    enabled: false  # Disabilita scoperta metadati sidecar
  
Nota: il controllo testo base e interno e non espone sezione `analyzers` nello YAML.
```

## Architettura Plugin

### Generatori ID Personalizzati

```python
from core.ingestion import IDGenerator, IDGeneratorFactory

class MioGeneratoreID(IDGenerator):
    def generate(self, file_bytes: bytes) -> str:
        # La tua logica
        return f"custom_{hash(file_bytes)}"

IDGeneratorFactory.register("mia_strategy", MioGeneratoreID)
```

```yaml
ingest:
  id_generation:
    strategy: mia_strategy
```

### Validazione Testo Disponibile

Il sistema esegue solo una validazione testo base interna, senza configurazione YAML dedicata.

### Backend Persistenza Personalizzati

```python
from core.ingestion import (
  IngestedDocument,
  IngestManifest,
  PersistenceBackend,
  PersistenceBackendFactory,
)

class MioBackend(PersistenceBackend):
    def persist(self, document: IngestedDocument, config):
        # Archivia su database, cloud, ecc.
        pass
    
    def save_manifest(self, manifest: IngestManifest, config):
        pass

PersistenceBackendFactory.register("mio_backend", MioBackend)
```

```yaml
ingest:
  output:
    backend: mio_backend
```

## Decisioni Design

### 1. **ID Deterministici (SHA256)**
**Perché?**
- Stesso documento sempre stesso ID → deduplicazione
- Nessun database necessario per gestione ID
- Rilevamento diff efficiente tra run

**Trade-off**: ID non-deterministici (UUID4) disponibili per testing.

### 2. **Estrazione Temporanea per ZIP**
**Perché?**
- Evita modifica dati input
- Gestisce ZIP annidati pulitamente
- Pulizia automatica previene accumulo disco

**Implementazione**: `tempfile.TemporaryDirectory()` con context manager

### 3. **Metadati Sidecar**
**Perché?**
- Molti documenti hanno file metadati accoppiati (.json)
- Strategie scoperta flessibili gestiscono layout diversi
- Opzionale - ingestione funziona senza metadati

**Ordine Ricerca**:
1. Corrispondenza nome esatta (`document.json`)
2. Qualsiasi JSON nella stessa directory
3. Directory padre (se cartella corrente è "attachments")

### 4. **Gestione Errori Per-Documento**
**Perché?**
- Un documento cattivo non fallisce intera run
- Manifest traccia cosa ha avuto successo/fallito/warning
- Adatto per elaborazione batch su larga scala

**Trade-off**: Senza fail-fast, bug possono essere più difficili da debug.

### 5. **Pluggable Prima, Batterie Incluse Secondo**
**Perché?**
- Logica core è pura
- Plugin sono opt-in
- Estensibilità non richiede fork

**Esempio**: Analizzatori disabilitati per default.

### 6. **Nessuna Logica Client Hardcoded**
**Perché?**
- Riutilizzabile tra progetti
- Evita assunzioni Fineco/Intesa/dominio-specifiche
- Configurazione diventa contratto

**Risultato**: Può essere usato in qualsiasi pipeline, qualsiasi organizzazione.

## Strategia Testing

```
test/
  unit/
    t_config_unit.py
    t_id_generator_unit.py
    t_main_unit.py
  contract/
    t_determinism.py
    t_output_contract.py
    t_safety_invariants.py
  integration/
    t_component_integration.py
  
  e2e/
    t_ingestion_e2e.py
    t_zip_resilience_e2e.py
```

Esegui test:
```bash
pytest test/unit/ -v
pytest test/integration/ -v
pytest --cov=core/ingestion test/
```

## Considerazioni Performance

### Single-Threaded (Predefinito)
- Semplice, prevedibile
- Facile da debug
- Adatto per la maggior parte casi d'uso

### Efficienza Memoria
- Byte documento letti una volta
- Testo estratto e archiviato (dimensione limitata)
- Directory temp auto-pulite

## Troubleshooting

### Problema: Documenti non trovati
**Controlla**:
- `input.supported_formats` include estensioni file
- `input.exclude_paths` non filtra file buoni
- `input.max_depth` sufficiente per profondità directory

### Problema: Nessun testo estratto
**Controlla**:
- `loader.pdf.extract_text: true`
- Librerie richieste installate (pypdf, beautifulsoup4)
- File non corrotto

### Problema: Metadati non allegati
**Controlla**:
- `metadata.enabled: true`
- Ordine strategia ricerca corrisponde al tuo layout file
- File metadati sono JSON validi

### Problema: Uso memoria alto
**Controlla**:
- Limite `loader.max_text_length`
- Input molto grandi e profondita ZIP annidata

## Miglioramenti Futuri

- [ ] Elaborazione parallela
- [ ] Modalità streaming per documenti enormi
- [ ] Backend persistenza database
- [ ] Analizzatore OCR (immagine → testo)
- [ ] Analizzatore estrazione entità
- [ ] Ingestione incrementale/delta
- [ ] Compressione in output
- [ ] Hook basati su eventi (pre_ingest, post_ingest)
- [ ] Integrazione metriche/monitoraggio
- [ ] Policy retry per fallimenti transienti

---

**Concetto Chiave**: Configurazione + Plugin = Motore Ingestione Universale
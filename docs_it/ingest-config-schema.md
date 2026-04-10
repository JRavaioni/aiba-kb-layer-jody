# Schema Configurazione Ingestione - Riferimento Completo

Riferimento completo per tutte le opzioni di configurazione YAML supportate dal modulo di ingestione.

## Struttura Generale

```yaml
ingest:
  # ============================================================================
  # SCOPERTA INPUT
  # ============================================================================
  input:
    supported_formats: [pdf, docx, doc, html, htm, txt, xml, md, json]
    max_depth: 10
    exclude_paths: [".git", "__pycache__", "node_modules"]

  # ============================================================================
  # ESTRAZIONE ZIP
  # ============================================================================
  zip_extraction:
    enabled: true
    max_archive_depth: 3
    temp_dir: null
    exclude_patterns_in_archive: ["__MACOSX/*", "*.DS_Store"]

  # ============================================================================
  # GENERAZIONE ID (DETERMINISTICA)
  # ============================================================================
  id_generation:
    strategy: sha256-16  # sha256-16, sha256-32, uuid4, custom
    prefix: "doc_"
    suffix: ""

  # ============================================================================
  # CARICAMENTO DOCUMENTI & ESTRAZIONE TESTO
  # ============================================================================
  loader:
    encoding_fallback: [utf-8, latin-1, cp1252]
    max_text_length: 1000000

    # Impostazioni estrazione testo supportate
    pdf:
      extract_text: true
      max_pages: 0

  # ============================================================================
  # GESTIONE METADATI (FILE SIDECAR)
  # ============================================================================
  metadata:
    enabled: true
    base_paths: ["."]  # Default: directory corrente e sottodirectory
    search_strategies:
      - name: by_name
        description: "corrispondenza nome file esatta con estensione .json"
        rule: "{basename}.json"

      - name: in_directory
        description: "qualsiasi file .json nella stessa directory"
        rule: "*.json"

      - name: in_parent
        description: "metadati nella directory padre se directory è denominata 'attachments'"
        rule: "parent_if_attachments"

    format: json
    validation_enabled: false

  # ============================================================================
  # OUTPUT & PERSISTENZA
  # ============================================================================
  output:
    backend: filesystem

    filesystem:
      dir_pattern: "{doc_id}"  # Directory per documento - ID COMPLETO
      preserve_extension: true
      create_manifest: true
      manifest_filename: manifest.json

  # ============================================================================
  # LOGGING & DEBUGGING
  # ============================================================================
  logging:
    level: INFO  # DEBUG, INFO, WARNING, ERROR
    file: null   # "logs/ingest.log"
    include_timings: false

```

## Riferimento Dettagliato

### Sezione `input`

Controlla come vengono scoperti i documenti di input.

#### `dirs` (array di stringhe)
- **Default**: `["ingestion_test_data/raw"]`
- **Descrizione**: Cartelle di input da cui leggere i documenti
- **Esempio**:
  ```yaml
  dirs:
    - "documents/"
    - "archive/old_docs/"
    - "/external/shared/documents/"
  ```

#### `supported_formats` (array di stringhe)
- **Default**: `[pdf, docx, html, txt]` (valore dataclass)
- **Descrizione**: Formati file supportati per l'ingestione
- **Valori usati nel progetto**: `pdf`, `docx`, `doc`, `html`, `htm`, `txt`, `xml`, `md`, `json`
- **Esempio**:
  ```yaml
  supported_formats: [pdf, docx, txt, json]
  ```

#### `max_depth` (intero)
- **Default**: `10`
- **Descrizione**: Profondità massima directory per scansione ricorsiva
- **Valori validi**: `1` - `100`
- **Esempio**:
  ```yaml
  max_depth: 5
  ```

#### `exclude_paths` (array di stringhe)
- **Default**: `[".git", "__pycache__", "node_modules", ".DS_Store"]`
- **Descrizione**: Pattern path da escludere dalla scansione
- **Supporta**: Glob pattern e percorsi relativi
- **Esempio**:
  ```yaml
  exclude_paths: [".git", "temp_*", "*.tmp"]
  ```

### Sezione `zip_extraction`

Controlla l'estrazione di archivi ZIP.

#### `enabled` (booleano)
- **Default**: `true`
- **Descrizione**: Abilita/disabilita estrazione ZIP automatica
- **Esempio**:
  ```yaml
  enabled: false
  ```

#### `max_archive_depth` (intero)
- **Default**: `3`
- **Descrizione**: Profondità massima per ZIP annidati
- **Valori validi**: `1` - `10`
- **Esempio**:
  ```yaml
  max_archive_depth: 2
  ```

#### `temp_dir` (stringa/null)
- **Default**: `null`
- **Descrizione**: Directory radice in cui vengono creati i workspace temporanei per l'estrazione ZIP
- **Comportamento**: Se valorizzato viene usato come root temp ZIP; se `null`, il sistema usa la temp di sistema
- **Esempio**:
  ```yaml
  temp_dir: "temp/zip-work"
  ```

#### `exclude_patterns_in_archive` (array di stringhe)
- **Default**: `["__MACOSX/*", "*.DS_Store"]`
- **Descrizione**: Pattern da escludere all'interno degli archivi ZIP
- **Esempio**:
  ```yaml
  exclude_patterns_in_archive: ["__MACOSX/*", "Thumbs.db"]
  ```

### Sezione `id_generation`

Controlla come vengono generati gli ID documento.

#### `strategy` (stringa)
- **Default**: `sha256-16`
- **Descrizione**: Strategia generazione ID
- **Valori validi**:
  - `sha256-16`: Primi 16 caratteri SHA256 (leggibile)
  - `sha256-32`: SHA256 completo (64 caratteri)
  - `uuid4`: UUID non-deterministico (per testing)
  - `custom`: Strategia custom registrata a runtime
- **Esempio**:
  ```yaml
  strategy: sha256-32
  ```

#### `prefix` (stringa)
- **Default**: `"doc_"`
- **Descrizione**: Prefisso aggiunto all'ID generato
- **Nota**: In `config/ingest.yaml` del progetto il prefisso e' impostato a stringa vuota
- **Esempio**:
  ```yaml
  prefix: "doc_"
  ```

#### `suffix` (stringa)
- **Default**: `""`
- **Descrizione**: Suffisso aggiunto all'ID generato
- **Esempio**:
  ```yaml
  suffix: "_v1"
  ```

### Sezione `loader`

Controlla l'estrazione testo dai documenti.

#### `encoding_fallback` (array di stringhe)
- **Default**: `[utf-8, latin-1, cp1252]`
- **Descrizione**: Encoding da provare in ordine per file testo
- **Esempio**:
  ```yaml
  encoding_fallback: [utf-8, cp1252]
  ```

#### `max_text_length` (intero)
- **Default**: `1000000`
- **Descrizione**: Lunghezza massima testo estratto (caratteri)
- **Valori validi**: `1000` - `10000000`
- **Esempio**:
  ```yaml
  max_text_length: 500000
  ```

#### Sottosezioni Formato-Specifico

##### `pdf`
- `extract_text` (booleano, default: `true`): Estrai testo da PDF
- `max_pages` (intero, default: `0`): Pagine massime (0 = tutte)

### Sezione `metadata`

Controlla scoperta metadati sidecar.

#### `enabled` (booleano)
- **Default**: `true`
- **Descrizione**: Abilita scoperta metadati sidecar

#### `base_paths` (array di stringhe)
- **Default**: `["."]`
- **Descrizione**: Directory base per ricerca metadati
- **Esempio**:
  ```yaml
  base_paths: [".", "../metadata", "/external/metadata"]
  ```

#### `search_strategies` (array di oggetti)
- **Descrizione**: Strategie ricerca metadati in ordine di priorità
- **Struttura**:
  ```yaml
  - name: "nome_strategy"
    description: "descrizione"
    rule: "pattern_ricerca"
  ```

#### `format` (stringa)
- **Default**: `json`
- **Descrizione**: Formato file metadati

#### `validation_enabled` (booleano)
- **Default**: `false`
- **Descrizione**: Valida schema metadati

### Sezione `output`

Controlla output e persistenza.

#### `backend` (stringa)
- **Default**: `filesystem`
- **Descrizione**: Backend persistenza da usare

#### Sottosezione `filesystem`

##### `dir_pattern` (stringa)
- **Default**: `"{doc_id}"`
- **Descrizione**: Pattern nome directory per documento
- **Template**: `{doc_id}` = ID documento completo

##### `preserve_extension` (booleano)
- **Default**: `true`
- **Descrizione**: Mantieni estensione originale nei nomi file

##### `create_manifest` (booleano)
- **Default**: `true`
- **Descrizione**: Crea file manifest riassuntivo

##### `manifest_filename` (stringa)
- **Default**: `manifest.json`
- **Descrizione**: Nome file manifest

#### Struttura Output Fissa

La struttura output non e configurabile tramite sezione `artifacts`.

Per ogni documento il backend filesystem produce sempre:
- file originale `<doc_id>.<ext>`
- metadati sidecar `source.json`
- indice relazioni `related.json`

Il manifest globale viene controllato dai soli parametri della sezione `filesystem`.

### Validazione Testo Base

Il sistema esegue un controllo testo base interno non configurato via YAML.

Comportamento:
- puo rimuovere null byte dal testo estratto
- puo verificare che la lunghezza del testo non sia nulla o anomala
- non produce alcun blocco `analyzer_output` negli artifact persistiti
- non esegue parsing o strutturazione di HTML, XML o JSON

### Sezione `logging`

Controlla logging e debugging.

#### `level` (stringa)
- **Default**: `INFO`
- **Descrizione**: Livello logging
- **Valori validi**: `DEBUG`, `INFO`, `WARNING`, `ERROR`

#### `file` (stringa/null)
- **Default**: `null`
- **Descrizione**: File log (null = console)

#### `include_timings` (booleano)
- **Default**: `false`
- **Descrizione**: Includi timing nelle operazioni

## Esempi Configurazione

### Configurazione Minimale
```yaml
ingest:
  input:
    dirs: ["documents/"]
    supported_formats: [pdf]
  id_generation:
    strategy: sha256-16
```

### Configurazione Completa
```yaml
ingest:
  input:
    dirs:
      - "documents/current/"
      - "archive/old_docs/"
      - "/external/shared/documents/"
    supported_formats: [pdf, docx, html, txt]
    max_depth: 5
  zip_extraction:
    enabled: true
    max_archive_depth: 2
  metadata:
    enabled: true
    base_paths: [".", "../metadata"]
  logging:
    level: DEBUG
    file: logs/ingest.log
```

### Configurazione Compliance
```yaml
ingest:
  id_generation:
    strategy: sha256-32
  loader:
    max_text_length: 500000
  logging:
    level: DEBUG
    include_timings: true
```

## Validazione Configurazione

Il sistema valida automaticamente la configurazione all'avvio:

```python
from core.ingestion import IngestConfig

config = IngestConfig.from_yaml("config/ingest.yaml")
errors = config.validate()

if errors:
    for error in errors:
        print(f"Errore configurazione: {error}")
```

## Estensioni Personalizzate

Le estensioni supportate attualmente sono il generatore ID e il backend di persistenza.

---

**Nota**: Questa documentazione riflette l'architettura corrente con ID documento completi senza prefissi, metadati sidecar configurabili con base_paths, e struttura output per-documento con convenzioni di denominazione fisse (source.json, related.json).
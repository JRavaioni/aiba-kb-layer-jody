# Invarianti di Correttezza

## Cosa Sono le Invarianti?

Un **invariante** è una proprietà del sistema che deve SEMPRE essere vera, in qualsiasi situazione.

Se un invariante viene violato, il sistema è **broken** e non può continuare.

Esempio:
- **Invariante**: "Raw bytes di un documento non sono mai modificati"
- **Se violato**: Hash del file originale ≠ Hash dei raw_bytes estratti → SISTEMA BROKEN

---

## Categorie di Invarianti

### 1. INVARIANTI DI INTEGRITÀ DATI

**Raw Bytes Mai Modificati**
- I byte grezzi di un documento rimangono **identici** dal file originale
- Hash SHA256 del file originale == Hash SHA256 dei raw_bytes in OutputDirectory
- Se violato: I dati non sono più affidabili

**Deduplicazione Basata su Contenuto**
- Due file con **identico contenuto** producono **identico ID**
- ID è basato su hash, NON su path/metadata
- Se violato: Deduplicazione fallisce

**Nessun File Perso**
- Se un documento è stato ingerito, rimane **permanentemente** in output_dir
- Non viene mai cancellato automaticamente
- Se violato: Documenti scompaiono

**Manifest Accurato**
- Tutti i documenti ingestiti sono listati in manifest.json
- Stato (success/fail) registrato correttamente
- Se violato: Perdita tracciamento

---

### 2. INVARIANTI DI SICUREZZA

**Nessuna Esecuzione di Codice**
- Un documento HTML **non esegue JavaScript**
- Archive ZIP **non esegue codice** dentro
- Codice maligno nel documento rimane inerte
- Se violato: RCE vulnerability

**Nessun Directory Traversal**
- Un documento non può scrivere fuori dalla sua directory autorizzata
- Path logico non contiene ".." pericolosi
- Se violato: File system compromise

**Metadata Non Inventato**
- Metadata viene SOLO da file sidecar che effettivamente esistono
- Se no sidecar → metadata = null (non inventato)
- Se violato: Hallucination di dati

**Accesso File Sicuro**
- Nessun accesso a file fuori directory di lavoro
- Configurazione non permette path hardcoded globali
- Se violato: Information disclosure

---

### 3. INVARIANTI DI DETERMINISMO

**Stesso Input, Stesso Output**
- Ingestire gli stessi documenti 2 volte produce **identico output**
- ID sono identici
- Testo estratto è identico
- Metadata è identico
- Se violato: Non-reproducibilità

**ID Deterministico**
- Basato su SHA256 hash
- Sempre uguale per stesso contenuto
- Non cambia mai (a meno che il codice hash cambi)
- Se violato: Deduplicazione impossibile

**Parsing Deterministico**
- Stesso HTML → sempre stesso testo estratto
- Stesso PDF → sempre stesso testo estratto
- Se violato: Output non-reproducibile

---

### 4. INVARIANTI FUNZIONALI

**Fail-Fast su Documento Invalido**
- Documento senza contenuto estratto → **FAIL** esplicitamente
- Non "passed" silenziosamente con testo=null
- Errore registrato in manifest
- Se violato: Documenti invalidi ingeri come validi

**Contratto di Output Structure**
- Ogni documento ha directory propria: `output_dir/<DOC_ID>/`
- Manifest.json sempre in root
- Nessun file loose in output_dir root
- Se violato: Sistemi downstream rompono

**Configurazione**
- Config YAML parametrizza TUTTO
- Nessuna logica hardcoded
- Override runtime possibile
- Se violato: Sistema non-flessibile

---

### 5. INVARIANTI DI ROBUSTEZZA

**Errore per Documento, Non Batch**
- Se documento X fallisce, documento Y continua
- Non fallisce l'intera ingestione
- Manifest traccia successi e fallimenti
- Se violato: Un documento rotto blocca tutto

**Gestione Graceful di File Corrotti**
- PDF con startxref incorretti → parsato (no crash)
- JSON malformato → metadata=null (no crash)
- File mancante → saltato (no crash)
- Se violato: Pipeline fragile

**Logging Esplicito di Fallimenti**
- Ogni errore è loggato
- Error message è descrittivo
- Manifest registra la causa
- Se violato: Debugging impossibile

---

## Verificare gli Invarianti

### Test Suite
Ogni invariante ha un test corrispondente:

```
Invariante: Raw bytes non modificati
↓
Test: t_safety_invariants.py::test_raw_bytes_never_modified
```

### Come Eseguire i Test di Invarianti

```bash
# Test di sicurezza
pytest test/contract/t_safety_invariants.py -v

# Test di integrità dati
pytest test/contract/t_determinism.py -v
pytest test/contract/t_scanner_contract.py -v

# Test di contratto output
pytest test/contract/t_output_contract.py -v

# Test di robustezza
pytest test/contract/t_fail_fast.py -v
```

### Se Un Invariante Viene Violato

1. **STOP**: Non procedere con ingestione
2. **ISOLA**: Trova il codice che viola l'invariante
3. **FIX**: Risolvi il bug
4. **VERIFY**: Il test passa adesso?
5. **REGRESS**: Aggiungi test che cattura il bug per il futuro

---

## Invarianti Critici (Priority 1)

Questi DEVONO SEMPRE essere veri:

| # | Invariante | Perché | Test |
|----|-----------|--------|------|
| 1 | Raw bytes non modificati | Integrità dati | `test_raw_bytes_never_modified` |
| 2 | Nessuna esecuzione codice | Sicurezza | `test_no_code_execution_during_html_loading` |
| 3 | Fail-fast su documento invalido | Qualità | `test_empty_html_document_fails_explicitly` |
| 4 | Metadata non inventato | Correttezza | `test_metadata_not_invented` |
| 5 | ID deterministico | Deduplicazione | `test_sha256_16_is_deterministic` |
| 6 | Contratto output structure | Compatibilità downstream | `test_output_directory_structure_exists` |
| 7 | Manifest accurato | Tracciamento | `test_ingest_produces_valid_manifest` |
| 8 | Errore per documento | Robustezza | `test_valid_document_ingests_successfully` |

---

## Invarianti Importanti (Priority 2)

Questi dovrebbero essere veri (ma con un po' di flessibilità):

| # | Invariante | Perché | Test |
|----|-----------|--------|------|
| 9 | Stesso input, stesso output | Reproducibilità | `test_*_deterministic` |
| 10 | ID basato su contenuto, non path | Deduplicazione | `test_sha256_id_content_based_not_path` |
| 11 | Estrazione testo di qualità | Downstream quality | `test_load_html_valid` |
| 12 | Gestione graceful file corrotti | Robustezza | `test_load_html_empty_should_fail_ingestion` |

---

## Quando Aggiungere Invarianti

Aggiungi un nuovo invariante quando:

1. **Scenario critico**: C'è una proprietà che, se violata, rompe il sistema
2. **Rischio regressione**: Qualcosa che potrebbe essere rotto da future changes
3. **Business requirement**: Cliente richiede garanzia (es. "dati non modificati")
4. **Security concern**: Vulnerabilità potenziale

Esempio: Se aggiungi feature di cifratura, aggiungi invariante:
> "Dati cifrati non sono mai archiviati in plain text"

---

## Testing Invarianti in Produzione

### Smoke Test
Al deploy, esegui:
```bash
pytest test/contract/t_output_contract.py -v
pytest test/contract/t_safety_invariants.py -v
pytest test/e2e/t_ingestion_e2e.py -v
```

### Monitoring
Nel codice di produzione, aggiungi check:

```python
# Verifica invariante: manifest existe
if not (output_dir / "manifest.json").exists():
    raise IngestException("INVARIANT VIOLATED: manifest.json non trovato")

# Verifica invariante: almeno 1 documento
manifest = json.load(...)
if len(manifest["ingested"]) == 0:
    raise IngestException("INVARIANT VIOLATED: nessun documento ingerito")
```

---

## Summary

Le invarianti definiscono il **comportamento minimo garantito** del sistema.

Se un invariante viene violato:
- ❌ Il sistema non funziona correttamente
- ❌ Downstream pipelines ottengono dati corrotti
- ❌ Fiducia nel sistema viene persa

Quindi:
- ✅ Mantieni invarianti
- ✅ Verifica con test
- ✅ Monitora in produzione
- ✅ Aggiorna quando aggiungere features


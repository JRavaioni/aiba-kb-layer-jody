# Suite di Test - Documentazione Completa

## Panoramica

La suite di test del pipeline di ingestione è organizzata in **quattro categorie** che verificano diversi aspetti del sistema:

- **Unit Tests** (`test/unit/`): Test unitari di singoli componenti
- **Integration Tests** (`test/integration/`): Test di integrazione tra componenti
- **Contract Tests** (`test/contract/`): Test di contratto (comportamento osservabile)
- **E2E Tests** (`test/e2e/`): Test end-to-end con dati reali

---

## Convenzione Naming

Tutti i file di test seguono la convenzione:

```
t_<keyword>.py
```

Esempi:
- `t_output_contract.py` - Testa il contratto di output directory
- `t_loader_formats.py` - Testa estrazione testo da vari formati
- `t_determinism.py` - Testa determinismo di ID
- `t_fail_fast.py` - Testa comportamento fail-fast
- `t_safety_invariants.py` - Testa invarianti di sicurezza

---

## Esecuzione Test

### Esegui tutti i test
```bash
pytest test/ -v
```

### Esegui una categoria
```bash
pytest test/contract/ -v      # Solo contract test
pytest test/e2e/ -v           # Solo end-to-end test
pytest test/unit/ -v          # Solo unit test
```

### Esegui un test specifico
```bash
pytest test/contract/t_output_contract.py -v
```

### Con coverage
```bash
pytest test/ --cov=core.ingestion
```

---

## Test Critici (Deve Passare Sempre)

### 1. **t_output_contract.py**
**COSA**: Verifica che la directory di output abbia la struttura corretta
**PERCHÉ**: Sistemi downstream si basano su questa struttura
**INPUT**: Due documenti di test (TXT, HTML)
**ATTESO**: 
- `manifest.json` esiste in root
- Ogni documento ha directory propria `output_dir/<DOC_ID>/`
- Nessun file loose nella root (tutto in subdirectory)

**FALLIMENTO**: 
❌ Documento nella root di output_dir
❌ File manifest.json mancante
❌ Doc ID directory non contiene expected files

---

### 2. **t_loader_formats.py**
**COSA**: Verifica estrazione testo da HTML, TXT, XML, JSON
**PERCHÉ**: Qualità estrazione determina qualità dei risultati downstream
**INPUT**: File validi e malformati per ogni formato
**ATTESO**:
- HTML: Testo estratto senza tag, script/style rimossi
- TXT: Testo decodificato con UTF-8 (fallback latin-1)
- XML: Testo estratto da foglie, whitespace normalizzato
- JSON: Pretty-printed per leggibilità

**FALLIMENTO**:
❌ HTML vuoto ingerito con successo
❌ Script tag non rimosso da HTML
❌ File corrotto crasha loader

---

### 3. **t_fail_fast.py**
**COSA**: Verifica comportamento FAIL-FAST
**PERCHÉ**: Previene passaggio di documenti invalidi downstream
**INPUT**: Documento valido, vuoto, corrotto
**ATTESO**:
- Documento valido: ingerito con successo
- Documento vuoto: FALLATO esplicitamente nel manifest
- Documento corrotto: FALLATO con errore registrato

**FALLIMENTO**:
❌ Documento senza contenuto ingerito con successo
❌ Manifest non registra fallimenti
❌ Documento corrotto ignoto

---

### 4. **t_determinism.py**
**COSA**: Verifica che stesso contenuto produce stesso ID
**PERCHÉ**: Consente deduplicazione tra ingestioni multiple
**INPUT**: Stesso contenuto, path diversi
**ATTESO**:
- Stessa file 2x → STESSO ID
- Stessa content, path diverso → STESSO ID
- ID è content-based, non path-based

**FALLIMENTO**:
❌ ID randomico (ogni volta diverso)
❌ ID basato su path
❌ Stessa content ha ID diversi

---

### 5. **t_safety_invariants.py**
**COSA**: Verifica che il sistema NON faccia cose pericolose
**PERCHÉ**: Protegge contro regressioni di sicurezza
**INVARIANTI**:
- ✅ Raw bytes non modificati (hash uguale)
- ✅ Nessun codice eseguito da documenti HTML
- ✅ Metadata non inventato (solo da file trovati)
- ✅ Nessun file perso (rimangono in output)
- ✅ Nessun directory traversal attack

**FALLIMENTO**:
❌ Raw bytes modificati
❌ Script tag eseguito da HTML
❌ Metadata inventato senza file sidecar

---

### 6. **t_yaml_config.py**
**COSA**: Verifica validazione configurazione YAML
**PERCHÉ**: Config è la single source of truth
**INPUT**: YAML valido, invalido, con tipi sbagliati
**ATTESO**:
- YAML valido → IngestConfig costruito
- Campi mancanti → default applicati
- Config.validate() ritorna [] (no errors)

**FALLIMENTO**:
❌ YAML invalido caricato senza errore
❌ Tipo sbagliato accettato
❌ validate() non cattura errori

---

### 7. **t_metadata_sidecar.py**
**COSA**: Verifica scoperta e caricamento metadata sidecar
**PERCHÉ**: Metadata è associato automaticamente ai documenti
**INPUT**: Documento + sidecar valido, malformato, mancante
**ATTESO**:
- File document.json trovato e caricato
- JSON malformato → metadata=None (no crash)
- File mancante → metadata=None (non inventato)

**FALLIMENTO**:
❌ Metadata trovato quando non dovrebbe
❌ Metadata non trovato quando dovrebbe
❌ Documento fallisce causa metadata invalido

---

### 8. **t_ingestion_e2e.py**
**COSA**: Ingestione completa di `ingestion_test_data/raw`
**PERCHÉ**: Verifica che intero pipeline funziona
**INPUT**: Dati reali con HTML, TXT, PDF, XML, ZIP
**ATTESO**:
- >= 50 documenti ingestiti
- Success rate >= 90%
- manifest.json valido e completo
- Tutte output directory strutturate correttamente

**FALLIMENTO**:
❌ Meno di 50 documenti ingestiti
❌ Success rate < 90%
❌ manifest.json non trovato
❌ Errore non-handled durante ingestione

---

## Struttura di un Test

Ogni test file deve contenere:

1. **Docstring estensivo in italiano** che spiega:
   - COSA FA IL TEST
   - QUALE PARTE DEL SISTEMA VERIFICA
   - QUALI INPUT UTILIZZA
   - QUALE OUTPUT È ATTESO (SUCCESSO)
   - QUALE OUTPUT / ERRORE È ATTESO (FALLIMENTO)
   - PERCHÉ QUESTO TEST È IMPORTANTE

2. **Fixture pytest** per setup/teardown

3. **Test methods** che:
   - Hanno nomi descrittivi (`test_<behavior>`)
   - Contengono docstring breve
   - Falliscono loudly con assert message chiaro
   - Non hanno effetti collaterali

Esempio:

```python
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
    assert isinstance(manifest_data["documents"], list), \
        "documents deve essere una lista"
    assert len(manifest_data["documents"]) > 0, \
        "manifest contiene 0 documenti (dovrebbe averne almeno 1)"
```

---

## Coverage Target

La suite mira a coprire questi aspetti:

- ✅ Estrazione testo da tutti i formati supportati
- ✅ Comportamento fail-fast su documento invalido
- ✅ Deduplicazione (ID deterministici)
- ✅ Contratto di output directory
- ✅ Scoperta metadati sidecar
- ✅ Validazione configurazione YAML
- ✅ Invarianti di sicurezza
- ✅ Determinismo e reproducibilità
- ✅ End-to-end con dati reali
- ✅ Gestione errori robusto

---

## Debugging Test

### Se un test fallisce:

1. **Leggi il messaggio di errore** - Include il nome della assertion che è fallita

2. **Leggi il docstring del test** - Spiega COSA dovrebbe succedere

3. **Controlla il codice test** - Quale condition è falsa?

4. **Esegui il test in verbose**:
```bash
pytest test/contract/t_output_contract.py::TestOutputContract::test_output_directory_structure_exists -v -s
```

5. **Aggiungi debug print**:
```python
print(f"Debug: manifest_data = {manifest_data}")
```

6. **Esegui solo quel test**:
```bash
pytest test/contract/t_output_contract.py::TestOutputContract::test_output_directory_structure_exists -x
```

---

## Aggiungere Nuovi Test

Quando aggiungi una nuova feature:

1. **Scrivi un test PRIMA** (test-driven development)
2. **Nomina il file** `test/contract/t_<feature>.py`
3. **Aggiungi docstring estensivo** in italiano
4. **Includi fixture necessarie**
5. **Scrivi assertion con messaggi chiari**
6. **Esegui** `pytest test/ -v` per verificare

---

## Note Importanti

- ⚠️ **Test non devono modificare codice**: Testano, non risolvono
- ⚠️ **Falliscono loudly**: Messaggi di erro chiari, no silent failures
- ⚠️ **Isolati**: Non dipendono da test precedenti
- ⚠️ **Veloci**: E2E test ~ 60sec, altri < 5 sec
- ⚠️ **Deterministici**: Stessi input sempre stesso output

---

## CI/CD Integration

In futuro, questi test saranno integrati in CI/CD:

```yaml
# .github/workflows/test.yml
- run: pytest test/ -v --cov=core.ingestion
- run: pytest test/e2e/ -v  # Separato, più lento
```

Finché non è in CI, eseguirli localmente:

```bash
pytest test/ -v
```

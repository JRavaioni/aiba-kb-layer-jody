# Pipeline Ingestione Documenti

Modulo di ingestione documentale basato su configurazione YAML, pensato come primo stadio di una pipeline dati.

## Obiettivo

Standardizzare l'acquisizione documenti da filesystem e archivi ZIP, estrarre contenuto testuale, associare metadati sidecar, produrre output deterministico e verificabile.

---

## Caratteristiche Principali

- Ingestione multi-formato (HTML, TXT, JSON, XML, PDF).
- Gestione ZIP con estrazione controllata.
- Metadati sidecar JSON con strategie di ricerca configurabili.
- ID documento deterministico (content-based).
- Struttura output stabile con manifest.
- Gestione errori robusta a livello documento.

---

## Struttura Output

```text
output_directory/
  manifest.json
  <doc_id>/
    <doc_id>.<ext>
    extracted.txt
    rd_<doc_id>.json
    sc_<doc_id>.json
```

---

## Esecuzione Rapida

### Da riga di comando

```bash
python main.py --config config/ingest.yaml --output output_directory
```

### Da API

```python
from core.ingestion import create_ingest_service

service = create_ingest_service("config/ingest.yaml", "output_directory")
manifest = service.ingest("ingestion_test_data/raw")
print(manifest.success_count, manifest.error_count)
```

---

## Configurazione

La configurazione principale è in `config/ingest.yaml`.

Aree principali:
- `input`
- `zip_extraction`
- `loader`
- `metadata`
- `id_generation`
- `output`
- `analyzers`

Per il riferimento completo usare `docs_it/ingest-config-schema.md`.

---

## Test

Suite test in `test/` con naming `t_<keyword>.py`.

Comandi principali:

```bash
python -m pytest test/ --collect-only -q
pytest test/ -v
pytest test/contract/ -v
pytest test/e2e/ -v
```

---

## Documentazione Ufficiale

- `docs_it/README.md`
- `docs_it/QUICK_REFERENCE.md`
- `docs_it/architecture.md`
- `docs_it/ingest-config-schema.md`
- `docs_it/examples.md`
- `docs_it/TESTING.md`
- `docs_it/INVARIANTI.md`

---

## Stato Attuale

Ultima verifica operativa nota:
- Documenti ingestiti: 68
- Errori: 0
- Success rate: 100%

Sistema pronto all'uso, testabile e documentato in italiano.

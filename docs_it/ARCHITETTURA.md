# Architettura Sottosistema ID Generation

## Panoramica

Il sottosistema ID generation e stato esteso per supportare strategie hash, incrementali e composte con fallback.

Nota operativa: la pipeline non crea file `.keepme` e non mantiene logiche di autogenerazione placeholder nelle directory di output.

Componenti principali:
- `IDGenerationConfig` (tipi e parametri)
- `IDGeneratorFactory` (selezione strategia)
- `HashIDGenerator`
- `IncrementalIDGenerator`
- `CompoundIDGenerator`

Eccezioni specifiche:
- `InvalidIDGenerationConfig`
- `IDGenerationException`

## Flusso di Esecuzione

1. `IngestConfig.from_yaml()` legge `ingest.id_generation`.
2. `IngestConfig.from_dict()` normalizza e valida i parametri.
3. `IngestService.__init__()` passa `IDGenerationConfig` alla factory.
4. `IDGeneratorFactory.create()` costruisce il generatore corretto.
5. In fase `ingest()`, ogni documento genera `doc_id` con il generatore scelto.
6. `FilesystemBackend.persist()` usa `doc_id` per directory e artefatti:
   - `{doc_id}/`
   - `{doc_id}.{ext}`
   - `sc_{doc_id}.json`
   - `rd_{doc_id}.json`
   - `extracted.txt`

## Strategy Selection

- `hash_only`: usa solo hash SHA256 troncato.
- `incremental_only`: usa solo sequenziale (`PREFIX_000001`).
- `hash_then_incremental`: hash primario, incrementale fallback.
- `incremental_then_hash`: incrementale primario, hash fallback.

## Logging

- `DEBUG`: ID generati.
- `WARNING`: fallback da strategia primaria a secondaria.
- `ERROR`: configurazioni invalide o errori runtime.

## Backward Compatibility

- Default senza nuovi parametri:
  - `hash_length_bytes=16`
  - `naming_strategy=hash_only`
- Supporto mapping legacy per `strategy`:
  - `sha256-16` -> `hash_only` con 8 byte
  - `sha256-32` -> `hash_only` con 16 byte

## Estendibilita Futura

1. Persistenza stato del contatore incrementale tra run.
2. Strategie distribuite (snowflake, ULID, KSUID).
3. Namespace multi-tenant (`TENANT_DOC_000001`).
4. Policy di collision handling configurabili.
5. Strategie ibride legate a metadati (`prefix` dinamico per source).

## Invarianti

1. Ogni documento validamente ingestito ha un `doc_id` non vuoto.
2. Il `doc_id` usato in manifest coincide con quello nei path artifact.
3. Le eccezioni di configurazione sono intercettate prima della run.
4. Le strategie combinate richiedono entrambi i motori attivi.

# Configurazione ID Generation

## Obiettivo

La sezione `ingest.id_generation` controlla come viene generato `doc_id` durante l'ingestione.

## Nuova Sezione YAML

```yaml
ingest:
  id_generation:
    strategy: sha256-16
    prefix: ""
    suffix: ""
    hash_digits: 16
    hash_length_bytes: null
    naming_strategy: hash_only
    incremental_prefix: "DOC"
    incremental_pad_digits: 6
    enabled_hash: true
    enabled_incremental: false
```

## Parametri

| Parametro | Tipo | Default | Vincoli | Descrizione |
|---|---|---|---|---|
| `strategy` | string | `sha256-16` | `sha256-16`, `sha256-32` | Strategia SHA legacy mantenuta |
| `prefix` | string | `""` | libero | Prefisso per ID hash |
| `suffix` | string | `""` | libero | Suffisso per ID hash |
| `hash_digits` | int/null | `null` | `8..64`, pari | Numero esatto di caratteri hex del digest SHA256 |
| `hash_length_bytes` | int/null | `null` | `4..32` | Alternativa a `hash_digits`, lunghezza in byte |
| `naming_strategy` | string | `hash_only` | `hash_only`, `incremental_only`, `hash_then_incremental`, `incremental_then_hash` | Strategia di naming |
| `incremental_prefix` | string | `DOC` | libero | Prefisso per naming incrementale |
| `incremental_pad_digits` | int | `6` | `1..10` | Zeri a sinistra per contatore incrementale |
| `enabled_hash` | bool | `true` | - | Abilita generazione hash |
| `enabled_incremental` | bool | `false` | - | Abilita naming incrementale |

## Precedenza Parametri Hash

Quando la lunghezza dell'hash puo essere determinata da piu campi, viene applicata questa precedenza:

1. `hash_digits`
2. `hash_length_bytes`
3. `strategy` (`sha256-16` o `sha256-32`)

Comportamento dei warning (non bloccanti):

- Se sono impostati sia `hash_digits` sia `hash_length_bytes`: warning, usa `hash_digits`.
- Se e impostato solo `hash_digits`: warning, la lunghezza derivata da `strategy` viene ignorata.
- Se e impostato solo `hash_length_bytes`: warning, la lunghezza derivata da `strategy` viene ignorata.

Questi warning servono a segnalare configurazioni ambigue ma non interrompono la pipeline.

## Come Viene Creato il Nome Hash (bytes usati)

Il `doc_id` hash viene calcolato su `loaded.raw_bytes`, cioe sui byte binari del documento letto dal loader.

Dettaglio pratico:

1. Il loader legge il file sorgente e produce `raw_bytes` (contenuto binario originale del documento).
2. Il generatore calcola `sha256(raw_bytes)`.
3. Il digest hex viene troncato secondo la precedenza (`hash_digits` -> `hash_length_bytes` -> `strategy`).
4. Il nome finale hash diventa: `prefix + hash_troncato + suffix`.

Importante:

- Non vengono usati testo estratto, sidecar metadata o analyzer output per il calcolo hash.
- Per file dentro ZIP, i byte usati sono quelli del file estratto (non i byte del contenitore ZIP).
- A parita di byte in input, l'ID hash e deterministico.

Esempio concettuale per `sha256-16`:

- Input: `raw_bytes` del file.
- Digest completo: 64 caratteri hex.
- Output hash: primi 16 caratteri hex (se non ci sono override).
- `doc_id` finale: `prefix + <16 hex> + suffix`.

## Strategie a Confronto

| Strategia | Deterministica | Esempio output | Caso d'uso |
|---|---|---|---|
| `hash_only` | Si | `4f3c...` (hex) | Deduplica forte, run ripetibili |
| `incremental_only` | No (dipende dall'ordine di scansione) | `DOC_000001` | Output leggibile per utenti |
| `hash_then_incremental` | Si in condizioni normali | hash, fallback a `DOC_000001` | Preferisci stabilita hash con fallback operativo |
| `incremental_then_hash` | No in condizioni normali | `DOC_000001`, fallback hash | Preferisci leggibilita umana con fallback robusto |

## Esempi Completi

### 1) Solo hash (consigliato per produzione)

```yaml
ingest:
  id_generation:
    strategy: sha256-16
    prefix: ""
    suffix: ""
    hash_digits: 16
    hash_length_bytes: null
    naming_strategy: hash_only
    enabled_hash: true
    enabled_incremental: false
```

Esempio ID: `95fd9f6f95a89b7f`

### 2) Solo incrementale

```yaml
ingest:
  id_generation:
    naming_strategy: incremental_only
    incremental_prefix: "DOC"
    incremental_pad_digits: 6
    enabled_hash: false
    enabled_incremental: true
```

Esempio ID: `DOC_000001`, `DOC_000002`

### 3) Hash con fallback incrementale

```yaml
ingest:
  id_generation:
    strategy: sha256-16
    hash_digits: 16
    naming_strategy: hash_then_incremental
    incremental_prefix: "DOC"
    incremental_pad_digits: 6
    enabled_hash: true
    enabled_incremental: true
```

### 4) Incrementale con fallback hash

```yaml
ingest:
  id_generation:
    strategy: sha256-16
    hash_digits: 16
    naming_strategy: incremental_then_hash
    incremental_prefix: "DOC"
    incremental_pad_digits: 6
    enabled_hash: true
    enabled_incremental: true
```

## Backward Compatibility

Compatibilita mantenuta:
- `strategy`, `prefix`, `suffix` legacy sono supportati nativamente.
- Se non sono impostati override (`hash_digits`, `hash_length_bytes`), la lunghezza hash deriva da `strategy`.
- Se `naming_strategy` non e specificato: default `hash_only`.
- `sha256-16` e `sha256-32` continuano a funzionare come prima.

## Migrazione da Configurazioni Legacy

### Prima (legacy)

```yaml
ingest:
  id_generation:
    strategy: sha256-16
    prefix: "doc_"
    suffix: ""
```

### Dopo (nuovo schema)

```yaml
ingest:
  id_generation:
    strategy: sha256-16
    prefix: "doc_"
    suffix: ""
    hash_digits: 16
    hash_length_bytes: null
    naming_strategy: hash_only
    enabled_hash: true
    enabled_incremental: false
```

Nota: `sha256-16` corrisponde a 16 caratteri hex.

## Validazioni e Errori

Viene sollevata `InvalidIDGenerationConfig` nei casi principali:
- `enabled_hash=false` e `enabled_incremental=false`
- `strategy` non valido
- `hash_digits` fuori range `8..64` o dispari
- `hash_length_bytes` fuori range `4..32`
- `incremental_pad_digits` fuori range `1..10`
- `naming_strategy` non valido
- strategia combinata senza entrambi i motori abilitati

Viene sollevata `IDGenerationException` per errori runtime durante la generazione.

## Best Practice

1. Usa `hash_only` in produzione quando serve deduplicazione stabile.
2. Usa `incremental_only` solo se il naming leggibile e prioritario.
3. Per resilienza operativa usa una strategia combinata.
4. Mantieni `hash_length_bytes >= 16` per collision risk molto basso.
5. Tieni `incremental_pad_digits` coerente con il volume atteso.
6. Evita di impostare contemporaneamente `hash_digits` e `hash_length_bytes` se non necessario.

## Troubleshooting

- Errore: "both enabled_hash and enabled_incremental are false"
  - Imposta almeno uno tra `enabled_hash` e `enabled_incremental` a `true`.

- Errore: "hash_length_bytes must be between 4 and 32"
  - Correggi il valore nel range consentito.

- Errore: "hash_digits must be between 8 and 64" oppure "hash_digits must be an even number"
  - Imposta un valore valido, pari e nel range richiesto.

- Warning: "both hash_digits and hash_length_bytes are set"
  - Il sistema usa `hash_digits`. Rimuovi uno dei due parametri per evitare ambiguita.

- Errore: "naming_strategy=... requires ..."
  - Verifica coerenza tra strategia e flag `enabled_*`.

- Output inatteso in incrementale
  - Ricorda: il contatore incrementale dipende dall'ordine documenti nella singola run.

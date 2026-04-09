# Modulo Ingestione - Esempi

## Esempio 1: Ingestione Base (Raccomandato)

Il modo più semplice per ingestire documenti:

```python
from core.ingestion import create_ingest_service
from pathlib import Path

# Crea servizio da config YAML
service = create_ingest_service(
    config_path="config/ingest.yaml",
    output_dir="output/"
)

# Avvia ingestione
manifest = service.ingest(input_dir="input/")

# Verifica risultati
print(f"Documenti ingestiti con successo: {len(manifest.ingested)} documenti")
print(f"Errori: {len(manifest.errors)} documenti")
print(f"Tasso successo: {manifest.success_rate:.1f}%")

# Ispeziona risultati
for logical_path, doc_id in manifest.ingested.items():
    print(f"  {logical_path} → {doc_id}")
```

## Esempio 2: Utilizzo da Riga di Comando con YAML

```bash
# Le cartelle di input sono definite nel file YAML
python main.py --config config/ingest.yaml --output output/

# Con configurazione personalizzata
python main.py --config my_config.yaml --output results/
```

## Esempio 3: Configurazione con Più Cartelle di Input

```yaml
ingest:
  input:
    dirs:
      - "documents/current/"
      - "documents/archive/"
      - "/external/shared/docs/"
    supported_formats: [pdf, docx, html]
    max_depth: 5
```

## Esempio 4: Pattern Builder (Avanzato)

Per più controllo, usa il builder:

```python
from core.ingestion import IngestBuilder
from pathlib import Path

# Crea da config
builder = IngestBuilder.from_config("config/ingest.yaml")

# Personalizza
builder.with_output_dir("output/")
builder.with_config_value("input.max_depth", 20)
builder.with_config_value("loader.max_text_length", 500000)
builder.enable_analyzers(False)

# Costruisci e avvia
service = builder.build()
manifest = service.ingest("input/")
```

## Esempio 3: Configurazione Minimale

```python
from core.ingestion import IngestBuilder

# Crea con valori predefiniti
service = (
    IngestBuilder.default()
    .with_output_dir("output/")
    .with_config_value("input.supported_formats", ["pdf"])
    .with_config_value("input.max_depth", 5)
    .build()
)

manifest = service.ingest("input/")
```

## Esempio 4: Configurazione Dizionario Personalizzato

```python
from core.ingestion import IngestBuilder

# Definisci config come dizionario
config_dict = {
    "ingest": {
        "input": {
            "supported_formats": ["pdf", "docx"],
            "max_depth": 10,
        },
        "id_generation": {
            "strategy": "sha256-16",
            "prefix": "doc_",
        },
        "output": {
            "backend": "filesystem",
        },
    }
}

# Crea servizio da dizionario
service = (
    IngestBuilder.from_dict(config_dict)
    .with_output_dir("output/")
    .build()
)

manifest = service.ingest("input/")
```

## Esempio 5: Configurazione Basata su Ambiente

```python
import os
from pathlib import Path
from core.ingestion import create_ingest_service

# Leggi da ambiente
input_dir = os.getenv("INPUT_DIR", "./input")
output_dir = os.getenv("OUTPUT_DIR", "./output")
config_file = os.getenv("INGEST_CONFIG", "./config/ingest.yaml")

# Crea e avvia
service = create_ingest_service(config_file, output_dir)
manifest = service.ingest(input_dir)

# Log risultati
with open("ingest_report.txt", "w") as f:
    f.write(f"Input: {input_dir}\n")
    f.write(f"Output: {output_dir}\n")
    f.write(f"Ingestiti: {len(manifest.ingested)}\n")
    f.write(f"Errori: {len(manifest.errors)}\n")
```

## Esempio 6: Elaborazione Output Manifest

```python
import json
from core.ingestion import create_ingest_service

service = create_ingest_service("config/ingest.yaml", "output/")
manifest = service.ingest("input/")

# Accedi manifest programmaticamente
print(f"Documenti totali elaborati: {manifest.total_input}")
print(f"Tasso successo: {manifest.success_rate:.1f}%")

# Itera ingestioni riuscite
for logical_path, doc_id in manifest.ingested.items():
    doc_dir = f"output/{doc_id}"
    print(f"\nDocumento: {logical_path}")
    print(f"  ID: {doc_id}")
    print(f"  Dir: {doc_dir}")
    
    # Leggi metadati
    with open(f"{doc_dir}/metadata.json") as f:
        metadata = json.load(f)
        print(f"  Dimensione: {metadata['source_file_size']} byte")
        print(f"  Formato: {metadata['format'].upper()}")
        print(f"  Lunghezza testo: {metadata['extracted_text_length']} caratteri")
        if metadata.get('sidecar_metadata'):
            print(f"  Ha metadati sidecar: Sì")

# Verifica errori
if manifest.errors:
    print("\nErrori:")
    for logical_path, error_msg in manifest.errors.items():
        print(f"  {logical_path}: {error_msg}")

# Salva manifest per reporting
manifest_dict = manifest.to_dict()
with open("output/manifest.json", "w") as f:
    json.dump(manifest_dict, f, indent=2)
```

## Esempio 7: Struttura Documento Dopo Ingestione

Dopo aver eseguito l'ingestione, la tua directory output appare così:

```
output/
  manifest.json                    # Riassunto ingestione
  b784e2c8dbba8d15/                # Una directory per documento
    b784e2c8dbba8d15.html          # File originale
    sc_b784e2c8dbba8d15.json       # Metadati sidecar
    rd_b784e2c8dbba8d15.json       # Documenti correlati
```

Dove `metadata.json` contiene:
```json
{
  "doc_id": "b784e2c8dbba8d15",
  "logical_path": "path/to/file.pdf",
  "basename": "file",
  "format": "pdf",
  "extracted_text_length": 45230,
  "pages_count": 12,
  "source_file_hash": "a1b2c3d4e5f6g7h8...",
  "source_file_size": 1024000,
  "ingested_at": "2024-01-15T10:30:45.123456",
  "sidecar_metadata": { ...metadati dal file .json accoppiato... },
  "analyzer_output": { ...risultati dalla pipeline analizzatore... }
}
```

## Esempio 8: Registra Generatore ID Personalizzato

```python
from core.ingestion import (
    IngestBuilder,
    IDGenerator,
    IDGeneratorFactory,
)

class GeneratoreIDPersonalizzato(IDGenerator):
    """Strategia generazione ID personalizzata."""
    
    def generate(self, file_bytes: bytes) -> str:
        # La tua logica personalizzata qui
        hash_val = hashlib.sha1(file_bytes).hexdigest()[:8]
        return f"custom_{hash_val}"

# Registra generatore personalizzato
IDGeneratorFactory.register("custom", GeneratoreIDPersonalizzato)

# Usa in builder
config_dict = {
    "ingest": {
        "id_generation": {"strategy": "custom"},
    }
}

service = (
    IngestBuilder.from_dict(config_dict)
    .with_output_dir("output/")
    .build()
)
```

## Esempio 9: Disabilita Analizzatori

```python
from core.ingestion import IngestBuilder

service = (
    IngestBuilder.from_config("config/ingest.yaml")
    .with_output_dir("output/")
    .enable_analyzers(False)  # Salta tutti analizzatori
    .build()
)

manifest = service.ingest("input/")
```

## Esempio 10: Utilizzo Command-Line

Crea `ingest.py`:

```python
#!/usr/bin/env python
"""Tool ingestione command-line."""

import argparse
from pathlib import Path
from core.ingestion import create_ingest_service

def main():
    parser = argparse.ArgumentParser(description="Tool ingestione documenti")
    parser.add_argument("input_dir", help="Directory input")
    parser.add_argument("--output", default="output/", help="Directory output")
    parser.add_argument("--config", default="config/ingest.yaml", help="File config")
    parser.add_argument("--no-analyzers", action="store_true", help="Disabilita analizzatori")
    
    args = parser.parse_args()
    
    # Crea servizio
    service = create_ingest_service(args.config, args.output)
    
    # Avvia
    print(f"Ingestendo da: {args.input_dir}")
    manifest = service.ingest(args.input_dir)
    
    # Report
    print(f"\nRisultati:")
    print(f"  Ingestiti: {len(manifest.ingested)}")
    print(f"  Errori: {len(manifest.errors)}")
    print(f"  Tasso successo: {manifest.success_rate:.1f}%")

if __name__ == "__main__":
    main()
```

Utilizzo:
```bash
python ingest.py ./documents --output ./output --config ./config/ingest.yaml
```

---

**Hai bisogno di più aiuto?** Vedi `docs/ingest-config-schema.md` per riferimento configurazione completo.
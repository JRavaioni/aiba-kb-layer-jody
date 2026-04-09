"""Contract tests for sidecar metadata discovery and loading."""

import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.sidecar import MetadataLoader
from core.ingestion.config import MetadataConfig, MetadataSearchStrategy


class TestMetadataSidecar:
    @staticmethod
    def _config() -> MetadataConfig:
        return MetadataConfig(
            enabled=True,
            base_paths=["."],
            search_strategies=[
                MetadataSearchStrategy(
                    name="exact_match",
                    description="Exact basename.json",
                    rule="{basename}.json",
                ),
                MetadataSearchStrategy(
                    name="wildcard",
                    description="Any json in directory",
                    rule="*.json",
                ),
            ],
        )

    def test_find_sidecar_metadata_exact_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            doc_file = tmpdir / "documento.txt"
            doc_file.write_text("Contenuto documento", encoding="utf-8")

            metadata_file = tmpdir / "documento.json"
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump({"autore": "Test User", "data": "2024-01-01"}, f)

            loader = MetadataLoader(self._config(), [tmpdir])
            loaded_metadata = loader.load(doc_file)

            assert loaded_metadata is not None
            assert loaded_metadata["autore"] == "Test User"
            assert loaded_metadata["data"] == "2024-01-01"

    def test_no_sidecar_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            doc_file = tmpdir / "documento_senza_meta.txt"
            doc_file.write_text("Contenuto documento", encoding="utf-8")

            loader = MetadataLoader(self._config(), [tmpdir])
            assert loader.load(doc_file) is None

    def test_malformed_sidecar_json_fails_gracefully(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            doc_file = tmpdir / "documento.txt"
            doc_file.write_text("Contenuto documento", encoding="utf-8")

            metadata_file = tmpdir / "documento.json"
            metadata_file.write_text("{invalid json content}", encoding="utf-8")

            loader = MetadataLoader(self._config(), [tmpdir])
            assert loader.load(doc_file) is None

"""End-to-end tests for ingestion with real sample data."""

import json
import tempfile
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.config import IngestConfig
from core.ingestion.ingest_service import IngestService


class TestIngestionE2E:
    @staticmethod
    def _service(output_dir: Path, input_dir: Path) -> IngestService:
        config = IngestConfig.from_yaml(Path("config/ingest.yaml"))
        config.input.dirs = [str(input_dir)]
        config.input.supported_formats = [f for f in config.input.supported_formats if f != "doc"]
        return IngestService(config, output_dir)

    def test_ingest_real_data(self):
        input_dir = Path("ingestion_test_data/raw")
        if not input_dir.exists():
            pytest.skip("ingestion_test_data/raw non trovato")

        with tempfile.TemporaryDirectory() as output:
            output_dir = Path(output)
            service = self._service(output_dir, input_dir)
            manifest = service.ingest(input_dir)

            assert len(manifest.ingested) >= 50
            assert manifest.success_rate >= 90.0

            manifest_file = output_dir / "manifest.json"
            assert manifest_file.exists()

    def test_ingest_produces_valid_manifest(self):
        input_dir = Path("ingestion_test_data/raw")
        if not input_dir.exists():
            pytest.skip("ingestion_test_data/raw non trovato")

        with tempfile.TemporaryDirectory() as output:
            output_dir = Path(output)
            service = self._service(output_dir, input_dir)
            manifest = service.ingest(input_dir)

            manifest_file = output_dir / "manifest.json"
            with open(manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert "ingested" in data
            assert "errors" in data
            assert "summary" in data
            assert data["summary"]["total_input"] == (len(manifest.ingested) + len(manifest.errors))

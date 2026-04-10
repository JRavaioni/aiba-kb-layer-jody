"""Contract tests for output directory composition and manifest structure."""

import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.config import IngestConfig
from core.ingestion.ingest_service import IngestService


class TestOutputContract:
    @staticmethod
    def _create_service(input_dir: Path, output_dir: Path) -> IngestService:
        config = IngestConfig.from_yaml(Path("config/ingest.yaml"))
        config.input.dirs = [str(input_dir)]
        return IngestService(config, output_dir)

    def test_output_directory_structure_exists(self):
        with tempfile.TemporaryDirectory() as tmp_in, tempfile.TemporaryDirectory() as tmp_out:
            input_dir = Path(tmp_in)
            output_dir = Path(tmp_out)

            (input_dir / "a.txt").write_text("hello", encoding="utf-8")
            (input_dir / "b.html").write_text("<html><body>ciao mondo</body></html>", encoding="utf-8")

            service = self._create_service(input_dir, output_dir)
            manifest = service.ingest(input_dir)

            manifest_path = output_dir / "manifest.json"
            assert manifest_path.exists()
            assert len(manifest.ingested) >= 2

            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert "ingested" in data
            assert "errors" in data
            assert "summary" in data
            assert data["summary"]["successfully_ingested"] >= 2

    def test_each_document_has_own_directory(self):
        with tempfile.TemporaryDirectory() as tmp_in, tempfile.TemporaryDirectory() as tmp_out:
            input_dir = Path(tmp_in)
            output_dir = Path(tmp_out)
            (input_dir / "doc.txt").write_text("content", encoding="utf-8")

            service = self._create_service(input_dir, output_dir)
            manifest = service.ingest(input_dir)

            assert len(manifest.ingested) == 1
            doc_id = next(iter(manifest.ingested.values()))
            doc_dir = output_dir / doc_id
            assert doc_dir.exists() and doc_dir.is_dir()
            assert any(doc_dir.iterdir())

    def test_no_loose_documents_in_root(self):
        with tempfile.TemporaryDirectory() as tmp_in, tempfile.TemporaryDirectory() as tmp_out:
            input_dir = Path(tmp_in)
            output_dir = Path(tmp_out)
            (input_dir / "doc.txt").write_text("content", encoding="utf-8")

            service = self._create_service(input_dir, output_dir)
            service.ingest(input_dir)

            root_files = [p.name for p in output_dir.iterdir() if p.is_file()]
            assert sorted(root_files) == ["manifest.json"]

    def test_document_file_naming_convention(self):
        with tempfile.TemporaryDirectory() as tmp_in, tempfile.TemporaryDirectory() as tmp_out:
            input_dir = Path(tmp_in)
            output_dir = Path(tmp_out)
            (input_dir / "doc.txt").write_text("content", encoding="utf-8")

            service = self._create_service(input_dir, output_dir)
            manifest = service.ingest(input_dir)

            doc_id = next(iter(manifest.ingested.values()))
            doc_dir = output_dir / doc_id
            files = {f.name for f in doc_dir.iterdir()}

            assert f"sc_{doc_id}.json" in files
            assert f"rd_{doc_id}.json" in files

"""Safety invariants tests for ingestion and metadata handling."""

import hashlib
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.ingestion.loader import DocumentLoader
from core.ingestion.config import LoaderConfig, MetadataConfig, MetadataSearchStrategy
from core.ingestion.sidecar import MetadataLoader
from core.ingestion.types import DocumentRef


class TestSafetyInvariants:
    def test_raw_bytes_never_modified(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_file = tmpdir / "original.txt"
            original_content = b"Contenuto originale da preservare esattamente"
            test_file.write_bytes(original_content)

            original_hash = hashlib.sha256(original_content).hexdigest()

            loader = DocumentLoader(
                LoaderConfig(
                    pdf_extract_text=True,
                    max_text_length=100000,
                    encoding_fallback=["utf-8"],
                )
            )

            file_ref = DocumentRef(
                real_path=test_file,
                logical_path="original.txt",
                format="txt",
                basename="original",
            )

            loaded = loader.load(file_ref)
            extracted_hash = hashlib.sha256(loaded.raw_bytes).hexdigest()
            assert original_hash == extracted_hash

    def test_metadata_not_invented(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            doc = tmpdir / "senza_metadata.txt"
            doc.write_text("Documento senza file di metadata", encoding="utf-8")

            config = MetadataConfig(
                enabled=True,
                base_paths=["."],
                search_strategies=[
                    MetadataSearchStrategy(
                        name="exact_match",
                        description="Exact match",
                        rule="{basename}.json",
                    )
                ],
            )

            loader = MetadataLoader(config, [tmpdir])
            metadata = loader.load(doc)
            assert metadata is None

    def test_no_code_execution_during_html_loading(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            html_file = tmpdir / "malicious.html"
            html_file.write_text(
                "<html><body><p>safe</p><script>window.pwned=true;</script></body></html>",
                encoding="utf-8",
            )

            loader = DocumentLoader(
                LoaderConfig(
                    pdf_extract_text=True,
                    max_text_length=100000,
                    encoding_fallback=["utf-8"],
                )
            )

            file_ref = DocumentRef(
                real_path=html_file,
                logical_path="malicious.html",
                format="html",
                basename="malicious",
            )

            loaded = loader.load(file_ref)
            assert loaded.extracted_text is not None
            # Loader is minimal now: HTML is decoded, not executed.
            assert "window.pwned" in loaded.extracted_text

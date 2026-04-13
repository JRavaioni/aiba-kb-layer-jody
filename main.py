#!/usr/bin/env python3
"""
Main entry point for the document ingestion pipeline.

This script loads configuration, validates it, initializes ingestion components,
and executes the ingestion process on the input directories specified in YAML.

Usage:
    python main.py [--config CONFIG_FILE] [--output OUTPUT_DIR]

Example:
    python main.py --config config/ingest.yaml --output output/
"""

import sys
from pathlib import Path
import logging

# Add project root to Python path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import argparse
from core.ingestion import IngestBuilder, IngestConfig

log = logging.getLogger(__name__)
step_log = logging.getLogger("pipeline.steps")


def _setup_logging(config: IngestConfig, output_dir: Path) -> Path:
    """Configure simplified operational logging for console and file output."""
    level_name = (config.logging.level or "INFO").upper()
    step_level = getattr(logging, level_name, logging.INFO)

    root_logger = logging.getLogger()
    # Keep detailed third-party/module logs quiet by default.
    root_logger.setLevel(logging.ERROR)

    # Replace existing handlers to avoid duplicated log lines on repeated runs.
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    configured_log_path = config.logging.file
    if configured_log_path:
        log_path = Path(configured_log_path)
        if not log_path.is_absolute():
            log_path = project_root / log_path
    else:
        log_path = Path(output_dir) / "ingestion.log"

    log_path.parent.mkdir(parents=True, exist_ok=True)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(step_level)
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(step_level)
    file_handler.setFormatter(formatter)

    # Dedicated logger for high-level operational steps.
    step_logger = logging.getLogger("pipeline.steps")
    step_logger.setLevel(step_level)
    step_logger.propagate = False
    step_logger.handlers.clear()
    step_logger.addHandler(stream_handler)
    step_logger.addHandler(file_handler)

    # Keep ingestion internals enabled for manifest warning capture,
    # but not noisy on console/file because root is set to ERROR.
    logging.getLogger("core.ingestion").setLevel(logging.INFO)

    logging.captureWarnings(True)
    return log_path


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Document Ingestion Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py
  python main.py --config my_config.yaml --output results/
        """
    )

    parser.add_argument(
        "--config",
        default="config/ingest.yaml",
        help="Path to YAML configuration file (default: config/ingest.yaml)"
    )

    parser.add_argument(
        "--output",
        default="output/",
        help="Output directory for ingested documents (default: output/)"
    )

    args = parser.parse_args()

    try:
        # Load configuration first to get input directories
        print(f"Loading configuration from: {args.config}")
        config = IngestConfig.from_yaml(args.config)
        output_dir = Path(args.output)
        log_path = _setup_logging(config, output_dir)
        step_log.info(
            f"STEP logging_setup status=SUCCESS level={config.logging.level} file={log_path}"
        )
        
        # Get input directories from configuration
        input_dirs = config.input.dirs
        if not input_dirs:
            step_log.error(
                "STEP config_validation status=FAILED entity=config reason=no_input_directories"
            )
            sys.exit(1)
        
        step_log.info("STEP config_load status=SUCCESS")
        
        # Create ingestion service
        service = (
            IngestBuilder(config)
            .with_output_dir(output_dir)
            .build()
        )

        # Validate configuration (handled by create_ingest_service)
        step_log.info("STEP config_validation status=SUCCESS")

        # Initialize ingestion components (handled by service creation)
        step_log.info("STEP service_init status=SUCCESS")

        # Execute ingestion for each input directory
        total_manifest = None
        
        for input_dir in input_dirs:
            input_path = Path(input_dir)
            if not input_path.exists():
                step_log.warning(
                    f"STEP input_check status=WARNING entity=input_directory file={input_dir} reason=not_found"
                )
                continue
                
            step_log.info(f"STEP ingest_start status=SUCCESS file={input_dir}")
            manifest = service.ingest(input_path)
            
            # Merge manifests if multiple directories
            if total_manifest is None:
                total_manifest = manifest
            else:
                # Merge ingested documents
                total_manifest.ingested.update(manifest.ingested)
                # Merge errors
                total_manifest.errors.update(manifest.errors)
                # Keep the merged manifest timestamps coherent.
                total_manifest.completed_at = manifest.completed_at
                total_manifest.duplicates_found += manifest.duplicates_found

        if total_manifest is None:
            step_log.error(
                "STEP ingest status=FAILED entity=input_directory reason=no_valid_input_directory"
            )
            sys.exit(1)

        # Report results
        outcome = "SUCCESS" if not total_manifest.errors else "WARNING"
        step_log.info(
            "STEP ingest_complete status=%s ingested=%s errors=%s warnings=%s success_rate=%.1f",
            outcome,
            len(total_manifest.ingested),
            len(total_manifest.errors),
            total_manifest.total_warnings,
            total_manifest.success_rate,
        )

        # Exit with success/failure code
        if total_manifest.errors:
            sys.exit(1)  # Non-zero exit for errors
        else:
            sys.exit(0)

    except FileNotFoundError as e:
        step_log.error(
            f"STEP config_load status=FAILED entity=config_file file={args.config} reason={e}"
        )
        sys.exit(1)
    except Exception as e:
        step_log.error(f"STEP ingest status=FAILED entity=pipeline reason={e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
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

# Add project root to Python path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import argparse
from core.ingestion import create_ingest_service, IngestConfig


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
        
        # Get input directories from configuration
        input_dirs = config.input.dirs
        if not input_dirs:
            print("Error: No input directories specified in configuration (ingest.input.dirs)")
            sys.exit(1)
        
        print(f"Input directories from config: {input_dirs}")
        
        # Create ingestion service
        service = create_ingest_service(args.config, args.output)

        # Validate configuration (handled by create_ingest_service)
        print("Configuration validated successfully")

        # Initialize ingestion components (handled by service creation)
        print("Ingestion components initialized")

        # Execute ingestion for each input directory
        total_manifest = None
        
        for input_dir in input_dirs:
            input_path = Path(input_dir)
            if not input_path.exists():
                print(f"Warning: Input directory does not exist: {input_dir}")
                continue
                
            print(f"\nStarting ingestion from: {input_dir}")
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
            print("No valid input directories found. Exiting.")
            sys.exit(1)

        # Report results
        print("\nIngestion completed:")
        print(f"  Success rate: {total_manifest.success_rate:.1f}%")
        print(f"  Documents ingested: {len(total_manifest.ingested)}")
        print(f"  Errors encountered: {len(total_manifest.errors)}")

        if total_manifest.ingested:
            print("\nIngested documents:")
            for logical_path, doc_id in total_manifest.ingested.items():
                print(f"  {logical_path} → {doc_id}")

        if total_manifest.errors:
            print("\nErrors:")
            for logical_path, error in total_manifest.errors.items():
                print(f"  {logical_path}: {error}")

        # Exit with success/failure code
        if total_manifest.errors:
            sys.exit(1)  # Non-zero exit for errors
        else:
            sys.exit(0)

    except FileNotFoundError as e:
        print(f"Configuration file not found: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Ingestion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
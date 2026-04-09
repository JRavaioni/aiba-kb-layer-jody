"""Workspace-wide Python startup customizations.

This file is auto-imported by Python's site module when running from this
workspace root. We disable bytecode generation so __pycache__ and .pyc files
are not created.
"""

import sys

# Disable writing .pyc files and __pycache__ directories.
sys.dont_write_bytecode = True

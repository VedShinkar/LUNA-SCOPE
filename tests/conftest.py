"""Pytest configuration and fixtures for LUNA-SCOPE."""
from pathlib import Path
import sys

# Ensure backend directory is in sys.path for test execution
repo_root = Path(__file__).resolve().parent.parent
backend_dir = repo_root / "backend"

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

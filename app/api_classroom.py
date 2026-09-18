"""Portable interpreter entry point for classroom_service.api."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from classroom_service.api import main

if __name__ == "__main__":
    main()

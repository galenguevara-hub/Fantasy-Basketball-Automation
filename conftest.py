import sys
from pathlib import Path

# Make the fba package importable during pytest without requiring PYTHONPATH to be set.
sys.path.insert(0, str(Path(__file__).parent / "src"))

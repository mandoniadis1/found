"""Shared setup for the scripts: run them from the repo folder with the project venv, e.g. .venv/bin/python scripts/x.py"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)

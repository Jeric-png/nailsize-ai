import json
from pathlib import Path

from app.main import app

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "packages" / "contracts" / "openapi.json"
OUTPUT.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

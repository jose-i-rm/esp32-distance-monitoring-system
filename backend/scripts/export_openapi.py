"""Exporta la especificación OpenAPI de la aplicación a ../api/openapi.json.

Uso (desde backend/):
    python scripts/export_openapi.py
"""

import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.main import app  # noqa: E402

output = BACKEND_DIR.parent / "api" / "openapi.json"
output.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Especificación exportada en {output}")

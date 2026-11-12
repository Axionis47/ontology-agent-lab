import json
from pathlib import Path

from oak.main import app

target = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"
target.write_text(json.dumps(app.openapi(), indent=2) + "\n")
print(f"Exported {target.name}")

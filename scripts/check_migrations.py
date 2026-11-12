"""Keep applied migrations immutable and reject destructive schema operations."""

import re
import subprocess
import sys
from pathlib import Path

base = sys.argv[1]
root = Path("backend/migrations")
tracked = subprocess.run(
    ["git", "ls-tree", "-r", "--name-only", base, str(root)], capture_output=True, text=True
)
for name in tracked.stdout.splitlines():
    before = subprocess.check_output(["git", "show", f"{base}:{name}"])
    if not Path(name).exists() or Path(name).read_bytes() != before:
        raise SystemExit(f"Applied migration changed: {name}. Add a new migration.")
for path in root.glob("*.sql"):
    sql = re.sub(r"--[^\n]*|/\*.*?\*/", "", path.read_text(), flags=re.S)
    if re.search(r"\b(DROP|TRUNCATE|RENAME)\b|ALTER\s+COLUMN|SET\s+NOT\s+NULL", sql, re.I):
        raise SystemExit(f"Migration needs a separate compatibility plan: {path}")
print("Migration compatibility checks passed.")

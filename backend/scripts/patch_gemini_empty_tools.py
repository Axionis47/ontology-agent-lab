"""Fix the empty tool catalog in the project-local Gemini CLI 0.67.0 installation.

Vertex AI rejects a tool entry with no function declarations.
Keep nonempty tool catalogs unchanged. Back up each changed bundle once.
"""

import json
from pathlib import Path

package = Path(__file__).resolve().parents[1] / ".local/gemini-cli/node_modules/@google/gemini-cli"
metadata = json.loads((package / "package.json").read_text())
if metadata["version"] != "0.67.0":
    raise SystemExit("This patch applies only to Gemini CLI 0.67.0.")

replacements = {
    "const tools = [{ functionDeclarations: toolDeclarations }];": (
        "const tools = toolDeclarations.length ? [{ functionDeclarations: toolDeclarations }] : [];"
    ),
    "return [{ functionDeclarations: toolDeclarations2 }];": (
        "return toolDeclarations2.length ? [{ functionDeclarations: toolDeclarations2 }] : [];"
    ),
}
changed = 0
for path in (package / "bundle").glob("*.js"):
    original = path.read_text()
    updated = original
    for old, new in replacements.items():
        updated = updated.replace(old, new)
    if updated != original:
        backup = path.with_suffix(".js.oak-original")
        if not backup.exists():
            backup.write_text(original)
        path.write_text(updated)
        changed += 1
print(f"Patched {changed} CLI bundles. Existing nonempty catalogs are unchanged.")

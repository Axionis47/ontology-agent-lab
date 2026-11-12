"""Keep JSON arrays and primitives as MCP text in the local Gemini CLI 0.67.0.

MCP structuredContent must be an object. Do not change the existing MCP servers.
Back up each changed bundle before this patch.
"""

import json
from pathlib import Path

MARKER = "// OAK MCP content: promote JSON objects only."
OLD = """          const parsed = JSON.parse(firstItem.text);
          result2.structuredContent = parsed;"""
NEW = """          const parsed = JSON.parse(firstItem.text);
          // OAK MCP content: promote JSON objects only.
          if (parsed !== null && typeof parsed === "object" && !Array.isArray(parsed)) {
            result2.structuredContent = parsed;
          }"""


def main():
    package = (
        Path(__file__).resolve().parents[1] / ".local/gemini-cli/node_modules/@google/gemini-cli"
    )
    if json.loads((package / "package.json").read_text())["version"] != "0.67.0":
        raise SystemExit("This patch applies only to Gemini CLI 0.67.0.")
    changes, found = [], 0
    for path in (package / "bundle").glob("*.js"):
        original = path.read_text()
        if "var McpComplianceTransport = class" not in original:
            continue
        found += 1
        if MARKER in original:
            continue
        if original.count(OLD) != 1:
            raise SystemExit(f"The CLI content conversion does not match: {path.name}")
        updated = original.replace(OLD, NEW, 1)
        updated += "\nexport { McpComplianceTransport as oakMcpComplianceTransport };\n"
        changes.append((path, original, updated))
    if found != 3:
        raise SystemExit(f"Expected three CLI transport bundles. Found {found}.")
    for path, original, updated in changes:
        backup = path.with_suffix(".js.oak-before-mcp-content-patch")
        if not backup.exists():
            backup.write_text(original)
        path.write_text(updated)
    print(f"Patched {len(changes)} CLI bundles. JSON arrays remain MCP text.")


if __name__ == "__main__":
    main()

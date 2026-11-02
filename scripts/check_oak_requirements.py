"""Export with StrictDoc, then check typed parent cycles with stdlib graphlib."""

import argparse
import json
import subprocess
import sys
from graphlib import CycleError, TopologicalSorter
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("docs/oak/requirements"))
    parser.add_argument("--output-dir", type=Path, default=Path(".runtime/docs/strictdoc"))
    parser.add_argument(
        "--json-input", type=Path, help="Audit an existing native JSON export only."
    )
    args = parser.parse_args()
    json_path = args.json_input
    if json_path is None:
        result = subprocess.run(
            [
                str(Path(sys.executable).with_name("strictdoc")),
                "export",
                str(args.source),
                "--formats",
                "html,json",
                "--output-dir",
                str(args.output_dir),
                "--no-parallelization",
                "--config",
                str(args.source / "strictdoc_config.py"),
            ],
            check=False,
        )
        if result.returncode:
            return result.returncode
        json_path = args.output_dir / "json/index.json"

    exported = json.loads(json_path.read_text())
    pending = [node for doc in exported["DOCUMENTS"] for node in doc["NODES"]]
    parents = {}
    while pending:
        node = pending.pop()
        pending.extend(node.get("NODES", []))
        if "UID" in node:
            parents[node["UID"]] = {
                relation["VALUE"]
                for relation in node.get("RELATIONS", [])
                if relation["TYPE"] == "Parent"
            }
    try:
        tuple(TopologicalSorter(parents).static_order())
    except CycleError as error:
        print(f"Typed parent cycle rejected by graphlib: {error.args[1]}", file=sys.stderr)
        return 1
    print(f"Documentation graph is acyclic: {len(parents)} nodes, all parent roles.")
    print("This check does not verify service contracts or runtime behavior.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

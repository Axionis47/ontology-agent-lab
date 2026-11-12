"""Recover recorded token counts from an experiment's Gemini session log."""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from uuid import UUID

TOKEN_FIELDS = ("input", "output", "cached", "thoughts", "tool", "total")
LIMITATION = (
    "These counts cover completed model responses in the session transcript. "
    "Gemini CLI records usage after stream validation. An invalid stream can trigger "
    "a retry before its usage is recorded. These counts do not prove complete billed "
    "usage and do not include unobserved auxiliary requests. Do not release an unknown "
    "usage reservation from these counts alone."
)


def _known_logs(session_id, experiment_root):
    matches = []
    pattern = re.compile(r'"session_id"\s*:\s*"' + re.escape(session_id) + r'"')
    for name in ("cli-stdout.json", "cli-stderr.log", "episode.json", "result.json"):
        for path in experiment_root.rglob(name):
            if pattern.search(path.read_text(errors="replace")):
                matches.append(str(path.resolve()))
    return sorted(matches)


def _episode_mapping(episode_dir, experiment_root, transcript_root, projects_path):
    episode = Path(episode_dir).resolve()
    if not episode.is_relative_to(experiment_root.resolve()):
        raise ValueError("The episode directory is outside this experiment.")
    workspace = episode / "gemini-workspace"
    start_path, end_path = episode / "hook-config.json", episode / "result.json"
    if not start_path.is_file() or not end_path.is_file():
        raise ValueError("The episode has no recorded execution window.")
    projects_path = Path(projects_path or Path.home() / ".gemini/projects.json")
    projects = json.loads(projects_path.read_text()).get("projects", {})
    folder = projects.get(str(workspace))
    if not isinstance(folder, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", folder):
        raise ValueError("The exact experiment workspace has no valid Gemini project mapping.")
    directory = transcript_root / folder
    project_root_path = directory / ".project_root"
    if project_root_path.read_text().strip() != str(workspace):
        raise ValueError("The Gemini project root does not match this experiment workspace.")
    return {
        "episode_directory": str(episode),
        "workspace": str(workspace),
        "projects_path": str(projects_path),
        "project_root_path": str(project_root_path),
        "transcript_directory": str(directory),
        "project_hash": hashlib.sha256(str(workspace).encode()).hexdigest(),
        "execution_window": [start_path.stat().st_mtime, end_path.stat().st_mtime],
    }


def recover_session_usage(
    session_id, *, experiment_root=None, transcript_root=None, episode_dir=None, projects_path=None
):
    """Return observed CLI-style token statistics and evidence, without message text.

    Only filenames with the known session prefix are opened. The full session ID is
    checked in the header before subsequent transcript lines are read.
    """
    try:
        canonical = str(UUID(session_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Use a canonical session UUID.") from exc
    if canonical != session_id:
        raise ValueError("Use a canonical session UUID.")
    backend = Path(__file__).resolve().parents[2]
    experiment_root = Path(experiment_root or backend / ".local/ontology-experiments")
    transcript_root = Path(transcript_root or Path.home() / ".gemini/tmp")
    logs = _known_logs(session_id, experiment_root)
    mapping = None
    if episode_dir is not None:
        mapping = _episode_mapping(episode_dir, experiment_root, transcript_root, projects_path)
        paths = sorted(
            Path(mapping["transcript_directory"]).glob(f"chats/session-*-{session_id[:8]}.jsonl")
        )
    else:
        if not logs:
            raise ValueError("The session ID is not in this experiment's CLI logs.")
        paths = sorted(transcript_root.glob(f"*/chats/session-*-{session_id[:8]}.jsonl"))
    matched = []
    for path in paths:
        with path.open() as stream:
            first = json.loads(stream.readline())
            if first.get("sessionId") != session_id:
                continue
            if first.get("kind") != "main":
                raise ValueError("Only main experiment sessions are supported.")
            if mapping:
                start_time = datetime.fromisoformat(first["startTime"].replace("Z", "+00:00"))
                lower, upper = mapping["execution_window"]
                if (
                    first.get("projectHash") != mapping["project_hash"]
                    or start_time.tzinfo is None
                    or not lower <= start_time.timestamp() <= upper
                ):
                    raise ValueError("The transcript header does not match this episode execution.")
                mapping["header_time_verified"] = first["startTime"]
            matched.append((path, [json.loads(line) for line in stream if line.strip()]))
    if len(matched) != 1:
        raise ValueError("Expected one transcript with the exact experiment session ID.")
    path, rows = matched[0]
    latest, metered = {}, {}
    model_rows = 0
    for line, row in enumerate(rows, start=2):
        if row.get("type") != "gemini":
            continue
        model_rows += 1
        identifier = row.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("A model response has no stable response ID.")
        latest[identifier] = row
        if row.get("tokens") is None:
            continue
        tokens, model = row["tokens"], row.get("model")
        if not isinstance(model, str) or not model:
            raise ValueError("A metered response has no model name.")
        if not isinstance(tokens, dict) or any(
            type(tokens.get(key)) is not int or tokens[key] < 0 for key in TOKEN_FIELDS
        ):
            raise ValueError("A response has incomplete or invalid token counts.")
        if tokens["cached"] > tokens["input"] or tokens["total"] < (
            tokens["input"] + tokens["output"] + tokens["thoughts"]
        ):
            raise ValueError("A response has inconsistent token counts.")
        record = {"model": model, "tokens": {key: tokens[key] for key in TOKEN_FIELDS}}
        if identifier in metered and metered[identifier]["record"] != record:
            raise ValueError("Repeated response IDs contain different token counts or models.")
        metered[identifier] = {"record": record, "line": line}
    if not latest or set(latest) != set(metered):
        raise ValueError("The transcript has an unmetered model response.")
    models = {}
    for item in metered.values():
        model, tokens = item["record"]["model"], item["record"]["tokens"]
        totals = models.setdefault(
            model,
            {
                "tokens": dict.fromkeys(
                    ("input", "prompt", "candidates", "cached", "thoughts", "tool", "total"), 0
                )
            },
        )["tokens"]
        totals["input"] += tokens["input"] - tokens["cached"]
        totals["prompt"] += tokens["input"]
        totals["candidates"] += tokens["output"]
        for key in ("cached", "thoughts", "tool", "total"):
            totals[key] += tokens[key]
    return {
        "stats": {"models": models},
        "evidence": {
            "session_id": session_id,
            "transcript_path": str(path.resolve()),
            "experiment_logs": logs,
            "experiment_mapping": mapping,
            "source": "completed_response_tokens",
            "complete_billed_usage_verified": False,
            "unique_model_responses": len(metered),
            "duplicate_rows_discarded": model_rows - len(metered),
            "response_evidence": [
                {"response_id": identifier, "line": item["line"]}
                for identifier, item in metered.items()
            ],
            "limitation": LIMITATION,
        },
    }

import hashlib
import json
import os

import pytest

from .session_usage import recover_session_usage

SESSION = "54a29bf3-707d-4715-ae7d-273a2e923dca"


def setup_files(tmp_path, responses, header=None):
    experiments = tmp_path / "experiments"
    experiments.mkdir()
    (experiments / "cli-stderr.log").write_text(json.dumps({"session_id": SESSION}))
    transcripts = tmp_path / "transcripts"
    path = transcripts / "ours/chats/session-2026-11-08T05-01-54a29bf3.jsonl"
    path.parent.mkdir(parents=True)
    rows = [{"sessionId": header or SESSION, "kind": "main"}, *responses]
    path.write_text("\n".join(json.dumps(row) for row in rows))
    return {"experiment_root": experiments, "transcript_root": transcripts}


def response(identifier="response1", **updates):
    return {
        "type": "gemini",
        "id": identifier,
        "model": "gemini-3.8-flash",
        "content": "This content must not be returned.",
        "thoughts": ["This content must not be returned."],
        "tokens": {
            "input": 100,
            "output": 10,
            "cached": 60,
            "thoughts": 20,
            "tool": 0,
            "total": 130,
        },
        **updates,
    }


def test_deduplicates_response_upserts_and_returns_only_metadata(tmp_path):
    config = setup_files(tmp_path, [response(), response(), response("response2")])
    recovered = recover_session_usage(SESSION, **config)
    assert recovered["stats"]["models"]["gemini-3.8-flash"]["tokens"] == {
        "input": 80,
        "prompt": 200,
        "candidates": 20,
        "cached": 120,
        "thoughts": 40,
        "tool": 0,
        "total": 260,
    }
    assert recovered["evidence"]["unique_model_responses"] == 2
    assert recovered["evidence"]["duplicate_rows_discarded"] == 1
    assert not recovered["evidence"]["complete_billed_usage_verified"]
    assert "This content must not be returned" not in json.dumps(recovered)


def test_requires_experiment_scope_and_exact_full_header(tmp_path):
    config = setup_files(tmp_path, [response()], header="54a29bf3-0000-0000-0000-000000000000")
    with pytest.raises(ValueError, match="exact experiment session"):
        recover_session_usage(SESSION, **config)
    with pytest.raises(ValueError, match="not in this experiment"):
        recover_session_usage("f8032d3c-8dba-430b-bb10-389ac541cf7d", **config)
    with pytest.raises(ValueError, match="canonical"):
        recover_session_usage("../unrelated", **config)


def test_rejects_conflicting_usage_for_same_response(tmp_path):
    changed = response()
    changed["tokens"]["output"] = 11
    changed["tokens"]["total"] = 131
    config = setup_files(tmp_path, [response(), changed])
    with pytest.raises(ValueError, match="different token"):
        recover_session_usage(SESSION, **config)


def test_accepts_later_usage_update_but_rejects_unmetered_responses(tmp_path):
    config = setup_files(tmp_path, [response(tokens=None), response()])
    assert recover_session_usage(SESSION, **config)["evidence"]["unique_model_responses"] == 1
    path = next(config["transcript_root"].glob("*/chats/*"))
    with path.open("a") as stream:
        stream.write("\n" + json.dumps(response("unmetered", tokens=None)))
    with pytest.raises(ValueError, match="unmetered"):
        recover_session_usage(SESSION, **config)


def test_explicit_episode_mapping_requires_project_hash_and_execution_window(tmp_path):
    config = setup_files(tmp_path, [response()])
    (config["experiment_root"] / "cli-stderr.log").unlink()
    episode = config["experiment_root"] / "episode"
    workspace = episode / "gemini-workspace"
    workspace.mkdir(parents=True)
    for name, timestamp in (("hook-config.json", 1000), ("result.json", 2000)):
        path = episode / name
        path.write_text("{}")
        os.utime(path, (timestamp, timestamp))
    projects = tmp_path / "projects.json"
    projects.write_text(json.dumps({"projects": {str(workspace): "ours"}}))
    (config["transcript_root"] / "ours/.project_root").write_text(str(workspace))
    transcript = next(config["transcript_root"].glob("*/chats/*"))
    rows = [json.loads(line) for line in transcript.read_text().splitlines()]
    rows[0].update(
        projectHash=hashlib.sha256(str(workspace).encode()).hexdigest(),
        startTime="1970-01-01T00:25:00.000Z",
    )
    transcript.write_text("\n".join(json.dumps(row) for row in rows))
    extra = {"episode_dir": episode, "projects_path": projects}
    result = recover_session_usage(SESSION, **config, **extra)
    assert result["evidence"]["experiment_logs"] == []
    assert result["evidence"]["experiment_mapping"]["header_time_verified"]
    assert not result["evidence"]["complete_billed_usage_verified"]
    rows[0]["projectHash"] = "wrong-project"
    transcript.write_text("\n".join(json.dumps(row) for row in rows))
    with pytest.raises(ValueError, match="header does not match"):
        recover_session_usage(SESSION, **config, **extra)
    with pytest.raises(ValueError, match="outside this experiment"):
        recover_session_usage(SESSION, **config, episode_dir=tmp_path / "unrelated")

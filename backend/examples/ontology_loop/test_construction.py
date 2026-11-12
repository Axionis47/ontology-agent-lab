import json
from pathlib import Path

import pytest

from .construction import construct, repair_mutation, sample_cases
from .kernel import Candidate, load_cases


class Composer:
    mode = "scripted_test_only"

    def __init__(self, candidates, reviews):
        self.candidates = iter(candidates)
        self.reviews = iter(reviews)
        self.requests = []

    async def turn(self, prompt, history, tools):
        name = tools[0]["name"]
        self.requests.append({"name": name, "prompt": prompt, "history": history})
        value = next(self.candidates if name == "propose_kernel" else self.reviews)
        return [{"name": name, "arguments": json.dumps(value)}]


def seed():
    return Candidate.model_validate_json(Path(__file__).with_name("seed.json").read_text())


def review(blocking=False):
    return {"blocking": blocking, "summary": "Test review.", "findings": []}


def test_sampling_resamples_worlds_and_preserves_factor_comparison():
    cases = [{"name": f"case{i}", "family": f"family{i % 10}"} for i in range(24)]
    first = sample_cases(cases, "stratified", 1)
    second = sample_cases(cases, "stratified", 2)
    assert len(first) == len({case["family"] for case in first}) == 6
    assert first != second
    assert first == sample_cases(cases, "stratified", 1)


async def test_operator_failure_reaches_repair_and_freeze(tmp_path):
    candidate = seed()
    broken = candidate.model_dump(mode="json")
    broken["program"]["filters"] = broken["program"]["filters"][:-1]
    model = Composer([broken, candidate.model_dump(mode="json")], [review(True), review()])
    result = await construct(model, load_cases()["training"], tmp_path)
    assert result["candidate"].fingerprint == candidate.fingerprint
    assert result["report"]["status"] == "frozen"
    assert len(result["report"]["rounds"]) == 2
    assert not result["report"]["native_training_checked"]
    repair_payload = json.loads(model.requests[2]["history"][0]["content"])
    assert repair_payload["feedback"]["failed_cases"]
    assert repair_payload["feedback"]["failed_cases"][0]["result"]["operator_trace"]
    assert (tmp_path / "schema.owl").exists()
    assert (tmp_path / "events.jsonl").read_text().count('"kind": "request"') == 4
    with pytest.raises(ValueError, match="new directory"):
        await construct(model, load_cases()["training"], tmp_path)


async def test_judge_cannot_override_failed_training(tmp_path):
    broken = seed().model_dump(mode="json")
    broken["program"]["filters"] = []
    result = await construct(
        Composer([broken], [review()]), load_cases()["training"], tmp_path, max_rounds=1
    )
    assert result["candidate"] is None
    assert result["report"]["status"] == "not_frozen"
    assert not (tmp_path / "kernel.json").exists()


async def test_native_failure_is_logged_and_blocks_freeze(tmp_path):
    async def runner(candidate, case, path):
        return {"passed": False, "trace": [{"tool": "submit_answer", "result": "invalid"}]}

    candidate = seed()
    result = await construct(
        Composer([candidate.model_dump(mode="json")], [review()]),
        load_cases()["training"],
        tmp_path,
        max_rounds=1,
        trajectory_runner=runner,
    )
    assert result["candidate"] is None
    assert result["report"]["native_training_checked"]
    assert result["report"]["rounds"][0]["feedback"]["failed_native_runs"]


async def test_mutation_repair_is_labeled_separately(tmp_path):
    candidate = seed()
    model = Composer([candidate.model_dump(mode="json")], [review()])
    result = await repair_mutation(model, candidate, load_cases()["training"], tmp_path)
    assert result["report"]["repair_challenge"]
    assert result["candidate"].fingerprint == candidate.fingerprint
    payload = json.loads(model.requests[0]["history"][0]["content"])
    assert "evaluator removed" in payload["feedback"]["challenge"]


async def test_mutation_trajectory_is_given_to_composer(tmp_path):
    candidate = seed()

    async def runner(current, case, path):
        passed = current.fingerprint == candidate.fingerprint
        return {"passed": passed, "trace": [{"tool": "eligible_stays", "passed": passed}]}

    model = Composer([candidate.model_dump(mode="json")], [review()])
    result = await repair_mutation(
        model, candidate, load_cases()["training"], tmp_path, trajectory_runner=runner
    )
    assert result["report"]["native_training_checked"]
    payload = json.loads(model.requests[0]["history"][0]["content"])
    assert not payload["feedback"]["native_trajectories"][0]["passed"]
    assert payload["feedback"]["native_trajectories"][0]["trace"]
    assert all(run["passed"] for run in result["report"]["rounds"][0]["native_runs"])

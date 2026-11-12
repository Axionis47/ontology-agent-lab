import json

import pytest

from oak.ontology_verification import encode_ontology
from scripts import check_reasoner_resources as check
from scripts import reasoner_resource_probe as probe


def test_largest_resource_fixture_is_within_the_verified_profile():
    candidate = probe.maximum_schema()
    assert len(candidate["schema"]["entities"]) == 100
    assert sum(len(item["properties"]) for item in candidate["schema"]["entities"]) == 300
    assert len(candidate["schema"]["relations"]) == 200
    assert len(candidate["formal_axioms"]) == 200
    assert "FunctionalProperty" in encode_ontology(candidate)


def test_probe_refuses_a_different_resource_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "CGROUP", tmp_path)
    (tmp_path / "memory.max").write_text(str(probe.MEMORY_BYTES))
    (tmp_path / "cpu.max").write_text("10000 100000")
    assert probe.resource_limits()["cpu_limit"] == 0.1
    (tmp_path / "cpu.max").write_text("100000 100000")
    with pytest.raises(ValueError, match="512 MB"):
        probe.resource_limits()


@pytest.mark.parametrize("fail_at_probe", [False, True])
def test_smoke_uses_one_limited_app_container_and_removes_its_resources(monkeypatch, fail_at_probe):
    calls = []

    def docker(*arguments, **kwargs):
        calls.append(arguments)
        if arguments[:2] == ("image", "inspect"):
            return "linux/amd64"
        if arguments[:2] == ("exec", app_name()) and "scripts.reasoner_resource_probe" in arguments:
            if fail_at_probe:
                raise check.SmokeFailure("The probe failed.")
            return json.dumps({"status": "passed"})
        if arguments[:3] == ("inspect", "--format", "{{json .State}}"):
            return json.dumps({"Running": True, "OOMKilled": False})
        return "fixture"

    def app_name():
        return next((item[item.index("--name") + 1] for item in calls if "--memory" in item), None)

    monkeypatch.setattr(check, "docker", docker)
    monkeypatch.setattr(check, "wait_for_database", lambda name: None)
    monkeypatch.setattr(check, "wait_for_app", lambda name: None)
    if fail_at_probe:
        with pytest.raises(check.SmokeFailure, match="probe failed"):
            check.run("fixture", build=False)
    else:
        assert check.run("fixture", build=False)["status"] == "passed"
    app_calls = [item for item in calls if "--memory" in item]
    assert len(app_calls) == 1
    arguments = app_calls[0]
    for flag, value in {
        "--memory": "512m",
        "--memory-swap": "512m",
        "--cpus": "0.1",
        "--platform": "linux/amd64",
    }.items():
        assert arguments[arguments.index(flag) + 1] == value
    created = [item[item.index("--name") + 1] for item in calls if item[0] == "run"]
    removed = [item[2] for item in calls if item[:2] == ("rm", "--force")]
    assert sorted(removed) == sorted(created)
    network = next(item[2] for item in calls if item[:2] == ("network", "create"))
    assert ("network", "rm", network) in calls

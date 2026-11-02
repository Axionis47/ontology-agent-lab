import socket

import pytest

from oak_contracts.fixture import input_fixture, package_fixture
from oak_contracts.models import REQUIRED_GATES, Scope, digest
from oak_contracts.store import SQLiteHarness


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("The offline contract suite attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


@pytest.fixture
def harness(tmp_path):
    store = SQLiteHarness(tmp_path / "contracts.sqlite")
    scope = Scope(project_id="project-a", agent_id="agent-1")
    store.bootstrap(scope.project_id, "owner", "verifier")
    store.create_agent("owner", scope)
    package_hash, package = package_fixture(store, scope)
    report_hash = store.issue_report(
        "verifier",
        scope,
        package_hash,
        dict.fromkeys(REQUIRED_GATES, "passed"),
        (digest("fixture-suite-v1"),),
    )
    store.activate("owner", scope, package_hash, report_hash, 0, (digest("fixture-suite-v1"),))
    request, observations, as_of = input_fixture()
    store.create_context("owner", scope, "context-1", package_hash, request, as_of)
    yield store, scope, package_hash, package, observations
    store.close()

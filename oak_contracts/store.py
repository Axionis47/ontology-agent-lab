"""Durable local substitute for integration tests, using one SQLite transaction domain.

Production PostgreSQL/Neo4j ordering and OIDC authentication are not simulated proofs.
Subjects are injected by the test fixture, as if a trusted authentication layer had
already authenticated them. Membership checks are real within this harness.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import (
    REQUIRED_GATES,
    ArtifactRef,
    ContractError,
    GateReport,
    IngestReceipt,
    Package,
    Scope,
    SelectionRequest,
    ToolObservation,
    canonical,
    digest,
)
from .selection import check_candidates, project, validate_scope

DDL = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS members(project TEXT, subject TEXT, role TEXT NOT NULL,
  PRIMARY KEY(project,subject), FOREIGN KEY(project) REFERENCES projects(id));
CREATE TABLE IF NOT EXISTS agents(project TEXT, id TEXT, PRIMARY KEY(project,id),
  FOREIGN KEY(project) REFERENCES projects(id));
CREATE TABLE IF NOT EXISTS artifacts(project TEXT, hash TEXT, kind TEXT, payload TEXT,
  PRIMARY KEY(project,hash), FOREIGN KEY(project) REFERENCES projects(id));
CREATE TABLE IF NOT EXISTS packages(project TEXT, agent TEXT, hash TEXT, payload TEXT,
  PRIMARY KEY(project,agent,hash), FOREIGN KEY(project,agent) REFERENCES agents(project,id));
CREATE TABLE IF NOT EXISTS reports(project TEXT, agent TEXT, hash TEXT, candidate TEXT, payload TEXT,
  PRIMARY KEY(project,agent,hash), FOREIGN KEY(project,agent,candidate) REFERENCES packages(project,agent,hash));
CREATE TABLE IF NOT EXISTS active(project TEXT, agent TEXT, hash TEXT, generation INTEGER,
  PRIMARY KEY(project,agent), FOREIGN KEY(project,agent,hash) REFERENCES packages(project,agent,hash));
CREATE TABLE IF NOT EXISTS runs(project TEXT, agent TEXT, id TEXT, package TEXT, deadline REAL,
  max_calls INTEGER, mode TEXT, status TEXT, PRIMARY KEY(project,agent,id),
  FOREIGN KEY(project,agent,package) REFERENCES packages(project,agent,hash));
CREATE TABLE IF NOT EXISTS reservations(project TEXT, agent TEXT, run TEXT, operation TEXT,
  request_hash TEXT, state TEXT, PRIMARY KEY(project,agent,run,operation),
  FOREIGN KEY(project,agent,run) REFERENCES runs(project,agent,id));
CREATE TABLE IF NOT EXISTS contexts(project TEXT, agent TEXT, id TEXT, package TEXT,
  request TEXT, as_of TEXT, revision INTEGER, PRIMARY KEY(project,agent,id),
  FOREIGN KEY(project,agent,package) REFERENCES packages(project,agent,hash));
CREATE TABLE IF NOT EXISTS snapshots(project TEXT, agent TEXT, context TEXT, revision INTEGER,
  payload TEXT, PRIMARY KEY(project,agent,context,revision),
  FOREIGN KEY(project,agent,context) REFERENCES contexts(project,agent,id));
CREATE TABLE IF NOT EXISTS observations(project TEXT, agent TEXT, context TEXT, id TEXT,
  hash TEXT, payload TEXT, receipt TEXT, PRIMARY KEY(project,agent,context,id),
  FOREIGN KEY(project,agent,context) REFERENCES contexts(project,agent,id));
CREATE TABLE IF NOT EXISTS events(sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  project TEXT, agent TEXT, event TEXT, payload TEXT);
"""


class SQLiteHarness:
    def __init__(self, path: str | Path):
        self.db = sqlite3.connect(path, isolation_level=None, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(DDL)

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def bootstrap(self, project_id: str, owner: str, verifier: str):
        """Trusted fixture setup only. This is not a public service endpoint."""
        with self.transaction():
            self.db.execute("INSERT INTO projects VALUES(?)", (project_id,))
            self.db.execute("INSERT INTO members VALUES(?,?,?)", (project_id, owner, "owner"))
            self.db.execute("INSERT INTO members VALUES(?,?,?)", (project_id, verifier, "verifier"))

    def authorize(self, subject: str, project_id: str, allowed: set[str]):
        row = self.db.execute(
            "SELECT role FROM members WHERE project=? AND subject=?", (project_id, subject)
        ).fetchone()
        if row is None or row["role"] not in allowed:
            raise ContractError("forbidden")

    def _scope(self, subject: str, scope: Scope, write=False):
        allowed = {"owner", "editor"} if write else {"owner", "editor", "viewer", "verifier"}
        self.authorize(subject, scope.project_id, allowed)
        if (
            self.db.execute(
                "SELECT 1 FROM agents WHERE project=? AND id=?", self._key(scope)
            ).fetchone()
            is None
        ):
            raise ContractError("agent_not_found")

    @staticmethod
    def _key(scope: Scope) -> tuple[str, str]:
        return scope.project_id, scope.agent_id

    def _event(self, scope: Scope, event: str, payload: dict):
        self.db.execute(
            "INSERT INTO events(project,agent,event,payload) VALUES(?,?,?,?)",
            (*self._key(scope), event, canonical(payload)),
        )

    def create_agent(self, subject: str, scope: Scope):
        self.authorize(subject, scope.project_id, {"owner", "editor"})
        with self.transaction():
            self.db.execute("INSERT INTO agents VALUES(?,?)", self._key(scope))
            self._event(scope, "agent.created", {})

    def put_artifact(self, subject: str, project_id: str, kind: str, payload: Any) -> ArtifactRef:
        self.authorize(subject, project_id, {"owner", "editor"})
        content_hash = digest({"kind": kind, "payload": payload})
        with self.transaction():
            self.db.execute(
                "INSERT OR IGNORE INTO artifacts VALUES(?,?,?,?)",
                (project_id, content_hash, kind, canonical(payload)),
            )
        return ArtifactRef(kind=kind, sha256=content_hash)

    def get_artifact(self, subject: str, project_id: str, ref: ArtifactRef) -> Any:
        self.authorize(subject, project_id, {"owner", "editor", "viewer", "verifier"})
        row = self.db.execute(
            "SELECT kind,payload FROM artifacts WHERE project=? AND hash=?",
            (project_id, ref.sha256),
        ).fetchone()
        if row is None:
            raise ContractError("artifact_not_found")
        payload = json.loads(row["payload"])
        if (
            row["kind"] != ref.kind
            or digest({"kind": row["kind"], "payload": payload}) != ref.sha256
        ):
            raise ContractError("artifact_integrity_failure")
        return payload

    def save_package(self, subject: str, scope: Scope, package: Package) -> str:
        self._scope(subject, scope, write=True)
        for ref in (package.schema_ref, package.functions, package.extractor, package.operators):
            self.get_artifact(subject, scope.project_id, ref)
        package_hash = digest(package)
        with self.transaction():
            self.db.execute(
                "INSERT OR IGNORE INTO packages VALUES(?,?,?,?)",
                (*self._key(scope), package_hash, canonical(package)),
            )
        return package_hash

    def _package(self, scope: Scope, package_hash: str) -> Package:
        row = self.db.execute(
            "SELECT payload FROM packages WHERE project=? AND agent=? AND hash=?",
            (*self._key(scope), package_hash),
        ).fetchone()
        if row is None:
            raise ContractError("package_not_found")
        package = Package.model_validate_json(row["payload"])
        if digest(package) != package_hash:
            raise ContractError("package_integrity_failure")
        return package

    def _runtime_dependencies(self, subject: str, scope: Scope, package_hash: str):
        from .fixture import implementation_manifest

        package = self._package(scope, package_hash)
        for ref in (package.schema_ref, package.functions, package.extractor, package.operators):
            payload = self.get_artifact(subject, scope.project_id, ref)
            if payload != implementation_manifest(ref.kind):
                raise ContractError("unsupported_fixture_implementation")

    def issue_report(
        self,
        verifier: str,
        scope: Scope,
        package_hash: str,
        gates: dict,
        input_hashes: tuple[str, ...],
    ) -> str:
        self.authorize(verifier, scope.project_id, {"verifier"})
        self._package(scope, package_hash)
        report = GateReport(
            candidate_hash=package_hash, gates=gates, input_hashes=input_hashes, issuer=verifier
        )
        report_hash = digest(report)
        with self.transaction():
            self.db.execute(
                "INSERT OR IGNORE INTO reports VALUES(?,?,?,?,?)",
                (*self._key(scope), report_hash, package_hash, canonical(report)),
            )
            self._event(scope, "verification.recorded", {"report_hash": report_hash})
        return report_hash

    def activate(
        self,
        subject: str,
        scope: Scope,
        package_hash: str,
        report_hash: str,
        expected_generation: int,
        expected_input_hashes: tuple[str, ...],
    ) -> int:
        self.authorize(subject, scope.project_id, {"owner"})
        with self.transaction():
            package = self._package(scope, package_hash)
            for ref in (
                package.schema_ref,
                package.functions,
                package.extractor,
                package.operators,
            ):
                self.get_artifact(subject, scope.project_id, ref)
            row = self.db.execute(
                "SELECT payload FROM reports WHERE project=? AND agent=? AND hash=?",
                (*self._key(scope), report_hash),
            ).fetchone()
            if row is None:
                raise ContractError("verification_not_found")
            report = GateReport.model_validate_json(row["payload"])
            if digest(report) != report_hash:
                raise ContractError("report_integrity_failure")
            if (
                report.candidate_hash != package_hash
                or report.input_hashes != expected_input_hashes
            ):
                raise ContractError("verification_binding_mismatch")
            if set(report.gates) != REQUIRED_GATES or any(
                v != "passed" for v in report.gates.values()
            ):
                raise ContractError("verification_incomplete")
            active = self.db.execute(
                "SELECT generation FROM active WHERE project=? AND agent=?", self._key(scope)
            ).fetchone()
            generation = active["generation"] if active else 0
            if generation != expected_generation:
                raise ContractError("stale_activation")
            self.db.execute(
                "INSERT INTO active VALUES(?,?,?,?) ON CONFLICT(project,agent) DO UPDATE SET hash=excluded.hash,generation=excluded.generation",
                (*self._key(scope), package_hash, generation + 1),
            )
            self._event(
                scope,
                "package.activated",
                {"package_hash": package_hash, "generation": generation + 1},
            )
            return generation + 1

    def start_run(
        self,
        subject: str,
        scope: Scope,
        run_id: str,
        deadline: float,
        max_calls: int,
        mode: str = "held_out",
    ) -> str:
        self._scope(subject, scope, write=True)
        if type(max_calls) is not int or max_calls < 1 or mode not in {"development", "held_out"}:
            raise ContractError("invalid_run_budget_or_mode")
        with self.transaction():
            row = self.db.execute(
                "SELECT hash FROM active WHERE project=? AND agent=?", self._key(scope)
            ).fetchone()
            if row is None:
                raise ContractError("no_active_package")
            self.db.execute(
                "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)",
                (*self._key(scope), run_id, row["hash"], deadline, max_calls, mode, "running"),
            )
            self._event(scope, "run.started", {"run_id": run_id, "package_hash": row["hash"]})
            return row["hash"]

    def read_run(self, subject: str, scope: Scope, run_id: str) -> dict:
        self._scope(subject, scope)
        row = self.db.execute(
            "SELECT * FROM runs WHERE project=? AND agent=? AND id=?", (*self._key(scope), run_id)
        ).fetchone()
        if row is None:
            raise ContractError("run_not_found")
        return dict(row)

    def reserve_call(
        self, subject: str, scope: Scope, run_id: str, operation_id: str, request: dict, now: float
    ) -> str:
        self._scope(subject, scope, write=True)
        with self.transaction():
            run = self.read_run(subject, scope, run_id)
            prior = self.db.execute(
                "SELECT * FROM reservations WHERE project=? AND agent=? AND run=? AND operation=?",
                (*self._key(scope), run_id, operation_id),
            ).fetchone()
            request_hash = digest(request)
            if prior:
                if prior["request_hash"] != request_hash:
                    raise ContractError("operation_identity_collision")
                return "completed" if prior["state"] == "completed" else "reconcile"
            if now >= run["deadline"] or run["status"] != "running":
                raise ContractError("run_not_dispatchable")
            count = self.db.execute(
                "SELECT count(*) FROM reservations WHERE project=? AND agent=? AND run=?",
                (*self._key(scope), run_id),
            ).fetchone()[0]
            if count >= run["max_calls"]:
                raise ContractError("call_budget_exhausted")
            self.db.execute(
                "INSERT INTO reservations VALUES(?,?,?,?,?,?)",
                (*self._key(scope), run_id, operation_id, request_hash, "reserved"),
            )
            self._event(scope, "call.reserved", {"run_id": run_id, "operation_id": operation_id})
            return "dispatch"

    def complete_call(self, subject: str, scope: Scope, run_id: str, operation_id: str):
        self._scope(subject, scope, write=True)
        with self.transaction():
            row = self.db.execute(
                "SELECT state FROM reservations WHERE project=? AND agent=? AND run=? AND operation=?",
                (*self._key(scope), run_id, operation_id),
            ).fetchone()
            if row is None:
                raise ContractError("reservation_not_found")
            if row["state"] == "completed":
                return
            self.db.execute(
                "UPDATE reservations SET state='completed' WHERE project=? AND agent=? AND run=? AND operation=?",
                (*self._key(scope), run_id, operation_id),
            )
            self._event(scope, "call.completed", {"run_id": run_id, "operation_id": operation_id})

    def create_context(
        self,
        subject: str,
        scope: Scope,
        context_id: str,
        package_hash: str,
        request: SelectionRequest,
        as_of: datetime,
    ):
        self._scope(subject, scope, write=True)
        self._package(scope, package_hash)
        if as_of.utcoffset() is None:
            raise ContractError("as_of_requires_timezone")
        with self.transaction():
            self.db.execute(
                "INSERT INTO contexts VALUES(?,?,?,?,?,?,?)",
                (
                    *self._key(scope),
                    context_id,
                    package_hash,
                    canonical(request),
                    as_of.isoformat(),
                    0,
                ),
            )
            self.db.execute(
                "INSERT INTO snapshots VALUES(?,?,?,?,?)",
                (
                    *self._key(scope),
                    context_id,
                    0,
                    canonical({"offers": {}, "observations": [], "exhaustive": False}),
                ),
            )

    def ingest(
        self,
        subject: str,
        scope: Scope,
        context_id: str,
        observation: ToolObservation,
        expected_parent: int,
    ) -> IngestReceipt:
        self._scope(subject, scope, write=True)
        with self.transaction():
            context = self.db.execute(
                "SELECT * FROM contexts WHERE project=? AND agent=? AND id=?",
                (*self._key(scope), context_id),
            ).fetchone()
            if context is None:
                raise ContractError("context_not_found")
            self._runtime_dependencies(subject, scope, context["package"])
            observation_hash = digest(observation)
            prior = self.db.execute(
                "SELECT hash,receipt FROM observations WHERE project=? AND agent=? AND context=? AND id=?",
                (*self._key(scope), context_id, observation.observation_id),
            ).fetchone()
            if prior:
                if prior["hash"] != observation_hash:
                    raise ContractError("observation_identity_collision")
                return IngestReceipt.model_validate_json(prior["receipt"])
            if context["revision"] != expected_parent:
                raise ContractError("stale_graph_parent")
            request = SelectionRequest.model_validate_json(context["request"])
            validate_scope(observation, request)
            age = (
                datetime.fromisoformat(context["as_of"]) - observation.observed_at
            ).total_seconds()
            if not 0 <= age <= 600:
                raise ContractError("source_outside_fixture_freshness_window")
            old = self.db.execute(
                "SELECT payload FROM snapshots WHERE project=? AND agent=? AND context=? AND revision=?",
                (*self._key(scope), context_id, expected_parent),
            ).fetchone()
            snapshot = project(json.loads(old["payload"]), observation)
            revision = expected_parent + 1
            receipt = IngestReceipt(
                context_id=context_id,
                observation_id=observation.observation_id,
                observation_hash=observation_hash,
                package_hash=context["package"],
                parent_revision=expected_parent,
                revision=revision,
            )
            self.db.execute(
                "INSERT INTO snapshots VALUES(?,?,?,?,?)",
                (*self._key(scope), context_id, revision, canonical(snapshot)),
            )
            self.db.execute(
                "INSERT INTO observations VALUES(?,?,?,?,?,?,?)",
                (
                    *self._key(scope),
                    context_id,
                    observation.observation_id,
                    observation_hash,
                    canonical(observation),
                    canonical(receipt),
                ),
            )
            self.db.execute(
                "UPDATE contexts SET revision=? WHERE project=? AND agent=? AND id=?",
                (revision, *self._key(scope), context_id),
            )
            self._event(scope, "graph.committed", receipt.model_dump(mode="json"))
            return receipt

    def select(
        self,
        subject: str,
        scope: Scope,
        context_id: str,
        revision: int,
        required_observations: tuple[str, ...],
        expected_package_hash: str,
    ):
        self._scope(subject, scope)
        context = self.db.execute(
            "SELECT * FROM contexts WHERE project=? AND agent=? AND id=?",
            (*self._key(scope), context_id),
        ).fetchone()
        if context is None or context["package"] != expected_package_hash:
            raise ContractError("view_package_mismatch")
        self._runtime_dependencies(subject, scope, expected_package_hash)
        row = self.db.execute(
            "SELECT payload FROM snapshots WHERE project=? AND agent=? AND context=? AND revision=?",
            (*self._key(scope), context_id, revision),
        ).fetchone()
        if row is None:
            raise ContractError("snapshot_not_found")
        snapshot = json.loads(row["payload"])
        if not set(required_observations).issubset(snapshot["observations"]):
            raise ContractError("required_observation_not_committed")
        request = SelectionRequest.model_validate_json(context["request"])
        return check_candidates(snapshot, request, expected_package_hash, context_id, revision)

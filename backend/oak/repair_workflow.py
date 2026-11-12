"""Deterministic repair decisions over immutable candidate and evaluation records.

The trusted host evaluator supplies reports. Model proposals cannot supply them.
This module does not dispatch tools, call models, or infer task meaning from text.
"""

from collections.abc import Sequence
from typing import Literal

from pydantic import Field, model_validator

from oak.repair_executor import execute_function, validate_candidate
from oak.repair_patch import apply_targeted_patch, candidate_digest, canonical_digest
from oak.repair_schemas import Candidate, Digest, Frozen, Identifier, TargetedPatch


class RepairCase(Frozen):
    id: Identifier
    query: str = Field(min_length=1, max_length=10000)
    tool_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=2000)
    criterion_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_identifiers(self):
        for values in (self.tool_ids, self.criterion_ids):
            if len(values) != len(set(values)):
                raise ValueError("Case tool and criterion IDs must be unique.")
        if not self.query.strip():
            raise ValueError("A case query cannot be blank.")
        return self


class RepairContract(Frozen):
    version: Literal["oak.repair-contract.v1"] = "oak.repair-contract.v1"
    task_text: str = Field(min_length=1, max_length=50000)
    discovery_digest: Digest
    granted_tool_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=2000)
    cases: tuple[RepairCase, ...] = Field(min_length=1, max_length=200)
    evaluator_id: Identifier
    evaluator_version: Identifier
    operator_version: Literal["oak.operators.v1"] = "oak.operators.v1"

    @model_validator(mode="after")
    def check_access(self):
        if not self.task_text.strip():
            raise ValueError("The original task cannot be blank.")
        if len(self.granted_tool_ids) != len(set(self.granted_tool_ids)):
            raise ValueError("Granted tool IDs must be unique.")
        if len(self.cases) != len({case.id for case in self.cases}):
            raise ValueError("Case IDs must be unique.")
        grants = set(self.granted_tool_ids)
        if any(not set(case.tool_ids) <= grants for case in self.cases):
            raise ValueError("A sample cannot expand the agent's tool grants.")
        return self

    @property
    def digest(self):
        return canonical_digest(self)


class CriterionEvaluation(Frozen):
    criterion_id: Identifier
    status: Literal["passed", "failed", "inconclusive", "error"]
    evidence_refs: tuple[Identifier, ...] = Field(default=(), max_length=100)

    @model_validator(mode="after")
    def require_pass_evidence(self):
        if self.status == "passed" and not self.evidence_refs:
            raise ValueError("A passing check requires evaluator evidence references.")
        return self


class CaseEvaluation(Frozen):
    case_id: Identifier
    environment_digest: Digest
    criteria: tuple[CriterionEvaluation, ...] = Field(min_length=1, max_length=100)
    execution_status: Literal["complete", "failed", "unknown"]
    trace_complete: bool = True
    function_ids: tuple[Identifier, ...] = Field(default=(), max_length=100)
    observed_tool_ids: tuple[Identifier, ...] = Field(default=(), max_length=2000)

    @model_validator(mode="after")
    def unique_checks(self):
        if len(self.criteria) != len({item.criterion_id for item in self.criteria}):
            raise ValueError("A case cannot report a criterion twice.")
        if len(self.function_ids) != len(set(self.function_ids)):
            raise ValueError("Reported function IDs must be unique.")
        if len(self.observed_tool_ids) != len(set(self.observed_tool_ids)):
            raise ValueError("Reported tool IDs must be unique.")
        return self


class EvaluationSuite(Frozen):
    version: Literal["oak.repair-evaluation.v1"] = "oak.repair-evaluation.v1"
    contract_digest: Digest
    candidate_digest: Digest
    evaluator_id: Identifier
    evaluator_version: Identifier
    mode: Literal["offline", "native"]
    cases: tuple[CaseEvaluation, ...] = Field(min_length=1, max_length=200)


class RepairRecord(Frozen):
    patch_id: Identifier
    base_digest: Digest
    candidate_digest: Digest
    target_case_id: Identifier
    target_criterion_ids: tuple[Identifier, ...]
    state: Literal["proposed", "rejected", "provisional", "ready"]
    reasons: tuple[str, ...] = ()


class InferencePin(Frozen):
    contract_digest: Digest
    candidate_digest: Digest


class RepairSession:
    """Keep repair decisions separate from model output and external execution."""

    def __init__(self, contract: RepairContract, initial: Candidate):
        contract = RepairContract.model_validate_json(contract.model_dump_json())
        self._contract_json = contract.model_dump_json()
        initial = Candidate.model_validate_json(initial.model_dump_json())
        if initial.original_input_digest != contract.digest:
            raise ValueError("The candidate does not match the locked input contract.")
        self._requirement_ids = tuple(item.id for item in initial.requirements.requirements)
        self._validate_candidate(initial)
        version = candidate_digest(initial)
        self._candidates = {version: initial.model_dump_json()}
        self._current = version
        self._accepted: str | None = None
        self._accepted_versions: set[str] = set()
        self._suites: dict[tuple[str, str], str] = {}
        self._patches: dict[str, str] = {}
        self._records: dict[str, RepairRecord] = {}
        self._receipts = {}
        self._pending: str | None = None
        self._environment_digests: dict[str, str] = {}

    @property
    def contract(self):
        return RepairContract.model_validate_json(self._contract_json)

    @property
    def current_digest(self):
        return self._current

    @property
    def accepted_digest(self):
        return self._accepted

    @property
    def records(self):
        return tuple(self._records.values())

    def candidate(self, version: str | None = None) -> Candidate:
        version = self._current if version is None else version
        if version not in self._candidates:
            raise ValueError("The candidate is not part of this repair session.")
        return Candidate.model_validate_json(self._candidates[version])

    def _validate_candidate(self, candidate):
        errors = validate_candidate(
            candidate, self.contract.granted_tool_ids, self._requirement_ids
        )
        if errors:
            raise ValueError("Invalid candidate: " + "; ".join(errors))

    def _validate_suite(self, suite: EvaluationSuite, version: str) -> EvaluationSuite:
        suite = EvaluationSuite.model_validate_json(suite.model_dump_json())
        contract = self.contract
        if (
            suite.contract_digest != contract.digest
            or suite.candidate_digest != version
            or suite.evaluator_id != contract.evaluator_id
            or suite.evaluator_version != contract.evaluator_version
        ):
            raise ValueError("The evaluation does not match the locked candidate and evaluator.")
        expected = {case.id: case for case in contract.cases}
        actual = {case.case_id: case for case in suite.cases}
        if len(actual) != len(suite.cases) or actual.keys() != expected.keys():
            raise ValueError("Evaluation must include every locked sample exactly once.")
        candidate = self.candidate(version)
        functions = {function.id: function for function in candidate.functions}
        relations = {relation.id: relation for relation in candidate.schema.relations}
        for case_id, result in actual.items():
            if {item.criterion_id for item in result.criteria} != set(
                expected[case_id].criterion_ids
            ):
                raise ValueError("Evaluation must include every locked criterion exactly once.")
            if not set(result.function_ids) <= functions.keys():
                raise ValueError("Evaluation cites a function outside the candidate.")
            selected = set(expected[case_id].tool_ids)
            if not set(result.observed_tool_ids) <= selected:
                raise ValueError("Evaluation cites a tool outside the sample selection.")
            entities = set()
            for function_id in result.function_ids:
                for step in functions[function_id].steps:
                    if step.op == "lookup":
                        entities.add(step.entity_id)
                    elif step.op == "traverse":
                        relation = relations[step.relation_id]
                        entities.update((relation.from_entity, relation.to_entity))
            if any(
                mapping.tool_id not in selected
                for mapping in candidate.mappings
                if mapping.entity_id in entities
            ):
                raise ValueError(
                    "A reported function requires a tool outside the sample selection."
                )
            previous = self._environment_digests.get(case_id)
            if previous is not None and previous != result.environment_digest:
                raise ValueError("The prepared case environment changed between evaluations.")
        key = (version, suite.mode)
        previous_suite = self._suites.get(key)
        if previous_suite and canonical_digest(
            EvaluationSuite.model_validate_json(previous_suite)
        ) != canonical_digest(suite):
            raise ValueError("An evaluation cannot overwrite a recorded result.")
        return suite

    def _save_suite(self, suite):
        self._suites[(suite.candidate_digest, suite.mode)] = suite.model_dump_json()
        for case in suite.cases:
            self._environment_digests[case.case_id] = case.environment_digest

    def _suite(self, version, mode: str | None = None):
        for kind in (mode,) if mode else ("native", "offline"):
            stored = self._suites.get((version, kind))
            if stored:
                return EvaluationSuite.model_validate_json(stored)
        raise ValueError("Record the base candidate's evaluation before proposing a repair.")

    @staticmethod
    def _outcomes(suite):
        return {
            (case.case_id, item.criterion_id): item.status
            for case in suite.cases
            for item in case.criteria
        }

    @staticmethod
    def _execution_errors(suite):
        issues = []
        for case in suite.cases:
            if case.execution_status != "complete" or not case.trace_complete:
                issues.append(f"Sample {case.case_id} has incomplete or uncertain execution.")
            if any(item.status in {"inconclusive", "error"} for item in case.criteria):
                issues.append(f"Sample {case.case_id} has no conclusive evaluator result.")
        return issues

    def _ready(self, suite):
        functions = {function.id for function in self.candidate(suite.candidate_digest).functions}
        executed = {function_id for case in suite.cases for function_id in case.function_ids}
        return (
            suite.mode == "native"
            and not self._execution_errors(suite)
            and all(value == "passed" for value in self._outcomes(suite).values())
            and bool(functions)
            and functions <= executed
        )

    def _accept(self, suite):
        self._accepted = suite.candidate_digest
        self._accepted_versions.add(suite.candidate_digest)

    def record_baseline(self, suite: EvaluationSuite):
        if self._patches:
            raise ValueError("The baseline is fixed after the first repair proposal.")
        suite = self._validate_suite(suite, self._current)
        self._save_suite(suite)
        if self._ready(suite):
            self._accept(suite)

    def propose(
        self,
        patch: TargetedPatch,
        target_case_id: str,
        target_criterion_ids: Sequence[str],
    ) -> RepairRecord:
        patch = TargetedPatch.model_validate_json(patch.model_dump_json())
        targets = tuple(target_criterion_ids)
        if not targets or len(targets) != len(set(targets)):
            raise ValueError("Select distinct failed criteria for this repair.")
        if patch.id in self._patches:
            record = self._records[patch.id]
            previous = TargetedPatch.model_validate_json(self._patches[patch.id])
            if (
                canonical_digest(previous) != canonical_digest(patch)
                or record.target_case_id != target_case_id
                or record.target_criterion_ids != targets
            ):
                raise ValueError("This patch ID belongs to another repair request.")
            return record
        if self._pending is not None:
            raise ValueError("Assess the pending repair before proposing another.")
        if patch.base_digest != self._current:
            raise ValueError("The repair base is stale.")
        if patch.fault.sample_id != target_case_id:
            raise ValueError("The diagnosed fault must identify the target sample.")
        baseline = self._suite(self._current)
        observed = self._outcomes(baseline)
        case = next((case for case in baseline.cases if case.case_id == target_case_id), None)
        if (
            case is None
            or case.execution_status != "complete"
            or not case.trace_complete
            or any(observed.get((target_case_id, item)) != "failed" for item in targets)
        ):
            raise ValueError("A repair requires a recorded, conclusive target failure.")
        application = apply_targeted_patch(
            self.candidate(),
            patch,
            applied_patches=self._receipts,
            allowed_tool_ids=self.contract.granted_tool_ids,
            requirement_ids=self._requirement_ids,
        )
        candidate = application.candidate
        self._validate_candidate(candidate)
        version = candidate_digest(candidate)
        if version == self._current:
            raise ValueError("An unchanged candidate is not a repair.")
        record = RepairRecord(
            patch_id=patch.id,
            base_digest=self._current,
            candidate_digest=version,
            target_case_id=target_case_id,
            target_criterion_ids=targets,
            state="proposed",
        )
        self._candidates[version] = candidate.model_dump_json()
        self._patches[patch.id] = patch.model_dump_json()
        self._receipts[patch.id] = application.receipt
        self._records[patch.id] = record
        self._pending = patch.id
        return record

    def assess(self, patch_id: str, suite: EvaluationSuite) -> RepairRecord:
        if patch_id not in self._records:
            raise ValueError("Unknown repair ID.")
        record = self._records[patch_id]
        suite = self._validate_suite(suite, record.candidate_digest)
        if record.state != "proposed":
            if (suite.candidate_digest, suite.mode) not in self._suites:
                raise ValueError("The repair already has a decision.")
            return record
        baseline = self._suite(record.base_digest, suite.mode)
        before, after = self._outcomes(baseline), self._outcomes(suite)
        reasons = self._execution_errors(suite)
        for criterion in record.target_criterion_ids:
            if after[(record.target_case_id, criterion)] != "passed":
                reasons.append(f"Target criterion {criterion} is not corrected.")
        for (case_id, criterion), result in before.items():
            if result == "passed" and after[(case_id, criterion)] != "passed":
                reasons.append(f"Sample {case_id}, criterion {criterion} regressed.")
        self._save_suite(suite)
        state = "rejected" if reasons else "ready" if self._ready(suite) else "provisional"
        record = record.model_copy(update={"state": state, "reasons": tuple(reasons)})
        self._records[patch_id] = record
        self._pending = None
        if not reasons:
            self._current = suite.candidate_digest
            if state == "ready":
                self._accept(suite)
        return record

    def validate_for_inference(self, suite: EvaluationSuite) -> InferencePin:
        if self._pending is not None:
            raise ValueError("Assess the pending repair first.")
        suite = self._validate_suite(suite, self._current)
        self._save_suite(suite)
        if not self._ready(suite):
            raise ValueError("Inference requires a complete passing native evaluation suite.")
        self._accept(suite)
        return self.pin_for_inference()

    def pin_for_inference(self) -> InferencePin:
        if self._accepted is None:
            raise ValueError("No candidate is ready for inference.")
        return InferencePin(contract_digest=self.contract.digest, candidate_digest=self._accepted)

    def execute_pinned(self, pin: InferencePin, function_id, arguments, observations):
        if (
            pin.contract_digest != self.contract.digest
            or pin.candidate_digest not in self._accepted_versions
        ):
            raise ValueError("The inference pin does not name an accepted version.")
        return execute_function(
            self.candidate(pin.candidate_digest), function_id, arguments, observations
        )

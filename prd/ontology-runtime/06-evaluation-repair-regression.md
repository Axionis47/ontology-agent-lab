# Evaluation, repair, and retained regression

[Product documentation](../../docs/README.md) | [Current system guide](../../docs/system.md)

This document retains component contracts and earlier research proposals.
Apply the current product scope before its benchmark-specific requirements.
Use the current system guide for implemented behavior.

Status: Retained component draft. AppWorld is the proposed benchmark environment.

## AppWorld scope revision

The [AppWorld implementation plan](07-implementation-plan.md) controls the proposed benchmark scope.
Retain this document's generic invariants and component responsibilities.
The hotel and stock profiles, fixed two-function catalog, and fixture-specific acceptance counts are superseded.
SQLite source templates and reservation transactions are not AppWorld requirements.
Do not assume global source versions, complete collection reads, or provider idempotency.
Revise these details against the actual AppWorld interface before implementation.
Use official AppWorld splits and evaluation instead of the former generated-world protocol.
This component draft is not yet an implementation-ready AppWorld specification.

## Purpose and scope

**EVAL-001.** Show whether generated relations and functions improve one agent's task decisions.
Measure execution safety separately from decision quality.
Use one Reasoning and Acting (ReAct) agent and existing Model Context Protocol (MCP) servers.
Do not add a frontend, agent memory system, new MCP server, or multi-agent runtime.

The first task surface is local hotel assessment and reservation.
The generated functions assess all offers and prepare one permitted reservation.
The SQLite MCP server performs the local action.
The Filesystem MCP server writes the answer artifact.
The action does not make a real booking.

The basis is paper Sections 3.1 to 3.3 and the current project decisions.
See the [source paper](../../docs/paper/source/oak-2608.22974v1.pdf) and
[existing victory criteria](../../docs/ontology-victory.md).
All numerical defaults in this document are project proposals, not paper requirements.

## Current evidence and proposed change

**EVAL-002.** Preserve the distinction between current evidence and proposed behavior.

| Current implementation | Proposed evaluation requirement |
| --- | --- |
| Gemini generates a bounded hotel schema and one function program. | Evaluate the two-function assessment and reservation design. |
| HermiT checks Web Ontology Language (OWL) schema consistency. | Keep logical checks and add evidence, state, and action tests. |
| Direct tests compare the generated executor with an independent calculation. | Keep an independent oracle outside all runtime acceptance paths. |
| Native episodes use unchanged SQLite and Filesystem MCP packages. | Evaluate actual MCP calls, observations, receipts, and committed state. |
| A handwritten `source_answer` check validates runtime proposals. | Remove this semantic oracle from ontology acceptance. Keep it only in evaluation. |
| The pilot records first proposals, rejected calls, and actions. | Add requirement coverage and precise failure attribution. |
| Some correct answers and actions were followed by a CLI turn-limit error. | Report task outcome and client termination as separate measurements. |

The current pilot does not establish the complete victory conditions.
Do not present a proposed receipt, gate, or atomic action check as implemented evidence.

## Independent responsibilities

**EVAL-003.** Keep the following surfaces fixed during each experiment.

| Fixed surface | Owner and rule |
| --- | --- |
| Task requirements | The task contract identifies each requirement. A repair cannot change its meaning. |
| Tool grants and provider capabilities | The host fixes permitted operations, schemas, account scope, and write capabilities. |
| Primitive semantics | Developer code defines types, comparisons, arithmetic, traversal, and transaction behavior. |
| Evidence and receipt rules | The host fixes authenticity, coverage, version, and dependency checks. |
| Reference calculation | An evaluator implements the agreed task independently of generated functions. |
| Dataset partitions and metrics | The experiment manifest fixes membership, denominators, budgets, and stopping rules. |
| Action safety | The action adapter fixes atomic version checks, idempotency, and commit verification. |

The constructor can edit declared source mappings, ontology relations, and function composition.
It can add, replace, or remove an artifact within the approved grammar.
It can correct derived requirement trace links and checked native operation bindings.
These edits cannot change the original task meaning or provider capabilities.
It cannot edit the evaluator, source facts, expected answers, grant list, or acceptance thresholds.
It cannot add a new primitive or executable code through a repair.

**EVAL-004.** The runtime must not call or import the reference calculation.
The reference calculation must not call the generated Python plan, operator executor, or runtime gate.
They can share documented source formats and task requirements.
They must not share the implementation that decides eligibility or selects the action.
Check evaluator results against small manually calculated examples.
Check every model proposal before any runtime rejection or correction.

A runtime receipt establishes execution and evidence binding.
It does not establish that a generated rule matches the user's intent.
An OWL pass establishes logical properties of the declared schema.
It does not establish source truth, data completeness, or task correctness.
Zero invalid commits caused by a common action gate are not an ontology accuracy gain.

## Dataset partitions and duplicate control

**EVAL-005.** Define a source world before sampling it.
A world contains the request, source records, source versions, initial action state, and fault schedule.
Its expected answer and action state are evaluator-only fields.
A world group contains that world and every derived paraphrase, rename, reorder, or mutation.

Use these proposed bounded defaults for the next authorized experiment:

| Partition | Root worlds | Use |
| --- | ---: | --- |
| Construction | 24 | Draft artifacts, diagnose faults, and repair candidates. |
| Development | 24 | Select or reject candidates after construction. |
| Small frozen unseen set | 30 | Test one promoted kernel against matched agent conditions. |
| Executor stress set | 10,000 per promoted kernel | Compare direct execution with the independent oracle. |

Use the ten hotel scenario families already defined in the project.
Each construction and development set contains at least two worlds from each family.
Each contains 16 complete worlds with eligible offers, four complete worlds with no eligible offer,
and four incomplete worlds.

The small unseen set contains three worlds from each family.
It contains 20 complete worlds with eligible offers, four complete empty worlds, and six incomplete worlds.
Record the family and outcome counts before the run starts.
Do not change these counts after results are visible.

The 30-world set is a small mechanism evaluation.
It does not replace the existing 240-world, three-kernel research gate.
The user must explicitly approve any change to that gate.

**EVAL-006.** Assign a root world to one partition before creating its variants.
Use distinct generator seeds and source identifiers for each partition.
Keep every descendant of a root world in the same partition.
Do not put a renamed construction world into the unseen set.

Store a lineage identifier and a normalized content hash for every world.
Use the following bounded algorithm for the controlled fixture generators:

1. Assign stable logical entity identifiers before rendering public source keys.
2. Keep the private map from each typed public key tuple to its logical identifier.
3. Normalize the typed request. Exclude prompt wording and case names.
4. Replace declared identity keys and relation references with their logical identifiers.
5. Preserve namespaces, entity types, key shapes, scalar values, missing targets, and conflicting assertions.
6. Sort properties and record representations. Preserve duplicate occurrences in this representation.
7. Include the initial action state and normalized fault schedule.
8. Encode the canonical result with JavaScript Object Notation (JSON).
9. Hash that result with the 256-bit Secure Hash Algorithm (SHA-256).

Renaming and reordering transformations keep the original logical identifiers and lineage.
Derived mutations remain in the same world group even when their content hash changes.
Two worlds with the same normalized content hash belong to one group.
Reject an exact or normalized duplicate across partitions before model access.
Regenerate a rejected duplicate and record its replacement seed.

This algorithm does not solve arbitrary graph isomorphism.
Do not admit an imported world to the unseen set without a registered lineage and trusted key map.
Do not treat different paraphrases or repeated episodes as independent worlds.

**EVAL-007.** Reserve structural combinations for the unseen partition.
Include shared policies with boundary prices, changed relation targets with distractors,
and duplicate records with missing or conflicting links.
Include equal identifier strings in different type namespaces.
Do not invent an undisclosed business rule to make an unseen case difficult.
All required decision rules remain in the task contract.

Keep unseen cases, their expected outcomes, and generator seeds outside the constructor's inputs.
Keep expected outcomes outside the agent workspace and all MCP responses.
Record source-world hashes before inference.
If an unseen result informs a patch, retire that set from future unseen claims.
Keep it as a regression set and create a new unseen set.

## Construction sampling and review

**EVAL-008.** Bound one construction run to three candidate versions.
This means one initial version and at most two repairs.
One candidate round produces and checks one version.

Use at most two generation calls and one reviewer call for each version.
The first generation call proposes requirements, schema, and source mappings.
Validate the schema and construct accepted sample graphs before the second generation call.
The second call composes functions from that validated schema and graph evidence.
The discovery `R_0` and `S_0` proposal counts as the initial schema call.
Count it in the initial candidate's generation limit and cost ledger.

Reuse an unchanged validated artifact when a targeted patch does not affect it.
Log every candidate, including parse failures and rejected artifacts.
Do not silently restart a failed candidate round with a new identifier.

Give the constructor a fresh six-example construction sample per version.
Fresh means a new seeded draw, not a guarantee that every selected world is new.
Record the first sample before the discovery `R_0` and `S_0` proposal.
Reuse that recorded sample for round zero. Do not resample after discovery.

Sample distinct families with a recorded seed.
Include both an eligible case and an incomplete case.
Prefer families and worlds with the least previous exposure.
Break ties with the recorded seed and candidate version number.

For a repair, add up to two retained failure witnesses outside the fresh sample.
Record fresh sample identifiers and retained failure identifiers separately.
Never fill either group from development or unseen data.

Run direct execution on all 24 construction worlds after schema and type checks pass.
Give the reviewer the requirement contract, candidate diff, complete score table,
operator observations, and available native trajectories.
Give evidence references for every reported fault.
Do not request or depend on private model reasoning.

The reviewer must identify a failing requirement or a failed admission condition.
A passing example is not sufficient evidence for an invariant.
A reviewer statement alone cannot reject a deterministic passing artifact without a stated test or contract conflict.
The reviewer cannot change an expected answer to make a candidate pass.

**EVAL-009.** Use two native construction cases after direct checks pass.
Use one complete case that requires a reservation and one incomplete case that forbids a reservation.
Select each reproducibly from its construction stratum for each candidate version.
Use the recorded seed and version number. Prefer a world not used in an earlier native check.

Record the selection before execution. Do not select cases after seeing their native results.
Native failures enter the construction record with their actual observations.
Do not repair a business rule to address a transport outage or a client configuration error.

Set the candidate state to `locked_for_development` after all construction gates pass.
This state fixes its artifact hashes for development checks. It is not promotion.
Use four fixed native development cases only in this state.
These cover a permitted action, a complete empty result, incomplete evidence, and a stale-action attempt.

The construction reviewer does not receive development expected answers or detailed failure traces.
Development failure rejects that candidate for this construction run.
To use that failure for a later repair, declare a new iteration and reclassify the case as construction or regression data.
Replace the development group before the next selection claim.

The native counts are proposed limits, not authorization to make paid calls.

## Direct tests and native episodes

**EVAL-010.** Keep direct executor tests separate from agent tests.

| Test level | Executes | Establishes |
| --- | --- | --- |
| Schema and compiler | OWL reasoner, type checker, and compiler | Artifact validity for the declared representation. |
| Direct executor | Frozen functions on evaluator-provided graphs | Deterministic correctness on those inputs. |
| Runtime admission | Actual-response adapter, graph publication, receipts, and gates | Evidence and state requirements are enforced. |
| Agent episode | Existing agent, registered Python functions, native MCP client, existing servers, and actions | The model can select functions and use native external tools together. |
| Commit verification | Provider outcome and final database state | The authorized action committed exactly once or remained unresolved. |

Ten thousand executor cases are not ten thousand model episodes.
A scripted model tests protocol handling, not live model behavior.
A direct Python function test does not establish model function registration or native MCP integration.
Test actual model function calls and actual external MCP calls in the same agent episode.

**EVAL-011.** Reset each episode to its declared initial environment.
Create an isolated source database and empty reservation state.
Start a fresh agent session with no previous conversation or persisted agent memory.
Reset runtime receipts, graph revisions, pending actions, and tool processes.
Use the same source world and initial state for each matched condition.
Do not copy the previous condition's answer or action into the next condition.

Fault schedules must identify the exact boundary at which a failure occurs.
For example, change a source after assessment but before action commit.
Source mutations must advance `source_version` atomically with the mutation.
Host graph, log, and receipt writes must not advance the source version.
Record each reset and check its hash before the episode starts.

## Matched comparison

**EVAL-012.** Compare plain ReAct, schema-only ReAct, and the full generated kernel.
Use the same model version, provider, task requirements, source worlds, and tool grants.
Keep source access, action intent, retry policy, and inference limits equal across conditions.
Use a proposed limit of 12 model turns and 24 tool calls per episode.
Count Python function calls, MCP calls, denied calls, and retries against the same limit in every condition.

The baseline can compose ordinary read-only queries over its granted sources.
Do not disable joins, arithmetic, filters, or permitted schema inspection only for the baseline.
The ontology condition adds declared functions and their receipts.
Its runtime can require those receipts for protected actions.
Record this treatment explicitly.

All conditions share grant, source-version, idempotency, and commit-confirmation checks.
The baseline supplies a typed model-proposed intent bound to its observed source version.
It does not receive a generated semantic function or a hidden handwritten eligibility oracle.
The ontology condition additionally requires its generated assessment and preparation receipts.
The independent evaluator determines whether either condition proposed or committed a wrong task decision.

Record differences in model-visible context.
Raw source quarantine and typed evidence projection can change context size and structure.
Do not describe those conditions as receiving identical model input.
Separate the effects of generated computation from shared tool access and commit safety.

Pair and randomize conditions by world.
Schedule complete world blocks before starting more blocks when the budget is small.
Do not spend most of the budget on one condition and compare it with a few baseline runs.
Record the schedule before inference.
Do not select a model seed or repeat because its result is favorable.

**EVAL-013.** Use a fixed retry policy.
Do not retry a wrong answer, rejected action, or exhausted reasoning budget outside the episode limit.
Permit at most one transport retry for an idempotent read after a classified transient failure.
The retry uses the same operation arguments and remains in the same episode.

After an uncertain write outcome, query the outcome using the same action identity and idempotency key.
Do not issue a new booking intent to recover from an unknown result.
Keep the action pending until the provider establishes the outcome.
An unresolved pending write is not a complete task outcome.

Use at most two write dispatches and three status lookups for one intent, including confirmation.
Reserve these five invocation slots within the 24-call limit before the first write dispatch.
Host-controlled read-only reconciliation may continue after model termination within that allowance.
Count model-selected and recovery invocations separately and include both in the total.

## Deterministic invariant suite

**EVAL-014.** Require every applicable invariant below to pass before promotion.
Map each test to its task requirement and component requirement, including `RUN-*` and `ACT-*` identifiers.

| Area | Required test and result |
| --- | --- |
| Source authenticity | A model-fabricated response, forged receipt, or response without a matching granted invocation cannot produce an accepted fact. This does not prove provider truth. |
| Typed arguments | Wrong argument types, changed request scope, or a different task identity fail before dispatch. |
| Actual observations | A successful request with a failed or malformed response does not establish a successful read. |
| Complete publication | A partially parsed batch produces no partial published graph or valid batch receipt. |
| Source coverage | A filtered subset, missing part, or unsupported paginated response cannot establish complete collection coverage. The first adapter does not implement pagination. |
| Graph integrity | Complete observed collections can contain unresolved links or conflicting identities. The assessment must then report incomplete evidence under the task contract. |
| Namespaced identity | Equal key strings in different declared namespaces remain distinct entities. |
| OWL | Conflicting domain or range types combined with disjointness, impossible cardinalities, and unsatisfiable classes fail schema admission. A domain declaration alone can infer a type without an inconsistency. |
| Requirement semantics | Exact age, capacity, price, city, duration, and fee boundaries match the independent reference. |
| Relation semantics | Changing a foreign-key target changes the decision according to the linked target, not a nearby record. |
| Function evidence | An omitted policy or omitted cheaper offer cannot produce a complete assessment receipt. |
| Declared selection | `select_min` uses integer cost and the declared identifier tie rule. A proposed candidate that differs from this result cannot use its preparation receipt. |
| Receipt binding | A different query, kernel, graph revision, source version, or grant version invalidates the old receipt. |
| Read order | Equivalent permitted read orders produce the same assessment and action permission. |
| Dispatch | Host invocation identifiers are unique. Serial dispatch prevents concurrent state admission. |
| Failure handling | A hook timeout, adapter failure, or missing gate decision blocks the protected operation. |
| Context limit | A context limit stops the episode safely. It does not silently remove required evidence or authorize an action. |
| Recovery allowance | Insufficient remaining recovery slots prevent write dispatch. A pending write keeps its permitted read-only recovery path after model termination. |
| Freshness | A source mutation between assessment and commit prevents the old action from committing. |
| Idempotency | Retrying the same intent and key produces one result. Changing the intent under that key fails. |
| Unknown commit | A timeout after commit causes outcome lookup. It does not cause a second reservation. |
| Provider support | A provider without the required atomic version or idempotency capability cannot receive protected writes. |
| Commit evidence | A permitted but failed write does not produce a commit receipt or a successful task outcome. |
| No-action cases | Complete empty and incomplete results produce no reservation. |

Test positive controls as well as rejection cases.
At least one valid assessment must authorize and commit the intended reservation.
A system that rejects every action does not pass.

**EVAL-015.** Measure mutation adequacy before accepting a regression suite.
Create explicit mutations for these faults:

- An omitted age rule or child capacity rule.
- A wrong hotel-policy relation.
- Wrong fee arithmetic.
- A strict comparison instead of an inclusive comparison.
- An omitted candidate.
- A stale source version.
- A changed action target or cost.

Mutate `select_min` to reverse cost order, use string order for integer costs, or reverse the tie rule.
Use unequal costs and equal-cost candidates as separate witnesses.

Each applicable mutation must fail a named invariant while the valid candidate passes.
Record the affected requirement and the test that detected the mutation.
If a mutation survives, add a construction or retained regression witness before promotion.
Do not obtain that witness from the sealed unseen set.

Label injected mutations as repair challenges.
Do not describe them as natural model drafting failures or proof of learning.
Keep naturally observed failures in a separate count.

## Small second-surface compatibility test

**EVAL-016.** Test the generic core with one read-only stock review fixture.
Use the same existing SQLite MCP server.
Do not add a server or a second agent.

The fixture has two declared types:

- `Warehouse` uses `code` as its key and has a `region` field.
- `StockRecord` uses the ordered key fields `warehouse_code` and `sku`.
  It has `units` and `floor_units` fields.

The relation maps `StockRecord.warehouse_code` to `Warehouse.code`.
The request specifies a region.
The function returns stock records in that region where `units <= floor_units`.
Its output contains the composite key and the compared values.
It has no hotel, age, price, reservation, or write rule.

Use six fixed direct cases: valid match, exact boundary, wrong region, missing warehouse,
identical duplicate, and conflicting composite identity.
Add record-order and identity-renaming transformations within those groups.
Run the same type, evidence, coverage, receipt, and evaluator isolation tests.
The compiler and runtime must not require a hotel-specific branch to process this fixture.

A changed surface can supply new declarations, mappings, and a function within the existing grammar.
It cannot change the primitive semantics or runtime gate implementation to pass this test.
An unsupported declared shape must produce an explicit unsupported result.
It must not silently adapt the task to the hotel schema.

This is compatibility evidence for the tested shapes.
It is not proof that the system accepts arbitrary tasks or performs universal entity resolution.
The current hotel-specific source vocabulary does not yet satisfy this proposed test.

## Metrics and exact denominators

**EVAL-017.** Record one result row for every planned condition and world.
Distinguish `not_started_budget`, `started`, `complete`, `failed`, and `unresolved`.
An exception after model dispatch must produce a failure row.
It must not disappear from the denominator.
Report planned, started, and scored counts for every condition and family.

| Measurement | Numerator | Denominator |
| --- | --- | --- |
| First-answer correctness | Exact first proposals that match the independent reference | All started episodes in the stated outcome group |
| First-action correctness | Correct first action intent and exact typed arguments | All started episodes that require an action |
| No-action correctness | Episodes with no action attempt | All started episodes whose reference forbids an action |
| Task outcome | Correct required answer and checked final action state, with no pending unknown write | All started episodes |
| Invalid proposal rate | Invalid proposed answers or action intents | All corresponding proposals. Also report episodes with any invalid proposal. |
| Runtime safety | Episodes with no unauthorized or invalid committed action | All started episodes, with no-action and action-required counts shown |
| Transport completion | Episodes whose client terminates without transport or turn-limit error | All started episodes |
| Evidence coverage | Assessments with complete required evidence coverage | All assessment attempts that claim completeness |

An absent or malformed first proposal is incorrect.
A JSON `null` proposal remains the first proposal after later corrections.
Duplicate offer IDs and wrong numeric types are incorrect.
Correcting a rejected price or action target does not change the first-action score.
An empty answer is correct only when the reference establishes that no offer qualifies.
Abstention on an answerable world is incorrect.

Report task outcome and transport completion separately.
A correct committed reservation followed by a CLI turn-limit error can have a correct task outcome
and failed transport completion.
Keep the earlier strict end-to-end metric as a separately named historical measure.
Do not rewrite historical results under a new definition.

**EVAL-018.** Compute comparison statistics over matched independent world groups.
Show the number of matched worlds beside every difference estimate.
Use the same reference outcome group in both conditions.
Do not combine repeated runs or four kernels on one world as four independent worlds.
Do not display a bootstrap confidence interval with fewer than ten matched worlds.
Report raw paired outcomes in that case.

For larger sets, record the interval method, seed, and resampling unit before inference.

The proposed method uses 10,000 paired bootstrap samples and random seed `1067`.
Compute one success-rate difference per matched world group.
If a group has repeated episodes, average its repeats within each condition first.
Sample the matched groups with replacement and compute the mean difference for each sample.
Use the 250th and 9,750th sorted sample means as the 95 percent percentile interval.

Compute answerable and incomplete-data results separately.
Compare each independently constructed kernel with baseline separately.
If all observed differences are equal, label the bootstrap interval degenerate.
Do not use that interval as evidence of statistical certainty or satisfaction of the interval gate.
This procedure measures uncertainty in the sampled world distribution, not universal reliability.

Report construction cost, inference cost, native calls, denied calls, retries, tokens,
and elapsed time separately.
Include model reasoning tokens when the provider reports them.
Identify estimates, missing usage, and provider invoices as different evidence.

## Failure attribution and durable evidence

**EVAL-019.** Identify the earliest failed contract without assuming it is the only fault.
Use this ordered diagnostic chain:

```text
Requirement -> source evidence -> identity/mapping -> graph relation
            -> function -> primitive operator -> action plan -> provider commit
```

| Failure class | Required evidence | Permitted response |
| --- | --- | --- |
| Requirement ambiguity | Conflicting or absent task statements | Stop semantic repair and request task clarification. |
| Source or coverage | Failed response, missing page, stale version, or incomplete scope | Correct acquisition or keep incomplete state. Do not invent a fact. |
| Identity or mapping | Raw source reference and incorrect normalized key or field | Propose a mapping patch. |
| Schema or relation | Declared axiom, typed edge, and failing check | Propose a schema patch within the fixed task contract. |
| Function or operator | Predicate or projection, operands, evidence references, expected result | Propose a function patch within the primitive grammar. |
| Workflow admission | Valid evidence was absent, stale, or incorrectly admitted | Report a runtime defect. Do not weaken a requirement. |
| Action or commit | Planned arguments, provider result, and observed final state | Repair the action adapter or reconcile the unknown outcome. |
| Transport or model execution | Timeout, denied operation, invalid call, or exhausted limit | Report separately from semantic correctness. |

A direct deterministic failure must reproduce from the same artifact and evidence hashes.
A stochastic model failure can vary across episodes with those hashes.
Record both kinds.
Do not retry stochastic failures until they disappear from the report.

**EVAL-020.** Write append-only trace events and immutable artifact references.
Each event records its schema version, event ID, sequence number, time, event type, and parent event IDs.
Use the common identifiers from the runtime contract.
These identifiers are:
`surface_id`, `surface_version`, `agent_id`, `grant_version`, `run_id`, `invocation_id`,
`query_hash`, `kernel_version`, `graph_revision`, `source_version`, `operation_id`,
`read_receipt_id`, `function_receipt_id`, `action_id`, and `idempotency_key`.
Use null for a field that does not apply.
Do not invent an identifier for an event that did not occur.

Also record:

- Requirement IDs and the exact task-contract hash.
- Dataset version, split, world group, fault schedule, and reset hash.
- Binding kind, registered tool name, typed arguments, result hash, and success state.
- MCP server identity and permitted scope for external calls.
- Python plan ID and operator library version for kernel function calls.
- Source evidence references, publication decision, coverage result, and source version.
- Relation, mapping, function, and operator identifiers with artifact hashes.
- Evaluated operands, comparison result, and retained or excluded entity keys.
- Proposed answer or action before the gate, gate decision, and rejection reason.
- Provider commit identity, observed final state, and unresolved outcome status.
- Model, client, MCP package, compiler, evaluator, and configuration versions.
- Budget reservation, reported usage, estimated charge, and any reconciliation event.

Keep raw evidence in access-controlled artifacts and refer to it by hash and location.
Do not put credentials or private model reasoning in the trace.
Do not replace an old event when a later observation corrects it.
Append a correction that refers to the earlier event.

## Patch selection, promotion, and rollback

**EVAL-021.** Every proposed patch must identify its target artifact, requirement IDs,
before and after hashes, changed declarations, diagnosis, and supporting trajectory events.
Allow edits to derived requirement trace links, mappings, schema, functions, and checked native operation bindings.
Keep those edits within the original task meaning and discovered provider capabilities.
Reject patches that alter task policy, grants, source facts, gold outcomes, evaluator code,
primitive semantics, or action safety checks.

A runtime or provider-adapter defect requires a separate engineering change.
Retire any evaluation manifest whose execution behavior changes.
Do not mix results from before and after that change into one comparison.

**EVAL-022.** Use dependency impact to choose the first regression checks, not the final promotion gate.
Follow changed mapping, type, relation, function, and operator dependencies to their requirements and cases.
Run those cases first for fast diagnosis.
Then run the full retained deterministic suite before promotion.
This includes previous failures, positive controls, mutation witnesses, and both task surfaces.

If a dependency is missing or its effect is unknown, broaden the selected checks to the complete suite.
Do not interpret a missing dependency as no impact.
Do not remove an inconvenient retained failure from the suite.
Record an explicit obsolete requirement decision before retiring its case.

**EVAL-023.** Promote only a complete artifact version.
Require schema validity, type validity, construction success, retained regression success,
mutation adequacy, development success, and the required native evidence.
Freeze mappings, schema, function catalog, operation catalog, and receipt contracts together.
Record the full promotion manifest and its predecessor.
Do not let a live inference episode change these artifacts.

A failed promotion leaves the previous active version unchanged.
Rollback selects a previously validated complete version for new episodes.
An episode with a pending write must finish outcome reconciliation under its original version.
Do not reuse its old receipt or idempotency key with a different action intent.

## Small victory, inconclusive results, and stopping

**EVAL-024.** A small mechanism result is conclusive only for the declared local slice.
Require all of the following:

1. A live constructor generated the relation and function artifacts from the fixed task contract.
2. Every applicable deterministic invariant and mutation witness passes.
3. At least one recorded model repair fixes a demonstrated fault without changing policy or the evaluator.
4. Agent episodes use actual MCP observations and model-selected calls to both generated Python functions.
5. Complete, empty, incomplete, stale-action, and retry cases have the required outcomes.
6. No invalid action commits in the evaluated cases, and valid positive controls do commit.
7. The second read-only surface passes with unchanged generic runtime and compiler semantics.
8. All 30 frozen unseen worlds receive scored outcomes in each predeclared condition.
9. Frozen unseen results and all failed candidate rounds remain inspectable with exact denominators.

This establishes a working mechanism with tested boundaries.
It does not establish a reliability improvement over baseline.
For that claim, keep all existing benefit criteria:

- At least 95 percent task success on answerable cases.
- At least a 10 percentage point improvement over baseline.
- A positive lower bound for the paired 95 percent confidence interval.
- At least 95 percent of incomplete cases produce the required incomplete result.
- The planned repeated evaluation with frozen artifacts and unseen cases.

Report `inconclusive` for insufficient matched worlds, incomplete conditions, baseline ceiling,
missing native evidence, unresolved writes, protocol changes, or unmeasured cost.
If only calls or elapsed time improve, report an efficiency result.
If only a shared gate prevents bad commits, report a runtime safety result.
Do not describe either result as demonstrated ontology semantic accuracy.

**EVAL-025.** Keep the existing 40 United States dollar (USD) experiment cap.
The previous experiment has nearly used that allowance.
This documentation task grants no new live-run budget and does not authorize another Gemini call.
Do not assume the proposed native counts fit the remaining allowance.

Before a future authorized run, reserve a conservative cost for each matched world block.
Include construction, review, retries, failed requests, and inference in the same accounting boundary.
Stop dispatch when the remaining allowance cannot cover the next block.
Preserve completed evidence and mark all unstarted jobs explicitly.
Do not lower thresholds, drop failed conditions, or spend beyond the cap to complete a table.

## Acceptance of this component

The component is ready for implementation planning when its partition rules, metrics,
sampling limits, patch boundaries, and trace fields agree with the other component PRDs.
The implementation remains a separate authorized task.
No new live result is claimed by this document.

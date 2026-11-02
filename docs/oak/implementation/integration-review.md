# Integration challenge and closure record

Design version 0.4.1. November 2, 2026.

This record challenges the proposed boundaries. It does not certify an unimplemented service as defect-free.
The [baseline](README.md) identifies component owners. The [production contracts](CONTRACTS.md) control shared messages.
The [harness report](INTEGRATION-HARNESS.md) separates executed subset checks from required service tests.

## Starting-shape amendment

The [starting shape](AGENT-SHAPE.md) replaces unspecified agent onboarding with an exact managed profile and executable declaration.
Independent reviews separated task identity from loop structure, executable binding from description, and required capabilities from evidence.
They identified and corrected the following handoffs:

| Gap | Closure |
| --- | --- |
| External attachment and managed reference execution were described as the same starting point | The first release is managed; external attachment requires a concrete later bridge |
| Admission lost its selected agent version | C0 request, receipt, storage, and downstream commands retain the immutable version and configuration reference |
| Creation could imply readiness | C9 schedules explicit binding probes; C0 consumes their receipt; C8 separately verifies the complete mount |
| Repeated candidate verification reused unique ordinary assignments | C6 creates session-scoped assignments and complete per-package scoring batches through C10's shared run ledger |
| The UI lacked the exact verification-set hash | CandidateView exposes the server-sealed set reference; review cannot reconstruct it |
| Initial evidence had no loading contract | The first profile rejects seeded observations and cross-run memory |
| Construction and Verify could both start regression | Construction stops after sealing; one bound verification session owns regression |
| Full-package probes required the ready mount they were meant to prove | Prepared bindings and recorded verifier-only conformance children exercise the existing handlers without recursive mounting |

The new declaration has 30 passing checks. The existing substitute has 24 passing checks.
These close specified local validation obligations. Full service conformance remains unimplemented and unrun.

## Disputed choices and resolutions

| Challenge | Failure if ignored | Resolution and responsible owner | Evidence or remaining gate |
| --- | --- | --- | --- |
| General adapter support would hide the agent being tested | Different loops, hooks, and tool policies make failures hard to attribute | C0 selects `offer-selection-v1`; C8 implements that bounded loop before new adapters | Fixed synthetic path runs; actual host lifecycle remains a service gate |
| One component per deployment would multiply failure boundaries | Distributed calls add coordination before the domain mechanism works | C10 uses one modular API and a separate worker | Deployment remains proposed |
| A graph canvas could imply that relations execute actions | Users mistake domain meaning for workflow control | C7 returns distinct domain, dependency, and workflow projections; C11 keeps their legends separate | Browser acceptance remains required |
| A successful HermiT run could certify the wrong task result | Missing business requirements can remain logically consistent | C1 owns formal checks; C5 scores task outcomes independently | Wrong-choice rejection passes in the local evaluator test; real reasoner loop remains required |
| Schema repair could leave old functions or facts usable | Consumers execute against incompatible meanings | C6 computes invalidation; C2 reprojects preserved sources; C3 rebuilds affected consumers | Routing set tested; actual rebuild and consumer blocking remain required |
| A UI could forge a passing verification report | Candidate promotion bypasses every check | Verifier service identity issues persisted, content-bound receipts; C6 resolves them server-side | Local role, hash, candidate, and test-input checks pass; service authentication remains required |
| A changed active package could alter an existing run | A held-out trial silently changes treatment | C10 pins package references in run creation; C6 promotion affects later runs | Local old-run/new-run test passes |
| A successful graph commit could lose its acknowledgement | Retry duplicates facts or advances the revision again | C2 commits graph and receipt atomically; C10 reconciles by replay key | SQLite lost-ack and concurrency tests pass; Neo4j tests remain required |
| A shared transaction across three stores is impossible | PostgreSQL says success while graph or bytes are absent | Store-local authoritative receipts, durable IDs, idempotent delivery, reconciliation | Cross-store crash matrix remains required |
| A reserved operation might be dispatched twice after restart | Budget recovery creates duplicate effects | New admission returns `dispatch`; an existing unresolved reservation returns `reconcile` | Local restart test passes; queue/provider reconciliation remains required |
| Finalization could race an in-flight observation | An old graph supports a result after newer evidence contradicts it | C4 seals dispatch, reconciles pending operations, selects the latest stable revision, applies guards, and commits once | Required release gate; not implemented by the harness |
| Global hashes or cached views could leak another project | Guessing an ID bypasses tenant membership | C9 authorizes scope before resolution; C7/C10 include project, agent, run, package, and revision in applicable keys | Local artifact and context denial pass; HTTP/cache/event tests remain required |
| Arrival order could erase conflicting source values | A later response appears authoritative without policy evidence | C2 retains conflicts; C3 returns unknown unless the pinned policy resolves them | Local conflict, false, unknown, scope, and freshness tests pass |
| Incomplete search could support a market-wide conclusion | A selected offer becomes an unjustified cheapest-offer claim | C3 returns coverage; C5 rejects unsupported claims | Local fixture preserves incomplete coverage and rejects reservation claims |
| A scorer could agree with the same buggy function | The implementation certifies itself | C5 uses an independently authored expected result or source/effect check | Literal evaluator does not import selection code; general source resolution remains required |
| A passing harness could be presented as a finished product | Users assume auth, services, repair, and UI exist | Label every substitute and retain service release gates | Explicit coverage table and machine-readable subset receipts |
| Custom infrastructure could overwhelm domain work | The project maintains an auth server, queue, ORM, DSL, and UI framework | Reuse the selected packages; write only domain rules and integration boundaries | Build-versus-reuse decisions belong to the production contracts |

## Source algorithm and implementation distinction

OaK's local schema construction loop drafts and verifies a schema before use.
Its later task loop evaluates trajectories and proposes schema or function repairs.
These are separate loops. A formal pass cannot replace task evaluation.

The paper freezes S and F for inference. New query evidence supplies the graph.
Our incremental native-tool observations, human review, projects, authentication, activation, and UI are declared engineering adaptations.
See the inspected source comparison in [C1](C01-schema.md) and [C5](C05-evaluation.md).

The local demo changes G after detail evidence arrives. It does not execute either schema repair loop.
Keep this difference visible when showing the demonstration.

## Final cross-component review

The integration reviewer inspected C0 through C11, the shared contracts, architecture decisions, and the documentation standard.
The review followed initial setup, admission, candidate construction, verification, review, activation, execution, repair, and resume.
It also checked the selected reuse boundaries. The following concrete inconsistencies were corrected during that review.

| Finding | Corrected design | Required verification |
| --- | --- | --- |
| A fresh project had no references required by candidate creation or execution | C0 publishes a public `StarterManifest` with the initial change, approved policy, suite, and registered assignments. C11 resolves it. | Complete browser journey from empty project through initial activation and replay |
| Engineering replay appeared to interpret arbitrary human text with a model | C6 accepts supported typed requirements or recorded patches in engineering mode. Uninterpreted text returns `unsupported_interpretation_mode`. | Zero model calls for engineering commands, including unsupported text |
| Repair proposals referred to event IDs that the event store did not define | Shared `EventRef` uses the actual `run_id` and `sequence` identity. C5 uses `supporting_event_refs`. | Resolve each cited event within its exact authorized run |
| A test policy could ambiguously reference private evaluator configuration | C6's `evaluator_ref` names the public contract. C5 resolves private data through its server-only binding. | Private-reference and answer canaries stay outside browser and builder payloads |
| Run creation did not enumerate all configuration checks | C10 requires matching admission mode, assignment, agent version, package dependencies, execution mode, and active generation. | Reject each mismatch before run or job creation |
| Package identity omitted C2 mapping and normalization dependencies | The package pins `mapping_ref` and `normalization_ref`. C2 also verifies the admission's frozen scenario clock. | Changed interpretation cannot reuse an old projection or package receipt |
| Saved draft discard had no command contract | C6 limits discard to an unsubmitted form. A corrected submitted change creates a new candidate. | Original submitted candidate remains readable and unchanged |
| Agent archive behavior had no API operation | C9 defines `AgentUpdate` and mutable revision. C10 exposes `PATCH A`; new work stops for archived agents. | Stale archive writes fail; existing pinned runs complete or are cancelled explicitly |
| The UI claimed that verification could select new mode or budget | C11 displays the admitted values and submits only `VerificationStart` fields. | Generated client rejects undeclared overrides |
| A host registry required a function bundle before that bundle could be built | C8 separates `FunctionBindingDeclaration`, preconstruction capability checks, and mount-time `ResolvedFunctionBinding`. | Fresh construction and repaired-bundle mounting both succeed without changing the immutable host configuration |
| A new request could create a second run for the same assignment | C10 makes the scoped assignment unique per run. Same-key replay returns the run; a different-key duplicate returns `409`. | Concurrent duplicate starts produce one run; deliberate repetition needs a new assignment |
| C8 and C4 could charge the same decision twice | C8 reserves the step before calling the driver. C4 uses that reservation. Invalid decisions retain their cost and step. | Twelve decisions remain twelve across malformed output, dispatch, and resume |

These are design corrections. The associated production tests remain unrun.
No remaining major contradiction was identified in these reviewed paths after the corrections.
This statement covers the reviewed documents. It does not prove complete behavior in unimplemented production code.

StrictDoc supplies the documentation graph. Its typed links connect requirements, owners, contracts, test definitions, decisions, and limited evidence.
That graph does not replace generated Pydantic/OpenAPI contracts or real-service tests.
The local harness uses `Exercises` relations for narrower checks. It cannot mark a production Neo4j, identity, or host requirement as fully verified.

The reviewer also checked the selected session and queue extension points against primary documentation.
Starsessions documents its store interface and supplied encryption support. Procrastinate documents transaction-bound job deferral with connector-specific connections.
These support the reuse choices, not deployment compatibility or successful installation.
See [Starsessions](https://github.com/alex-oleshkevich/starsessions) and [Procrastinate external connections](https://procrastinate.readthedocs.io/en/stable/howto/production/external_connection.html).

## Integration release gates

| Gate | Required evidence | Current status |
| --- | --- | --- |
| Domain and ownership design | One owner, exact contracts, storage authority, errors, and tests for C0 through C11 | Dedicated component reviews and final cross-component document review completed; production models remain unimplemented |
| Offline subset | Scoped handoffs, replay, stable reads, version gates, durable reservations, independent literal result | 24/24 local checks pass |
| Real identity and API | OIDC, session and CSRF checks, project isolation, generated client contract tests | Not implemented |
| Real persistence | Migrations, artifact recovery, queue redelivery, Neo4j atomic receipt, PostgreSQL activation race | Not implemented |
| Real schema change | Compiler, HermiT, source replay, consumer rebuild, regression, independent score, review binding | Not implemented |
| Finalization | Closed dispatch admission, pending-operation reconciliation, stable latest graph, guard, one terminal result | Not implemented |
| Human interface | Auth/project/agent journeys, meaningful graph views, evidence drill-down, stale-result handling | Not implemented |
| Agent benefit study | Registered model settings, enabled thinking, case assignments, independent evaluator, controls, budget | Not selected or run |

An unrun gate blocks its dependent claim. It does not erase passing evidence at another level.
No model call, live provider task, benchmark, or publication occurred during this harness work.

## Completion rule

Each proposed integration needs one accountable owner, a declared failure response, and a verification gate.
Each implemented integration also needs a passing receipt from its real dependencies.
Document completeness and local substitutes cannot close real-service verification.

The writing follows ASD-STE100 principles. Full dictionary and grammar conformity remains unverified.

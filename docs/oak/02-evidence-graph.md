# C2: Evidence and graph builder

Design version 0.3.0. November 2, 2026. This component is proposed. Its algorithm is not implemented.

The [PRD](../OAK-PRD.md) defines requirements. The [integration specification](INTEGRATION.md) defines handoffs. The [research narrative](STATUS.md) records the study status.

## Purpose and ownership

C2 converts source observations into addressable graph facts. A relationship such as `offer FOR_HOTEL hotel` expresses domain meaning. It does not specify an execution sequence.

| Artifact | Meaning | Example |
| --- | --- | --- |
| S, schema | Domain types, properties, relations, and identity declarations | A StayOffer has occupancy and stay restrictions |
| G, evidence graph | Facts extracted from observations within a declared scope | Observation o1 says Offer A permits four guests |
| O, operators | Registered reusable computations | Lookup, traversal, projection, and numeric filtering |
| F, functions | Typed procedures composed from O | Compare observed offers with party size and stay length |
| LangGraph workflow | Component scheduling, retries, and checkpoint transitions | Run C2, receive its receipt, then permit a dependent F call |

The paper separates the schema/function kernel from its evidence graph. [OaK sections 3.1 and 3.2, Steps 2 and 3](https://arxiv.org/html/2608.22974v1).

Neo4j stores facts and source references. F contains computations. LangGraph coordinates execution. Graph relationships do not execute themselves.

C2 owns extraction, identity resolution, evidence validation, and domain-graph commits. C2 does not select external calls, edit S, compose F, or declare task success.

C1 owns HermiT verification. That verification does not certify source facts or reservation outcomes. [OaK section 3.2, Step 1 and Appendix A](https://arxiv.org/html/2608.22974v1).

## Paper procedure and live adaptation

The paper pairs each development query q with a corpus Cq. Each round divides sampled corpora into chunks. The schema-conditioned LLM Phi extracts typed candidates. The merge operation then combines them:

```text
G = Build(S, C) = merge(Phi_S(c1), ..., Phi_S(cn))
key(entity) = (entity_type, declared_primary_key_value)
```

Matching keys identify canonical nodes. The merge reconnects relations and removes duplicate assertions. [OaK section 3.2, opening paragraphs and Step 2](https://arxiv.org/html/2608.22974v1).

During inference, S and F stay fixed. The paper builds Gq from the unseen query's accompanying corpus. [OaK section 3.3](https://arxiv.org/html/2608.22974v1).

Our live adaptation grows Cq as the host obtains observations. C2 adds supported facts to G. The paper does not specify this acquisition or commit protocol.

Native tools remain available beside F. This changes the paper's sole-kernel data route. F has no direct access to task-provider APIs. [OaK section 3.1](https://arxiv.org/html/2608.22974v1).

Domain documentation defines field meanings. Case evidence supplies values. Bootstrap uses bounded sample responses or recorded development attempts. Each trial starts with its declared initial evidence. It does not receive an automatic copy of the development graph.

## Inputs and outputs

Use the shared integration envelope for terminal status and invocation identifiers. Persisted artifacts have identifiers, timestamps, and content hashes.

Use `component_status` to distinguish complete, partial, unsupported, or failed processing. A valid partial commit uses `status: succeeded` and `component_status: partial`. Its receipt lists missing or rejected evidence.

A failed request uses `status: failed` and commits no projection. These states do not establish task success.

| Input or output | Required payload |
| --- | --- |
| SchemaArtifact, input | Exact schema hash, identity and unit declarations, encoding coverage, verification receipt |
| ToolObservation, input | Stable observation and call IDs, tool version, request scope, raw-output reference, source IDs, timestamps, coverage, invocation status, effect status |
| IngestRequest, input | Evidence-context ID, expected parent revision or explicit empty context, extractor/mapping/policy versions, budget |
| GraphSnapshotRef, output | Context, committed revision, schema hash, dependency versions, observation references, coverage |
| IngestReceipt, output | Parent and new revisions, accepted and rejected candidates, unresolved identities, conflicts, diagnostics, processing status |

Keep invocation status separate from effect status:

```text
invocation_status = completed | failed | timed_out
effect_status = not_applicable | confirmed | rejected | unknown
```

Record effect-evidence references when available. An uncertain write must not become a confirmed effect fact. A failed observation may add provenance only. Its receipt remains visible even when it adds no domain facts.

## Internal procedure

1. Validate the schema, context, dependency versions, and remaining budget.
2. Find any receipt with the same replay key.
3. Preserve the original response and its content hash.
4. Retain source pointers, request scope, and timestamps.
5. Divide extraction input into bounded chunks.
6. Preserve record boundaries, source offsets, units, and provider namespaces.
7. Run Phi with the configured schema and model settings.
8. Validate candidate types, values, relation endpoints, units, keys, and source pointers.
9. Record unsupported fields and unresolved records in diagnostics.
10. Merge candidates with declared identity keys.
11. Reconnect relations and remove duplicate assertions.
12. Apply the frozen scope, source-priority, and freshness policies.
13. Preserve conflicting assertions and unresolved values.
14. Commit the accepted projection and receipt in one transaction.
15. Return the processing status and evidence limits.

Structured responses can remain structured inputs to Phi. Direct field mapping is a separately versioned future choice. Treat response content as evidence, never as instructions.

A source pointer permits inspection. It does not prove that an extracted fact matches its source. An unresolved conflict remains unknown through the typed view.

Chunking, extraction, and key-based merging follow the paper. Validation, source tracking, time policies, and transactional revisions are added requirements. [OaK section 3.2, Step 2](https://arxiv.org/html/2608.22974v1).

## Replay and atomic commits

The observation identity combines the evidence-context ID and observation ID. Bind that identity to one immutable payload hash.

Reject changed bytes under the same observation identity, even if projection dependencies change. New schema or extractor versions cannot bypass this rule.

The replay key adds schema, extractor, mapping, and policy hashes to the observation identity. Store the payload hash with that key.

For the same key and payload hash, return the existing receipt. Do not add assertions or create another revision. For the same key with different bytes, reject the request. Preserve the original observation and graph.

A new extractor or mapping version requires explicit reprojection. It must not silently replace the earlier result.

Serialize commits within each evidence context. In one transaction, compare the expected parent, write the projection, write its evidence manifest, and persist its receipt. Reject a stale parent without writes. Return that rejection for explicit rescheduling.

A lost acknowledgment must not cause a second commit. On replay, return the original durable receipt and committed revision. This requires atomic storage of the projection and receipt.

Local extraction retries consume the shared budget. Retain all attempts and costs. Processing completion does not establish complete domain knowledge.

## Storage and revision reads

An assertion retains its source, context, and applicable time. Account-local IDs require scoped keys, such as provider/account/type/external ID. Missing keys must not merge unrelated records into one null-key entity.

A quote belongs to its dates, party size, and currency. Do not store it as a timeless hotel price. Preserve original and normalized units. Unknown values must not become invented zeros.

Committed revisions must remain readable. Use versioned records and revision filters, or another explicit snapshot mechanism. A new revision label on overwritten facts is insufficient. Shared storage must isolate each trial's evidence.

The official Neo4j driver and parameterized Cypher perform graph reads. Projection, filtering, and aggregation can also use returned typed rows. Each F invocation binds one compatible committed revision.

Neo4j Browser displays the same entities, relations, and source records. Neo4j does not automatically supply OWL entailments. Any later materialization of logical consequences requires a versioned policy.

## Teaching example

This example uses the [canonical input fixture](00-task-surface-and-corpus.md). It is not benchmark evidence.

Case dev-001 requests an offer for four people, March 10-12, 2027. Its total budget is USD 420, including fees. It excludes reservation execution.

Search observation obs-search-001 supplies three offers. A conceptual projection is:

```text
Offer o3 --HAS_QUOTE--> LocalQuote obs-search-001/o3
LocalQuote obs-search-001/o3 --FOR_REQUEST--> Request dev-001
LocalQuote obs-search-001/o3 --SUPPORTED_BY--> Observation obs-search-001
```

The local quote ID comes from the observation and offer IDs. It is not a provider quote ID or a hotel ID. Values retain their source times.

| Offer | Maximum occupancy | Minimum nights | Quoted total | Availability |
| --- | --- | --- | --- | --- |
| o1 | 2 | 1 | USD 300 | Unknown |
| o2 | 4 | 3 | USD 340 | Unknown |
| o3 | 4 | Unknown | USD 390 | Unknown |

The following table shows a proposed function trace. Operator names come from the paper. These are data-flow steps, not literal call signatures. [OaK Appendix B](https://arxiv.org/html/2608.22974v1).

| Step | Operation and expected result |
| --- | --- |
| 1 | `lookup_entities` resolves o1, o2, and o3 in g1. |
| 2 | `traverse_relations` follows HAS_QUOTE and FOR_REQUEST. |
| 3 | `project_properties` reads totals, dates, currency, occupancy, minimum stay, and availability. |
| 4 | Function evidence checks retain unknown fields and reject incompatible quote contexts. |
| 5 | `filter_numeric` identifies o1's occupancy violation and o2's minimum-stay violation. o3 still needs minimum-stay evidence. |
| 6 | `filter_categorical` uses known availability values. o3 still needs availability evidence. |
| 7 | The function returns violations, unknowns, and sources. No offer has complete supporting evidence. |

F supplies ordered comparisons. Missing-evidence handling is our extension. Known violations remain visible when other constraints are unknown.

## Inference after construction

1. C4 loads frozen S and F.
2. C4 creates the request's evidence context.
3. The host's native search tool returns an observation.
4. C4 submits the observation to C2.
5. C2 commits g1 and returns its receipt.
6. C4 binds the dependent F call to g1.
7. The native detail tool returns o3's minimum nights and availability for the same stay.
8. C2 ingests obs-detail-001 into g2.
9. F evaluates the new evidence without changing its definition.
10. The agent returns o3 with supporting evidence.
11. C5 independently evaluates the selection.

The detail observation gives minimum nights 1 and availability true. Source times remain distinct from processing times.

This interleaving adapts the paper's build-then-execute sequence. [OaK section 3.3](https://arxiv.org/html/2608.22974v1). F does not fetch missing details. The [host executor](04-task-executor.md) integrates the host's tool choice.

An ingestion failure remains visible. C4 must not report failed evidence as incorporated. Frozen inference allows new observations, but no silent schema or extraction-policy changes.

Unsupported concepts produce diagnostics for a later package. Pagination and retrieval scope limit absence claims. An empty page does not prove that no suitable entity exists elsewhere.

## Independent verification

These are required tests, not completed test results. Use the [verification protocol](INDEPENDENT-VERIFICATION.md).

Supply a saved schema, observation envelope, ingestion request, and expected graph projection. Use a recorded Phi-response stub for deterministic tests. Use an isolated Neo4j database or context for transaction tests. C1, C3, C4, and C5 do not run.

| Test input or injected fault | Expected output | Measurable pass condition |
| --- | --- | --- |
| Valid observation and recorded Phi output | Attributable projection and receipt | All expected assertions match literal expected values and source references |
| Same replay key and same payload | Original receipt | Zero added assertions and zero new revisions |
| Same replay key and changed payload | Rejection | Original payload hash and graph revision remain unchanged |
| Commit succeeds but acknowledgment is lost | Original receipt on replay | Exactly one committed revision and one assertion set |
| Missing identity key | Unresolved identity | No null-key merge |
| Conflicting or outdated values | Visible conflict or unknown result | No unsupported current value is selected |
| Stale expected parent | Rejection | No graph or receipt commit for the rejected projection |
| New revision after g1 | g1 remains readable | The g1 result remains identical to its saved expected result |
| Same entity ID in another context | Isolated results | Zero facts from the other context |
| Timed-out write with unknown effect | Unknown effect preserved | Zero confirmed-effect assertions |

C2 may write graph revisions, observations, and receipts. It must not change S, F, or external provider state.

Recorded extraction results permit exact replay. New model extraction may differ. Report that difference separately from deterministic merge or transaction failures.

Record model settings, tokens, latency, retries, rejected candidates, graph operations, and artifact versions. Successful extraction is a component result. Task benefit requires separate paired evaluation.

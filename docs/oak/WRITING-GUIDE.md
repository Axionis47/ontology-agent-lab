# OaK document writing guide

Version 0.3.0. November 2, 2026.

## Purpose and review limit

Use this guide for the OaK design documents. Preserve source papers, recorded results, and previous review receipts.

ASD-STE100 uses writing rules and a controlled dictionary. Technical terms also need consistent meanings and correct grammatical use. See the [official description](https://www.asd-ste100.org/about_STE.html) and [official FAQ](https://www.asd-ste100.org/STE_faq.html).

This revision applies STE principles. Full conformity with ASD-STE100 is unverified. The review did not validate every word, approved meaning, or grammatical form against the complete Issue 9 dictionary.

The local document checks detect selected mechanical defects. They do not certify STE conformity or software correctness.

## Sentence rules

- Use short, active sentences.
- Give each instruction one action.
- Name the component that performs the action.
- Put a necessary condition before its instruction.
- Use the same technical term for the same item.
- Define an abbreviation before use.
- Keep identifiers and source titles unchanged.
- Do not use an em dash.

Use a maximum of 20 words for an instruction. This follows Issue 9, rule 5.1. See the [official standard, part 1, section 5](https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf).

For local review, use a 25-word ceiling for descriptive sentences. Treat this automated ceiling as a screening rule. Review tables, code, titles, and citations separately.

The STE dictionary restricts words by meaning and part of speech. For example, use “check” as a noun. See the [official FAQ](https://www.asd-ste100.org/STE_faq.html).

## Project terms

These definitions control project usage. They are not a claim that every term has passed a complete STE terminology review.

| Term | Meaning in this design |
| --- | --- |
| Schema, S | Domain types, properties, relationships, identity rules, and declared axioms |
| Domain graph, G | Observed facts and relationships under one schema |
| Operator, O | A reusable executable operation, such as entity lookup or numeric filtering |
| Function, F | A typed procedure that combines operators for a domain task |
| Host | The existing agent runtime that owns its model loop and native tool implementations |
| Adapter | The connection between host extension points and the OaK integration protocol |
| Coordinator | The owner of schedules, shared budgets, package assembly, and repair routing |
| Contract | The versioned requirements for an input, output, or permitted operation |
| Artifact | A saved output with an identifier, version, content hash, and location |
| Receipt | A saved record of an actual operation and its result |
| Fixture | Declared test input with independently specified expected results |
| Substitute | A declared replacement dependency used in an isolated test |
| Replay | Execution with saved inputs and declared dependency responses |
| Revision | One committed state of a graph within an evidence context |
| Evidence context | The permitted task, source, and observation scope for graph operations |
| Logical consistency | Absence of a contradiction under the encoded OWL axioms |
| Task success | An independently verified complete task result |
| Frozen package | A package whose pinned definitions, functions, and dependencies cannot change during evaluation |

## Requirement rules

For each requirement, identify its owner, trigger, input, expected output, and permitted writes. Name the failure result. Define the test and its evidence.

Use “must” for a required property. Use “may” for a permitted choice. Use “proposed” for behavior that lacks an implementation receipt.

Distinguish these states:

| State | Required evidence |
| --- | --- |
| Proposed | A written contract or algorithm |
| Implemented | An identified executable implementation |
| Verified | A saved test result against a named expectation and version |
| Not run | No execution receipt for the specified test |
| Unknown | Available evidence cannot establish the value or outcome |

Do not report a substitute test as a live-service result. Do not report document checks as algorithm tests. Do not report a consistent schema as a correct task result.

## Document structure

Each component document defines purpose, inputs, outputs, ownership, dependencies, algorithm, failure handling, and independent acceptance tests.

Shared contracts belong in [integration](INTEGRATION.md). Test records and release criteria belong in [independent verification](INDEPENDENT-VERIFICATION.md).

Keep paper claims beside their source citations. Label implementation choices and live-API adaptations explicitly.

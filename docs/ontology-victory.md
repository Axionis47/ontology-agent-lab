# Victory for the first ontology experiment

## Objective

Improve agent reliability by making implicit task relationships explicit.
The first result must show that a generated reasoning structure helps on unseen tasks.
A working OWL file, a successful scripted run, or a large test count is not sufficient.

The source is paper Sections 3.1 to 3.3 and Appendices A and B.
See the [paper](paper/source/oak-2608.22974v1.pdf).
The limits and numerical targets below are project decisions.
They are not results or requirements from the paper.

## First task surface

A task surface is the set of requests, source tools, data, and actions available to one agent.
The first surface is room eligibility for adults and one child.
The request specifies city, nights, adult count, child age, and a budget in USD cents.
The result contains all eligible room offers and their total costs.
If required evidence is absent or conflicting, the result must state that the data is incomplete.
An empty eligible set is valid only when complete data establishes that no offer qualifies.

Two existing free Model Context Protocol (MCP) servers provide database and file operations.
The SQLite server reads fictional inventory and child policies.
The Filesystem server writes the answer file.
After a valid answer, the agent inserts one local reservation for the cheapest eligible offer.
Equal prices use ascending offer ID order.
An incomplete answer or an empty eligible set permits no reservation.
The experiment has no real booking or paid MCP service.

## Victory conditions

| Condition | Required evidence |
| --- | --- |
| Generated kernel | A model drafts named relations and a typed function composed from generic operations. The prompt does not supply the finished relation map or function plan. |
| Repair | A failed construction case produces a recorded diagnosis and a revised artifact. The corrected artifact passes the complete construction suite. A scripted repair tests the mechanism but does not satisfy this model requirement. |
| Logical validity | HermiT checks the declared OWL axioms and unsatisfiable classes. Separate data checks cover missing facts and conflicting identities. |
| Native MCP | The agent discovers and calls tools through its own MCP client. A host loop that interprets JSON action text does not satisfy this condition. |
| Frozen inference | Schema and function hashes stay unchanged throughout the final evaluation. New runs replace facts, not rules. |
| Generalization | The final evaluation uses unseen source worlds and held-out combinations of known rules. Entity renaming and record reordering do not change the correct result. |
| Benefit | On answerable cases, full-kernel exact task success is at least 95%, exceeds baseline by at least 10 percentage points, and has a positive lower bound for a paired 95% confidence interval. |
| Failure handling | At least 95% of incomplete-data cases produce the required incomplete result. No invalid answer is accepted in the final evaluation. Report attempted invalid answers separately. |
| Repetition | Repeat the paired evaluation for three independently constructed kernels. Report all attempts, construction failures, and per-family results. Do not select only the best run. |

The percentage targets are initial decision thresholds for this surface.
They do not establish universal reliability or eliminate long-tail failures.
If baseline already reaches the ceiling, report an inconclusive reliability comparison.
Lower cost or fewer calls can be a separate result. They do not satisfy the reliability target.

## Architecture

```text
Construction inputs
Task requirements + granted MCP contracts + training examples
                         |
              Generate schema and function
                         |
       OWL validation + data checks + task evaluation
                         |
          Diagnose failure -> repair -> repeat
                         |
                   Freeze artifacts

Inference
Existing agent and starting prompt
             |
      Native MCP tool calls
             |
   Source adapters -> typed graph
             |
   Generated typed reasoning functions
             |
        Evidence and result
```

Source record formats and generic operations are developer code.
The generated artifact selects relations, traversals, comparisons, and arithmetic expressions.
The compiler checks the artifact and executes only declared operations.
It does not evaluate generated Python or shell commands.

An MCP adapter connects a source to the kernel.
It preserves the granted tool operation and validates returned records.
The function operates on source records and declared relations.
Its result includes source identifiers and an operator trace.

The paper routes task evidence and computations through the frozen kernel.
Native MCP describes the transport. It does not require an unrestricted bypass around the kernel.
Other tools can remain available when the task grants them.
Their results cannot establish a protected task decision until a declared adapter accepts them.
This is a project integration choice. The experiment must record this choice.

OWL does not check data completeness, numerical task rules, or the truth of source records.
The schema check and executable task checks have separate reports.
See the [OWL primer](https://www.w3.org/TR/owl-primer/).

## Protection against overfitting

Use three distinct sets of source worlds:

1. Construction: 24 worlds. Use these for drafting and repair.
2. Development: 24 worlds. Use these for kernel selection. Record all selection attempts.
3. Final evaluation: 240 worlds across ten scenario families. Freeze before opening the results.

Use different random seeds and identifiers for each set.
Split by complete source world, not by a paraphrase of the same world.
Keep the final examples and expected answers outside the agent's workspace.
Keep expected answers outside every MCP response.
The compiler must not import the reference scorer.

The final families cover ordinary mixtures, age boundaries, capacity boundaries, budget boundaries,
shared policies, changed relation targets, distractor records, identical duplicates,
missing links, and conflicting records.
Use held-out combinations of these conditions.
Do not expect the agent to infer a business rule that the task never supplied.

Add 10,000 inexpensive generated cases for executor checks.
Use an independent reference calculation.
Add relation-change, record-order, identity-renaming, and budget-monotonicity checks.
These checks test the executor. They are not 10,000 independent LLM observations.

After final results influence a repair, retire that final set.
Use a new final set before making a new generalization claim.
The suite is protected from the model by process inputs and tool access.
Local files are not a security boundary against a developer who edits the evaluator.

## Comparison and accounting

Use the same model, starting task requirements, source snapshots, and tool-call budget.
Use the same final answer format and independent scorer for all variants.
Measure proposed answers before any acceptance check.
This prevents a strict acceptance check from appearing to improve the agent's reasoning.

| Variant | Agent capabilities |
| --- | --- |
| Baseline | Native MCP source reads and ordinary ReAct reasoning. |
| Schema only | The same reads, plus the generated schema. No generated computation. |
| Full kernel | The same reads and schema, plus generated typed reasoning functions. |

Report exact task success, invalid proposals, accepted invalid results, incomplete-data handling,
tool calls, model tokens, elapsed time, and construction cost separately.
Count timeouts and missing final answers as failures.
An abstention on an answerable task is a failure.
Report each family before the aggregate score.
Compute paired intervals over independent source worlds, not over paraphrases or repeated runs.

## Current status

Four live Gemini construction variants generated and froze kernels.
Each passed HermiT, 24 construction worlds, 24 development worlds, and 10,000 executor cases.
The four constructions converge on one equivalent reasoning procedure.
Live mutation challenges show schema repair and function repair from trajectory feedback.
The baseline and strict ontology agent both completed a native MCP smoke episode.
The strict agent used the generated SQL view and committed a local reservation.
One later repair episode completed its task but hit the old eight-turn CLI limit.
The final pilot uses twelve turns for every condition and counts CLI errors as failures.
The recorded pilot is smaller than the planned final evaluation.
The CLI has local fixes for empty tool catalogs, required-hook failure handling,
and empty MCP result conversion.
The MCP server packages remain unchanged.
The first two pilots are retired integration diagnostics.
The third pilot uses a new seed and a frozen execution protocol.
It completed 38 of 60 planned episodes before the budget gate stopped new runs.
The full conditions passed 27 of 27 runs. Baseline passed 2 of 6. Schema only passed 2 of 5.
The case sets are incomplete and unequal. Use the matched-case results for comparisons.
All 36 submitted first answers were correct. Two runs submitted no answer.
Seven runs reached the CLI turn limit. Three already had the correct final database state.
These results support further tests of execution efficiency. They do not establish higher answer accuracy.
The conservative Gemini budget total is USD 36.26, including retained allowances for uncertain usage.
There are no open cost reservations. The local suite has 58 passing tests.
Keep the victory result `not_demonstrated` until all required evidence is present.

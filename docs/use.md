# User guide

[Documentation index](README.md)

## Before a run

Complete [Local setup](setup.md).
Use a tool environment that permits the intended read and write operations.
Discovery and training can change external data.
Oak does not create isolation for a supplied environment or establish that the environment is isolated.

A task surface states what the agent must do and which boundaries apply.
A tool grant permits the agent to use one Model Context Protocol (MCP) tool.
See [Terms](terms.md) for the other project terms.

## Create a task and agent

1. Select the intended demo user.
2. Create a task with its name, objective, and scope.
3. Open the task's **MCPs** tab.
4. Connect the necessary MCP servers.
5. Open **Agents**.
6. Select **Add agent**.
7. Enter the agent name and task surface.
8. Select the individual tools that the agent can use.
9. Select **Create agent**.

The task objective and scope remain fixed after creation.
The task name can change.
Use **Edit configuration** to change an agent's task surface or grants.
A configuration change can make earlier discovery and acceptance records ineligible.

Catalog refresh does not grant new tools or execute task operations.
Tools with equal names on different connections keep separate identities.
Removed tools remain visible as unavailable.

## Do the model connection check

1. Open the agent.
2. Find **Model connection**.
3. Select **Check connection**.
4. Read the result and the recovery instructions.

The check sends a fixed model request.
It does not send task content or execute MCP tools.
A successful connection check does not establish successful discovery or training.

## Complete discovery

1. Open **Discovery**.
2. Enter a label for the supplied environment.
3. Set the cost, call, active-time, and clarification limits.
4. Select **Start discovery**.
5. Examine the observations, requirements, and proposed schema.
6. Examine the proposed function needs in **Schema** and **Review**.
7. If Oak asks a blocking question, enter the necessary clarification.
8. Select **Answer and resume**.
9. Wait for a ready discovery result.

Discovery proposes declarations from actual evidence.
A user answer can clarify intent. It cannot prove a tool capability or remove an explicit task boundary.
An incomplete draft can remain available for inspection without becoming ready for training.

| Control | Effect |
| --- | --- |
| Pause | Prevents the next call. An active call can still finish. |
| Resume | Continues the same run with saved observations and counters. |
| Stop | Stops execution and keeps the partial result. |
| Increase a limit | Changes the total allowance for the same run. It does not reset usage. |

Pause and Stop do not reverse external writes.
An unknown write outcome stops the run without an automatic retry.
After a backend interruption, Oak keeps the records without call replay.

## Save training cases

1. Open **Training** after discovery is ready.
2. Add a case with a query, selected tools, and task-success description.
3. Select case tools only from the agent's granted tools.
4. Save the case.
5. Repeat these steps for every training case.

The task-success description states the necessary answer, external outcome, or both.
The trainer is responsible for its correctness.
The internal evaluator uses this description and the recorded evidence.
The trainer does not supply a repair checklist.

## Start training

Training repeats cases with a baseline and candidate harnesses.
Each repeated case must start with comparable environmental conditions.
A server preparation adapter can reset a controlled environment.
The comparable-state option is a trainer assertion. Oak does not independently establish its correctness.

1. Prepare the environment for repeated episodes.
2. Set the training limits.
3. If the environment stays comparable, select the comparable-state option.
4. Select **Start training**.
5. Examine case outcomes and execution records in **Results**.
6. Confirm that the run produced an accepted harness.

Oak first executes all saved cases with the basic agent.
It reuses a compatible accepted candidate when one is available.
Otherwise, it constructs the minimum initial definitions from discovery and baseline evidence.
It does structural, formal, coverage, and offline execution checks.
It then executes all cases with the candidate and evaluates their outcomes.
Oak reviews a failure before it requests a patch.
One supported gap is sufficient for a targeted change.
Missing evidence, tool errors, agent-use errors, and unresolved causes do not authorize changes.
A correction must pass replay with the same recorded observations.
A successful route does not create a helper function.

For acceptance, all saved cases must pass.
Every function and operation binding must also have execution coverage.
A completed run can reach its round limit without an accepted harness.

## Examine definitions and changes

1. Open the saved training run.
2. Select a candidate in **Candidate versions and repairs**.
3. Open **Definition catalog**.
4. Expand a definition to inspect dependencies, supporting evidence, and recorded use.
5. Select an evidence link to open its saved event.
6. Open **Change history** to inspect reviews, routes, unchanged decisions, and rejection reasons.

A proposed cause is a model explanation.
The verification record states which runtime checks support a change.
Earlier runs can lack a repair review.
Reloading the page reads saved records and does not start training.

## Use an accepted harness

1. Select **Try accepted version**.
2. Enter a new query.
3. Select the necessary tools from the available list.
4. Set the inference limits.
5. Start inference.
6. Examine the answer, tool outcomes, function results, and evidence references.

For inference, a current `oak.candidate.v3` acceptance record is necessary.
The saved inputs, grants, definitions, validation reports, and runtime versions must agree.
The interface shows a reason when inference is unavailable.

Inference starts a fresh evidence graph and keeps the accepted definitions fixed.
It does not run construction, repair, or the training evaluator.
The agent can call a saved function or query several existing relations.
Temporary graph queries do not change the accepted function library.
A historical candidate must pass validation under the current runtime before inference.
A successful write response can supply evidence without a separate read.
An unknown action outcome does not establish success.

## Examine a failure

1. Open the affected run.
2. Read its stop reason or failed check.
3. Open the first relevant call or function record.
4. Compare its arguments with the original query and granted tools.
5. Examine the cited observation and validation report.
6. Select the next action from the recorded cause.

Do not repeat an uncertain external action solely because the interface shows a failure.
Use the provider's supported reconciliation method to establish the actual outcome.

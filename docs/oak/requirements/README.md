# OaK requirements

These StrictDoc sources define requirements, component ownership, contract dependencies, architecture decisions, and acceptance tests.
Use the [implementation specification](../implementation/README.md) for algorithms and payload details.
The [task contract](../implementation/TASK-CONTRACT.md) governs the multiple-task boundary; its changes still need to be applied throughout the older component requirements.
For primary paper inference, the task contract and [C4 primary protocol](../implementation/C04-execution.md#primary-kernel-inference), including C4-R09/C4-R10 and C4-T18/C4-T19, take precedence over older managed-fixture native-action and optional-function descriptions. Those fixture requirements remain scoped to their declared profile and do not establish the primary runtime.

| Source | Purpose |
| --- | --- |
| [00-system.sdoc](00-system.sdoc) | System requirements and acceptance tests |
| [01-contracts.sdoc](01-contracts.sdoc) | Named handoffs and their detailed specifications |
| [02-decisions.sdoc](02-decisions.sdoc) | Architecture choices and constraints |
| [03-agent-boundary.sdoc](03-agent-boundary.sdoc) | Agent-loop compatibility invariants |
| `C00.sdoc` through `C11.sdoc` | Component requirements and acceptance tests |
| [oak.sgra](oak.sgra) | StrictDoc grammar |

Keep requirement IDs stable and update the corresponding component specification when changing a requirement.
Each acceptance test must identify the requirements it checks. A specified test is not a passing test result.
Executable local tests are in [tests/oak_contracts](../../../tests/oak_contracts).

# OaK requirements

These StrictDoc sources define requirements, component ownership, contract dependencies, architecture decisions, and acceptance tests.
Use the [implementation specification](../implementation/README.md) for algorithms and payload details.
The [task contract](../implementation/TASK-CONTRACT.md) governs the multiple-task boundary; its changes still need to be applied throughout the older component requirements.

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

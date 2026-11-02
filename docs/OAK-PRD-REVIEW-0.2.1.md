# OaK onboarding clarification review

Version 0.2.1, November 2, 2026. Proposed integration clarification. The [PRD](OAK-PRD.md) now links the [host onboarding contract](oak/08-agent-onboarding.md). [Version 0.2.0](OAK-PRD-REVIEW-0.2.md) and [version 0.1.0](OAK-PRD-REVIEW.md) receipts remain historical.

## Review findings

Two specialist agents reviewed the runtime boundary and adapter semantics. The clarification distinguishes model-visible tool contracts from executable bindings and from interception hooks. C4 integrates the host's existing loop rather than requiring a replacement planner or a literal next_operation method.

Required capabilities cover namespaced F registration, additive versioned context, pinned task/graph binding, actual result delivery, ingestion ordering, lifecycle events, and observable traces. Guarded mode additionally requires pre-action and typed-finalization control. Delayed after-the-fact telemetry cannot provide pre-action enforcement.

The document distinguishes compound/delegated tools with nested events from opaque tools, and prevents outer summaries from being treated as inner provider receipts. It retains memory provenance and source age, and reports black-box integration limits. A concrete runtime adapter is still to be selected and implemented.

The paper supplies the agent/kernel abstraction in [sections 3.1 to 3.3](https://arxiv.org/html/2608.22974v1). It does not supply this universal host-adapter protocol. All named adapter operations are proposed interfaces, not assertions that an existing SDK implements them.

## Research integration

The six synthesis questions are addressed by the [narrative update](oak/STATUS.md): missing runtime attachment semantics motivated the change; version 0.2.1 adds exact integration contracts; C4 and future host adapters are the planned consumers; no evaluation denominator, result, uncertainty, or new task-execution cost exists; context/memory/observability/enforcement are explicit controls; the benefit hypothesis remains unrun and unresolved.

No input corpus, shared study/claim register, implementation, or experiment result changed. No model or provider task was launched. Document validation covers references, formatting, example preservation, and recorded hashes, not runtime correctness.

## Narrative hashes

| State | SHA 256 |
| --- | --- |
| Before | `879810b9bccda88fd20de324996d0ce242d5d8898d2b6883e39da01f115e8ffe` |
| After | `01d09d975a4c9ae1957b042d448c76acde642c3e536a09abdf0d077cf1a79fa6` |
| Study register unchanged | `6e4a165cdbc295c83d5c1ac0a78ae68fffa1a81f8fa5668b8d87d989de5f6963` |
| Claim register unchanged | `b376ce38fbc18a92773778c59da4dcd26f16c1b91f38529cf006d281b1cccdef` |

## Artifact hashes

| File | Before SHA 256 | After SHA 256 |
| --- | --- | --- |
| `docs/OAK-PRD.md` | `dbafca8931f7e309c9a7851551a22ce6ab9eac0ea2e97df35060cb2eaaa41b67` | `d6f954c4a4b173404c93a1b5db8605ee2c0c119509479fececd84d6521cce465` |
| `docs/oak/04-task-executor.md` | `64a835364464735b5b694ad301e1d7dfb2b04a34901826aa2237fedc7f7fa04b` | `435f961e47197f75b5b2a47a5463c97c641feab303817655250171862338b9dd` |
| `docs/oak/INTEGRATION.md` | `ad934a1af9a665463aab39f00ef1fb7cd16a24d92ce538affe4a5ab0e4395311` | `8dd989d5f4312da50e6842bb8e27d8682c9dd9cd142435ac5e8890492addad92` |
| `docs/oak/08-agent-onboarding.md` | `new file` | `732979f72e73b960c3b7175d631d9d434dc0551c447c3b617136eb9f7409b18f` |

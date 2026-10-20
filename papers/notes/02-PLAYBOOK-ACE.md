# ACE: learning a playbook from task execution

ACE changes the instructions available to an agent, rather than its model weights. Its useful idea is to turn execution feedback into small, individually tracked playbook entries. Its important limitation is that preserving and adding guidance does not guarantee that guidance is correct or compact.

Source: [ACE, arXiv 2510.04618v3](../pdfs/2510.04618v3.pdf), March 29, 2026, published at ICLR 2026. Page references below use the PDF's printed pages. Status: paper reading only; no local implementation, benchmark replication, or experimental model calls.

## What the authors actually tested

The main agent benchmark was **AppWorld**. Input is a natural-language task plus an application environment and API documentation. The agent emits Python API calls over multiple steps and, where requested, a final answer. Official checks measure Task Goal Completion and Scenario Goal Completion on normal and challenge splits.

The main domain benchmarks were **FiNER**, labeling financial-document tokens among 139 XBRL entity types, and **Formula**, answering numerical financial questions. These use exact-match accuracy. Additional offline studies use DDXPlus for medical reasoning and BIRD-SQL for natural-language-to-SQL generation. DDXPlus uses accuracy; their BIRD-SQL evaluation uses a GPT-4o-mini judge, which introduces grader uncertainty. These are benchmark tasks, not evidence of safe deployment in these domains. [Sections 4.1-4.2, p. 6; Appendix A.2, pp. 16-18](../pdfs/2510.04618v3.pdf).

Comparators include the unchanged base model, in-context demonstrations, MIPROv2, GEPA, and Dynamic Cheatsheet. Not every comparator appears in every setting. AppWorld variants share the official ReAct agent. The main ACE study uses DeepSeek-V3.1 in non-thinking mode for Generator, Reflector, and Curator, avoiding a stronger teacher as the explanation for improvement.

**Offline:** construct the playbook from training examples, then evaluate on separate test examples with pass@1. **Online:** shuffle the test stream identically across methods, predict each answer using the current playbook, then update from that example. Consequently, online results measure adaptation through a stream, not one frozen playbook on an untouched test set. Ground-truth-label access differs across explicitly labeled conditions. [Sections 4.1-4.4, pp. 6-8](../pdfs/2510.04618v3.pdf).

## Follow one example through the mechanism

The paper's prompt illustrations include the task **“Find money sent to roommates since Jan 1 this year.”** The illustrated failure identifies roommates from payment descriptions instead of authoritative Phone contacts, producing the wrong total. This is an example embedded in prompts, not a published complete execution record or a separately verified benchmark outcome. [Figures 10-11, pp. 28-29](../pdfs/2510.04618v3.pdf).

1. **Generator attempts the task.** It receives the task, application instructions, and current playbook, then makes API calls. The illustrated mistake uses transaction wording to infer relationships.
2. **Feedback arrives.** Tests or execution results expose a mismatch. Ground-truth code is available in the illustrated Reflector prompt; it is not available in every evaluated condition.
3. **Reflector proposes a lesson.** It identifies the observable mismatch and proposes consulting the Phone relationship data before filtering payments. Referenced entries can receive helpful, harmful, or neutral labels. These labels are model judgments.
4. **Curator creates a delta.** It checks the existing playbook and proposes an addition only if the guidance is missing. Figure 11 shows an `ADD` operation with a section and content, rather than a replacement of the entire document.
5. **Software merges it.** Non-model logic applies itemized deltas and assigns identifiers. Deterministic merging makes the edit reproducible; it does not establish its semantic truth.
6. **Refinement controls redundancy.** Semantic-embedding comparisons detect duplicate bullets. Refinement can run after updates or when a context-size threshold is reached. Metadata counters can guide maintenance.
7. **A later task receives the playbook.** The visible Generator prompt inserts `{{ playbook }}` directly. It asks the model to apply relevant sections. Although the architecture supports fine-grained retrieval, these prompts do not establish that only a small retrieved subset is loaded. [Sections 3.1-3.2, p. 5; Figures 9-11, pp. 27-29](../pdfs/2510.04618v3.pdf).

What persists is the evolving playbook: bullet content, identifiers, sections, and feedback counters. What enters a decision is the supplied playbook plus the current task and execution context. Model weights stay unchanged.

## What our visibility policy requires

Retain the task, permitted feedback, playbook version before, proposed operation, exact committed difference and receipt, counter changes, deduplication decisions, and exact later model-visible playbook. Separate **proposed, saved, loaded, referenced, and demonstrated useful**. The prompts request internal reasoning; our [visibility policy](VISIBILITY-POLICY.md) instead records observable actions and concise evidence-backed explanations, without collecting private chain-of-thought.

A helpful counter is not proof of use or causal improvement. Table 2 reports online FiNER without labels at 67.3 accuracy versus 70.7 for the base model. Incorrect feedback can accumulate harmful guidance. Growth also needs explicit pruning; Appendix A.6 tests context thresholds rather than proving indefinite scalability. A successful later task needs a controlled comparison before attributing success to the new entry.

## Three inspection questions

- **Did ACE learn by retraining?** No, it changed supplied context.
- **Does an accepted delta prove the lesson is correct?** No, merge validity and task validity are separate.
- **What remains unverified locally?** Every execution, update receipt, later reuse, and performance result; this is a source walkthrough only.

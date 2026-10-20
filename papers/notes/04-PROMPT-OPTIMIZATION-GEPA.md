# Learning from Evaluated Prompt Revisions

Reading note for GEPA, arXiv 2507.19457v2. This is a paper walkthrough, not a local replication. The authors' measurements below belong to their evaluation. No experiment was run for this note. Read it with our [visibility policy](VISIBILITY-POLICY.md).

## The problem

Imagine an instruction that sometimes works and sometimes fails. A model can propose a clearer instruction, but sounding clearer does not establish improvement. GEPA uses execution feedback to propose revisions, tests candidate instructions, and keeps candidates that perform well on different evaluation instances. The accumulated knowledge resides in selected instructions and their candidate history; the task model's weights do not change during prompt optimization.

## What the authors actually tested

The six main benchmarks were HotpotQA (multi-hop questions), HoVer (retrieval-based claim verification), IFBench (instruction constraints), PUPA (privacy-aware delegation), AIME-2025, and LiveBench-Math. Each benchmark was paired with a task system and a feedback function. The main models were Qwen3 8B and GPT-4.1 Mini. Comparisons included unoptimized baselines, MIPROv2, GRPO, and, where applicable, TextGrad and Trace/OptoPrime. Metrics were benchmark task scores and optimization rollouts. [Paper, Section 4 and Tables 1-2, PDF p. 8](https://arxiv.org/abs/2507.19457v2#page=8).

The optimizer could inspect training inputs and labels. Validation scores helped select candidates, while direct access to validation-instance content was restricted. Test results assessed the selected system separately. This is important: a validation score used repeatedly for selection is not untouched test evidence.

## A concrete example shown in the paper

Figure 5 shows a prompt-evolution branch for PUPA. The task system reformulates a private user request for an external model, aiming to preserve usefulness while withholding private information. The figure starts with a general privacy instruction and shows revisions adding more explicit handling of identifying details, abstraction, and task utility. Full candidate instructions are referenced in Appendix K.1. This is an actual optimization illustration from the paper, not an invented invoice example or a complete per-request execution record. [Figure 5, PDF p. 7](https://arxiv.org/abs/2507.19457v2#page=7).

Follow these observable steps:

1. A parent prompt defines how the task system should reformulate requests.
2. The system runs training examples and produces outputs, scores, and feedback about failures.
3. A reflection component uses that feedback to propose a changed prompt. The proposed instruction is an inspectable artifact.
4. The candidate is evaluated. Software records scores and its relationship to the parent.
5. Selection retains useful diversity: a candidate that leads on particular instances may remain valuable even when it is not best on average. This reduces dependence on a single current winner.
6. The selected prompt is used for later task execution. The historical failed requests need not all appear in that task's input.

These are candidate-selection mechanics, not an automatic production-deployment approval policy. [Sections 3 and 3.1, PDF pp. 4-8](https://arxiv.org/abs/2507.19457v2#page=4).

## What we can inspect

The paper exposes prompt revisions, candidate relationships, benchmark protocols, and aggregate results. For our visibility policy, a runnable reproduction would additionally need exact case identities, rendered requests, feedback versions, candidate scores, selection decisions, and the prompt actually used on each test case. A diagram alone cannot establish those bindings or why an individual answer succeeded. Do not reproduce hidden reasoning as a visibility requirement.

## The result can reverse by task

Table 1 reports Qwen3 8B AIME-2025 scores of 32.00 for GEPA and 38.00 for GRPO. Table 1 also shows that adding merge can worsen particular task scores. An aggregate gain is not a guarantee for each domain, and a selected prompt can overfit its evaluation conditions. The broader comparison also changes optimization resources and mechanisms; it is not proof that every difference is caused solely by reflection. [Table 1, PDF p. 8](https://arxiv.org/abs/2507.19457v2#page=8).

Use this approach when you have a repeated task, a meaningful feedback signal, and separate evaluation data. If evaluation rewards fluent explanations while missing privacy leakage, optimization may improve the wrong property.

## Questions to answer while reading

- **Where does the learning persist?** In revised prompts and selection history, rather than updated task-model weights.
- **Why preserve several candidates?** Different instructions can succeed on different instances; a single aggregate winner can hide complementary strategies.
- **What would reject a plausible improvement?** Worse validation or test behavior, leakage, a regression on a critical slice, or insufficient evidence for the claimed benefit.

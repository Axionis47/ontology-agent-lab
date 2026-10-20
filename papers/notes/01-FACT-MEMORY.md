# Fact memory with Mem0 and Zep

Mem0 and Zep turn conversation history into maintained information that can be retrieved for a later question. They investigate remembering facts across sessions. Their evaluations do not establish that an agent learns a better working procedure. This is a reading walkthrough, with no local replication, model execution, or measured local result.

## What the authors tested

**Mem0:** The input is a multi-session conversation, followed by questions about its contents. The output is an answer compared with a reference answer. LoCoMo contains ten extended conversations, averaging about 26,000 tokens and roughly 200 questions each. The evaluation covers single-hop, multi-hop, temporal, and open-domain questions; adversarial questions were excluded. Baselines include raw-history retrieval with different chunk sizes, full conversation context, and other memory systems. Metrics include F1, BLEU-1, an LLM judge score, retrieved tokens, and search plus answer latency. GPT-4o-mini powers the reported memory operations. [Mem0, sections 2.1 and 3, PDF pp. 5–9](https://arxiv.org/abs/2504.19413v1).

**Zep:** The same broad task is tested on two datasets. Deep Memory Retrieval has 500 conversations, each with five sessions and up to twelve messages per session, plus a question/reference-answer pair. LongMemEval-S has much longer histories, averaging about 115,000 tokens, with questions about preferences, updated information, temporal relationships, and information spread across sessions. Baselines include full context, session summaries for DMR, and reported MemGPT results. An LLM judge evaluates answers; the paper also reports latency and context tokens. Zep constructs graphs with GPT-4o-mini and tests answers with GPT-4o-mini, GPT-4o, and GPT-4-turbo in specified comparisons. [Zep, sections 4–4.3, PDF pp. 5–7](../pdfs/2501.13956v1.pdf).

## Follow one paper illustration

Mem0 Figure 1 describes a person who previously established vegetarian and dairy-free preferences, then asks for dinner suggestions in another session. This is the authors' illustration of the motivation, not a published benchmark case with a complete execution record. Do not treat the pictured recommendation as a measured result. [Mem0, Figure 1 and introduction, PDF p. 2](https://arxiv.org/abs/2504.19413v1).

Trace that illustration through Mem0's documented mechanism:

1. **Incoming evidence:** A new message pair arrives. The extractor also receives a conversation summary and recent messages. In the reported configuration, the recent window is ten messages.
2. **Candidate memory:** A model extracts useful facts from the exchange. In our on-paper interpretation of the illustration, the candidates concern dietary preferences. The PDF does not expose this illustration's actual extractor response.
3. **Related knowledge:** For each candidate, software retrieves ten similar memories. This narrows the comparison instead of placing all prior cases together in context.
4. **Proposed operation:** The model selects ADD, UPDATE, DELETE, or NOOP. An existing equivalent preference may require no change; complementary information may enrich a record. These are possible operations, not recorded outputs for Figure 1.
5. **Commit:** Software executes the selected operations. The observable object to inspect would be the stored record before and after, including unchanged or deleted records.
6. **Later reuse:** When the dinner question arrives, relevant stored information supplies answering context. Retrieval and answer correctness are separate boundaries. [Mem0, section 2.1, PDF pp. 3–5; Algorithm 1, p. 21](https://arxiv.org/abs/2504.19413v1).

Zep represents facts as relationships between entities, linked to original episodes. It resolves duplicate entities and facts, extracts temporal information, and invalidates overlapping contradictory relationships. It preserves historical validity separately from database creation and expiration times. Retrieval searches, reranks, and constructs text containing relevant facts, date ranges, and entity summaries. A timestamp records a temporal claim; it does not independently verify that claim. [Zep, sections 2–3, PDF pp. 2–5](../pdfs/2501.13956v1.pdf).

## Work through it without executing anything

Draw six boxes: source message, extracted preference, related memories, proposed operation, saved record, later answer context. Mark every unavailable Figure 1 artifact as unknown. Then ask what happens when a preference changes or applies only to a guest. Those are hypothetical counterexamples, not paper results. Check whether the source supports an update to the user's preference or a separately scoped fact. Do not invent model responses or score the exercise as an experiment.

## Results and visibility limits

Mem0 Table 2 reports judge scores of 66.88% for Mem0, 68.44% for its graph variant, and 72.90% for full context. Efficiency gains therefore do not establish superior accuracy over full history. [Mem0, Table 2, PDF p. 11](https://arxiv.org/abs/2504.19413v1). Zep reports 71.2% versus 60.2% for GPT-4o on LongMemEval-S, but assistant-information questions regress. [Zep, Tables 2–3, PDF p. 7](../pdfs/2501.13956v1.pdf).

The PDFs provide architectures, selected prompts, configurations, and aggregate results. They do not supply complete per-case proposal, commit, retrieval, and grading records for this illustration. Zep also describes twenty retrieved items in section 4 but ten in its DMR discussion. Those details need resolution before replication. Our [visibility policy](VISIBILITY-POLICY.md) requires exact records before claiming a local improvement.

**Conditional takeaway:** Fact memory is useful when later questions depend on earlier information and full-history context is costly. These results do not establish trustworthy procedure learning, correct updates in every case, or a universal advantage over full context.

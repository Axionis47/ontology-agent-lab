# Trace2Skill turning execution experience into a reusable procedure

**Trace2Skill learns a maintained procedure from many task executions while keeping model weights fixed.** Instead of retrieving another similar case every time, it consolidates proposed lessons into a skill directory: `SKILL.md`, supporting references, scripts, and assets. This is a paper walkthrough, with no local replication or measured local model run.

## What the authors tested

The main task is spreadsheet manipulation. Input is a task description and workbook files; output is an edited workbook evaluated against the expected result. SpreadsheetBench-Verified has **400 tasks: 200 for skill evolution and 200 held out for testing**. The authors also report full SpreadsheetBench Soft scores, the proportion of subproblems passed, and Hard scores, requiring all subproblems to pass. These evaluations should not be conflated with the explicitly held-out Verified split.

For transfer, WikiTableQuestions asks compositional questions about Wikipedia tables. The authors convert its inputs and expected outputs to spreadsheet format. Additional studies cover mathematical problems and questions about document images. Results use benchmark-specific evaluation criteria; the spreadsheet setup reports three seeds. [Source: sections 3.1-3.4, PDF pages 5-8](../pdfs/2603.25158v2.pdf#page=5).

## Follow one visible example

**Original paper example, not our invented task:** Appendix B.2.3 presents a representative patch from a failure where an agent deleted rows outside the requested range and confused partly empty data rows with completely empty padding rows. The patch uses `F14:M83` as an illustrative range. The appendix does not provide the complete original workbook and execution as a self-contained measured case. [Source: PDF pages 17-18](../pdfs/2603.25158v2.pdf#page=17).

1. **Collect executions.** A fixed agent runs the evolution tasks using an initial skill. Recorded actions, observations, files, and correctness results divide executions into successes and failures. Test tasks stay outside this learning pool.
2. **Analyze each execution independently.** Every analyst sees the same frozen initial skill and one execution. A success analyst proposes reusable patterns. An error analyst can inspect files, compare against the expected output, and try a minimal correction. Cases without a valid failure analysis are excluded from the error-patch pool.
3. **Propose a patch.** For the row-deletion example, the proposal adds range-boundary enforcement, checks before deletion, and checks that adjacent data and padding survive. A proposal is still only a candidate lesson.
4. **Merge proposals.** Analysts do not edit each other's work. Merge agents consolidate batches, remove duplicates, resolve competing edits, and prioritize recurring patterns. The example joins related structural-edit lessons; the final procedure also includes descending row-deletion order to prevent index shifts.
5. **Apply the update.** Software translates the consolidated patch into edits. It rejects nonexistent file references, withholds overlapping line edits, and checks skill format. Common procedures enter the main document; uncommon details can enter linked reference files.
6. **Use the new skill on other tasks.** The agent receives the evolved skill and produces another workbook. Independent benchmark checks establish whether that workbook is correct. [Pipeline: sections 2.2-2.4, PDF pages 4-5; example consolidation: section 4.4 and Appendix B.3, pages 11 and 18-20](../pdfs/2603.25158v2.pdf#page=4).

## What the comparison establishes

Comparisons include no skill, Anthropic's human-written spreadsheet skill, a model-drafted skill, error-only, success-only, and combined consolidation. Ablations compare sequential editing, a ReasoningBank-style retrieval baseline, and single-call error analysis. Success rate, Soft/Hard scores, and transfer performance measure outcomes.

For the 122B model, human-written skill performance on Verified is 48.33%; its combined deepening adds 21.50 percentage points. Improvements are not universal: 122B-authored success-only deepening loses 21.83 points there. On DocVQA, the 35B-authored skill reduces the 35B user's reported accuracy by 6.2 points. Cross-model and reformatted-table transfer are evidence within those settings, not a portability guarantee. [Tables 1 and 3, PDF pages 6 and 8; ablations, pages 8-10](../pdfs/2603.25158v2.pdf#page=6).

## What remains visible and what remains uncertain

**Creating a skill and selecting a skill are separate problems.** Appendix B.1 says the relevant `SKILL.md` is preloaded; the agent still discovers linked resources. This study does not establish that a system can reliably choose this skill from a large library. [PDF page 16](../pdfs/2603.25158v2.pdf#page=16).

“Conflict-free” includes syntactic guards. Semantic reconciliation still relies on a model, and usefulness requires evaluation. Under our [visibility policy](VISIBILITY-POLICY.md), prompts, patch excerpts, applied differences, splits, and aggregate outcomes are helpful. Complete per-case commit receipts, excluded-case accounting, and exact later section usage are not established by those excerpts. The authors explicitly identify missing per-patch causal attribution and section-use tracing. [Section 6, PDF page 12](../pdfs/2603.25158v2.pdf#page=12).

## Three inspection questions

1. **Did the model retrain?** No. The skill artifact changes while weights remain fixed.
2. **Does a clean merge prove a good lesson?** No. Valid edits can encode harmful guidance.
3. **Did this exact checklist cause the gain?** Unknown. The paper measures whole-skill outcomes and identifies individual contribution tracing as future work.

"use client";

import type { DiscoveryDetail } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { EvidenceLinks } from "./discovery-inspector";
import { DiscoveryModeling } from "./discovery-modeling";
import { adaptSchema, evidenceIssues, type Selection } from "./schema-adapter";

export function DiscoveryReview({
  detail,
  onInspect,
  onAnswer,
}: {
  detail: DiscoveryDetail;
  onInspect: (item: Selection) => void;
  onAnswer: () => void;
}) {
  const model = adaptSchema(detail.schema_proposal ?? {});
  const issues = [...model.issues, ...evidenceIssues(detail)];
  const gaps = [
    ...model.gaps.map((gap) => ({ gap, scope: "schema" as const })),
    ...(detail.requirements?.gaps ?? []).map((gap) => ({
      gap,
      scope: "requirements" as const,
    })),
  ];
  const pending = detail.questions.filter(
    (question) => question.answer === null,
  );
  const uncertain = detail.calls.filter(
    (call) =>
      call.kind === "mcp" && ["failed", "unknown"].includes(call.status),
  );
  return (
    <div className="space-y-6">
      <DiscoveryModeling detail={detail} onInspect={onInspect} showChoices />
      <section aria-label="Questions for you" className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-medium">Questions for you</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              These questions resolve task intent. Your answers are saved as
              user clarifications.
            </p>
          </div>
          {pending.length > 0 && detail.run.status === "paused" && (
            <Button size="sm" onClick={onAnswer}>
              Go to answer fields
            </Button>
          )}
        </div>
        <p className="text-xs">
          {pending.length} awaiting an answer ·{" "}
          {detail.questions.length - pending.length} answered
        </p>
        <div
          className="max-h-80 space-y-3 overflow-auto"
          tabIndex={0}
          aria-label="Question history"
        >
          {detail.questions.map((question) => (
            <article key={question.id} className="space-y-2 border p-3 text-xs">
              <p className="font-medium">{question.question.text}</p>
              <p className="text-muted-foreground">
                {question.question.why_needed}
              </p>
              {question.answer === null ? (
                <p>
                  Awaiting an answer
                  {detail.run.status === "paused"
                    ? ". Use the answer fields above."
                    : "."}
                </p>
              ) : (
                <>
                  <p className="text-primary">Answer: {question.answer}</p>
                  <p className="text-muted-foreground">
                    User clarification · {question.answered_by}
                    {question.answered_at
                      ? ` · ${new Date(question.answered_at).toLocaleString()}`
                      : ""}
                  </p>
                </>
              )}
              {question.answer === null &&
                question.question.unresolved_detail && (
                  <p>Point to clarify: {question.question.unresolved_detail}</p>
                )}
              <button
                className="inspection-link"
                onClick={() =>
                  onInspect({
                    kind: "evidence",
                    ref: { source: "question", id: question.id, path: "" },
                  })
                }
              >
                Inspect question and source
              </button>
            </article>
          ))}
          {!detail.questions.length && (
            <p className="text-xs text-muted-foreground">
              No questions were asked.
            </p>
          )}
        </div>
      </section>
      <section aria-label="Evidence gaps" className="space-y-3 border-t pt-5">
        <h3 className="text-sm font-medium">Evidence gaps</h3>
        <p className="text-xs text-muted-foreground">
          Missing evidence or capabilities recorded by discovery. A user answer
          cannot establish an external fact.
        </p>
        <div
          className="max-h-80 space-y-3 overflow-auto"
          tabIndex={0}
          aria-label="Evidence gap list"
        >
          {gaps.map(({ gap, scope }) => (
            <article
              key={`${scope}:${gap.id}`}
              className="space-y-2 border p-3 text-xs"
            >
              <p className="text-muted-foreground">
                {scope === "schema" ? "Schema proposal" : "Requirements"} ·{" "}
                {gap.blocking ? "Blocking gap" : "Limitation"}
              </p>
              <button
                className="inspection-link text-left"
                onClick={() => onInspect({ kind: "gap", id: gap.id, scope })}
              >
                {gap.message}
              </button>
              <EvidenceLinks
                refs={gap.evidence ?? []}
                onOpen={(ref) => onInspect({ kind: "evidence", ref })}
              />
            </article>
          ))}
          {!gaps.length && (
            <p className="text-xs text-muted-foreground">
              No evidence gaps were recorded. This does not establish complete
              coverage.
            </p>
          )}
        </div>
      </section>
      <section aria-label="Package checks" className="space-y-3 border-t pt-5">
        <h3 className="text-sm font-medium">Package checks</h3>
        <p className="text-xs text-muted-foreground">
          Broken references and unsuccessful calls are validation or execution
          issues. They are separate from user questions.
        </p>
        <div className="max-h-80 space-y-2 overflow-auto text-xs" tabIndex={0}>
          {issues.map((issue, index) => (
            <p key={index}>
              <button
                className="inspection-link text-left"
                onClick={() => onInspect(issue.item)}
              >
                {issue.message}
              </button>
            </p>
          ))}
          {uncertain.map((call) => (
            <article key={call.id} className="space-y-2 border p-3">
              <p>
                {call.status === "unknown" ? "Outcome unknown" : "Call failed"}
                {call.effect ? ` · ${call.effect}` : ""}
              </p>
              <button
                className="inspection-link text-left"
                onClick={() =>
                  onInspect({
                    kind: "record",
                    id: call.id,
                    title: call.purpose,
                    value: call,
                  })
                }
              >
                {call.purpose}
              </button>
            </article>
          ))}
          {!issues.length && !uncertain.length && (
            <p className="text-muted-foreground">
              No broken references or unsuccessful tool calls in these saved
              records. The ontology remains a proposal.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}

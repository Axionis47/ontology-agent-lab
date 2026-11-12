import type { DiscoveryDetail, EvidenceRef } from "@/lib/api";
import type { Selection } from "./schema-adapter";

type Choice = {
  target: { kind: string; id: string; property: string | null };
  purpose: string;
  reason: string;
  evidence: EvidenceRef[];
  unresolved: string[];
  identity_scope: string | null;
  connection_rule: string | null;
};
type Draft = {
  revision: number;
  proposal: {
    summary: string;
    choices: Choice[];
    function_needs: {
      id: string;
      output_kind: string;
      missing_evidence: string;
    }[];
    probe_question: { question: string; expected_information: string } | null;
    tool_access?: {
      tool_id: string;
      capabilities: {
        capability: string;
        status: string;
        description: string;
        evidence: EvidenceRef[];
      }[];
    }[];
  };
  findings: { errors: string[]; gaps: { message: string }[] };
};

export function currentDraft(detail: DiscoveryDetail): Draft | null {
  const payload = detail.artifacts
    .filter((a) => a.kind === "draft")
    .at(-1)?.payload;
  if (!payload || typeof payload.revision !== "number") return null;
  const proposal = payload.proposal;
  if (
    !proposal ||
    typeof proposal !== "object" ||
    !("choices" in proposal) ||
    !Array.isArray(proposal.choices)
  )
    return null;
  return payload as unknown as Draft;
}

export function modelingChoices(
  detail: DiscoveryDetail,
  selection: Selection | null,
) {
  if (!selection || !("id" in selection)) return [];
  return (currentDraft(detail)?.proposal.choices ?? []).filter(({ target }) =>
    selection.kind === "record"
      ? target.kind === "function" && selection.id === `function:${target.id}`
      : target.kind === selection.kind &&
        target.id === selection.id &&
        (selection.kind !== "property" ||
          target.property === selection.property),
  );
}

export function ModelingReasons({
  choices,
  onInspect,
}: {
  choices: Choice[];
  onInspect: (selection: Selection) => void;
}) {
  if (!choices.length) return null;
  return (
    <section aria-label="Modeling reasons" className="space-y-3 text-xs">
      <h3 className="font-semibold">Modeling reasons</h3>
      {choices.map((choice) => (
        <div key={JSON.stringify(choice.target)} className="space-y-2">
          <p>
            <span className="font-medium">Task purpose: </span>
            {choice.purpose}
          </p>
          <p>
            <span className="font-medium">Representation: </span>
            {choice.reason}
          </p>
          {choice.identity_scope && (
            <p>Identity scope: {choice.identity_scope}</p>
          )}
          {choice.connection_rule && (
            <p>Connection rule: {choice.connection_rule}</p>
          )}
          {choice.unresolved.map((question) => (
            <p key={question}>Unresolved: {question}</p>
          ))}
          <div className="flex flex-wrap gap-2">
            {choice.evidence.map((ref, index) => (
              <button
                key={index}
                className="inspection-link break-all"
                onClick={() => onInspect({ kind: "evidence", ref })}
              >
                {ref.source}: {ref.path || ref.id}
              </button>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}

export function DiscoveryModeling({
  detail,
  onInspect,
  showChoices = false,
}: {
  detail: DiscoveryDetail;
  onInspect: (selection: Selection) => void;
  showChoices?: boolean;
}) {
  const draft = currentDraft(detail);
  if (!draft) return null;
  return (
    <section
      aria-label="Discovery modeling"
      className="space-y-4 border-t pt-4 text-xs"
    >
      <div>
        <h3 className="font-medium">Discovery revision {draft.revision}</h3>
        <p className="mt-1 text-muted-foreground">{draft.proposal.summary}</p>
      </div>
      {!!draft.proposal.tool_access?.length && (
        <details className="border p-3">
          <summary className="cursor-pointer">
            Source access capabilities
          </summary>
          {draft.proposal.tool_access.map((tool) => (
            <div key={tool.tool_id} className="mt-3 space-y-2">
              <button
                className="inspection-link break-all"
                onClick={() => onInspect({ kind: "tool", id: tool.tool_id })}
              >
                {tool.tool_id}
              </button>
              {tool.capabilities.map((capability) => (
                <p key={capability.capability}>
                  {capability.capability}: {capability.status}.{" "}
                  {capability.description}{" "}
                  {capability.evidence.map((ref, index) => (
                    <button
                      key={index}
                      className="inspection-link"
                      onClick={() => onInspect({ kind: "evidence", ref })}
                    >
                      Source contract
                    </button>
                  ))}
                </p>
              ))}
            </div>
          ))}
        </details>
      )}
      {draft.proposal.probe_question && (
        <div>
          <p className="font-medium">Current exploration question</p>
          <p>{draft.proposal.probe_question.question}</p>
          <p className="text-muted-foreground">
            Expected information:{" "}
            {draft.proposal.probe_question.expected_information}
          </p>
        </div>
      )}
      {showChoices && (
        <div
          className="max-h-80 space-y-2 overflow-auto"
          aria-label="Modeling decisions"
          tabIndex={0}
        >
          {draft.proposal.choices.map((choice) => (
            <details key={JSON.stringify(choice.target)} className="border p-3">
              <summary className="cursor-pointer break-words font-medium">
                {choice.target.kind}: {choice.target.id}
                {choice.target.property ? `.${choice.target.property}` : ""}
              </summary>
              <div className="mt-3">
                <ModelingReasons choices={[choice]} onInspect={onInspect} />
              </div>
            </details>
          ))}
        </div>
      )}
      <section aria-label="Proposed functions" className="space-y-2">
        <h3 className="font-medium">Proposed functions</h3>
        <p className="text-muted-foreground">
          These computations guide exploration. Training constructs executable
          functions after the baseline runs.
        </p>
        {draft.proposal.function_needs.map((need) => (
          <div key={need.id}>
            <button
              className="inspection-link break-words"
              onClick={() =>
                onInspect({
                  kind: "record",
                  id: `function:${need.id}`,
                  title: need.id,
                  value: need,
                })
              }
            >
              {need.id} · {need.output_kind}
            </button>
            <p className="mt-1 text-muted-foreground">
              Missing evidence: {need.missing_evidence}
            </p>
          </div>
        ))}
        {!draft.proposal.function_needs.length && (
          <p>No computations proposed.</p>
        )}
      </section>
      {showChoices && (
        <div
          className="max-h-60 space-y-2 overflow-auto"
          aria-label="Draft findings"
          tabIndex={0}
        >
          {draft.findings.errors.map((error, index) => (
            <p key={`error-${index}`}>{error}</p>
          ))}
          {draft.findings.gaps.map((gap, index) => (
            <p key={`gap-${index}`}>{gap.message}</p>
          ))}
          {!draft.findings.errors.length && !draft.findings.gaps.length && (
            <p>No draft findings remain. The proposal is untrained.</p>
          )}
        </div>
      )}
    </section>
  );
}

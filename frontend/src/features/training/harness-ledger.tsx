import type { TrainingDetail } from "@/lib/api";
import { SavedData, object, text } from "./saved-data";

type Candidate = TrainingDetail["candidates"][number];

const labels: Record<string, string> = {
  repair_review: "Repair review",
  graph_route: "Graph route",
  harness_unchanged: "Unchanged",
  proposal_rejected: "Rejected proposal",
  repair_applied: "Applied change",
  definition_sources: "Constant sources",
  kernel_validation: "Validation result",
  harness_base: "Reused candidate",
};

function definitions(candidate: Candidate) {
  return [object(candidate.payload.schema), candidate.payload].flatMap(
    (owner) =>
      Object.entries(owner).flatMap(([collection, items]) =>
        Array.isArray(items)
          ? items
              .filter((item) => typeof object(item).id === "string")
              .map((item) => ({
                collection,
                id: text(object(item).id),
                value: object(item),
              }))
          : [],
      ),
  );
}

function references(value: unknown, keyPattern: RegExp): unknown[] {
  if (Array.isArray(value))
    return value.flatMap((item) => references(item, keyPattern));
  return Object.entries(object(value)).flatMap(([key, child]) =>
    keyPattern.test(key) ? [{ [key]: child }] : references(child, keyPattern),
  );
}

export function HarnessLedger({
  detail,
  candidate,
  onInspectEvidence,
}: {
  detail: TrainingDetail;
  candidate?: Candidate;
  onInspectEvidence: () => void;
}) {
  const selected = candidate ?? detail.candidates.at(-1);
  const history = detail.events.filter((event) => event.kind in labels);
  const reviewed = history.some((event) => event.kind === "repair_review");
  return (
    <div className="min-w-0 space-y-5">
      <section aria-label="Definition catalog" className="space-y-3">
        <h4 className="text-sm font-medium">Definition catalog</h4>
        {selected ? (
          <>
            <p className="break-all text-xs text-muted-foreground">
              Candidate {selected.id} · Version {selected.digest}
            </p>
            <div className="max-h-[32rem] space-y-2 overflow-auto">
              {definitions(selected).map((definition) => {
                const uses = detail.events.filter((event) => {
                  const data = object(event.data);
                  const episode = detail.episodes.find(
                    (item) => item.id === event.episode_id,
                  );
                  if (
                    episode?.candidate_id !== selected.id &&
                    data.candidate_digest !== selected.digest
                  )
                    return false;
                  if (event.kind === "function_result")
                    return (
                      definition.collection === "functions" &&
                      data.function_id === definition.id
                    );
                  return (
                    [
                      "graph_route",
                      "graph_updated",
                      "dispatch_decision",
                    ].includes(event.kind) &&
                    references(
                      data,
                      /^(function_id|entity_id|entity_types|relation_id|relation_ids|mapping_id|binding_id|constraint_ids)$/,
                    ).some((ref) =>
                      Object.values(object(ref)).some(
                        (value) =>
                          value === definition.id ||
                          (Array.isArray(value) &&
                            value.includes(definition.id)),
                      ),
                    )
                  );
                });
                return (
                  <details
                    key={`${definition.collection}/${definition.id}`}
                    className="border p-3 text-xs"
                  >
                    <summary className="cursor-pointer break-words">
                      {definition.collection.replaceAll("_", " ")} /{" "}
                      {definition.id}
                    </summary>
                    <div className="mt-3 space-y-2">
                      <p>Recorded use: {uses.length}</p>
                      <div className="flex flex-wrap gap-3">
                        {uses.map((event) => (
                          <a
                            key={event.id}
                            className="underline"
                            href={`#record-${event.id}`}
                            onClick={onInspectEvidence}
                          >
                            Evidence {event.sequence}
                          </a>
                        ))}
                      </div>
                      <SavedData
                        title="Dependencies"
                        value={references(
                          definition.value,
                          /(_id|_ids|entity_types)$/,
                        )}
                      />
                      <SavedData
                        title="Supporting evidence"
                        value={references(
                          definition.value,
                          /^(support|evidence_refs|requirement_ids)$/,
                        )}
                      />
                      <SavedData
                        title="Complete definition"
                        value={definition.value}
                      />
                    </div>
                  </details>
                );
              })}
            </div>
          </>
        ) : (
          <p className="text-xs text-muted-foreground">
            No candidate is saved.
          </p>
        )}
      </section>
      <section aria-label="Change history" className="space-y-3">
        <h4 className="text-sm font-medium">Change history</h4>
        {!reviewed && (
          <p className="text-xs text-muted-foreground">
            No repair review is recorded for this run. Earlier records can lack
            a review.
          </p>
        )}
        <ol className="max-h-[32rem] space-y-2 overflow-auto">
          {history.map((event) => {
            const data = object(event.data);
            return (
              <li key={event.id} className="border p-3 text-xs">
                <a
                  className="underline"
                  href={`#record-${event.id}`}
                  onClick={onInspectEvidence}
                >
                  {labels[event.kind]} · Evidence {event.sequence}
                </a>
                {event.kind === "repair_review" ? (
                  <>
                    <p className="mt-2">
                      Decision: {text(data.decision).replaceAll("_", " ")}
                    </p>
                    <p>Proposed cause: {text(data.reason)}</p>
                    <p>
                      Verification:{" "}
                      {text(data.verification).replaceAll("_", " ")}
                    </p>
                  </>
                ) : (
                  <p className="mt-2 break-words">
                    {text(data.reason, event.message)}
                  </p>
                )}
                <SavedData title="Saved record" value={data} />
              </li>
            );
          })}
        </ol>
      </section>
    </div>
  );
}

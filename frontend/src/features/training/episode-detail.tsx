import { Button } from "@/components/ui/button";
import type { TrainingEpisode, TrainingEvent } from "@/lib/api";
import { SavedData, object, text } from "./saved-data";

function records(value: unknown) {
  return Array.isArray(value) ? value.map(object) : [];
}

export function EpisodeDetail({
  episode,
  events,
  onClose,
}: {
  episode: TrainingEpisode;
  events: TrainingEvent[];
  onClose: () => void;
}) {
  const result = episode.result;
  const graph = object(result.graph);
  const entities = Object.entries(object(graph.entities));
  const observations = records(result.observations);
  const calls = records(result.function_calls);
  const decisions = records(result.dispatch_decisions);
  const trace = records(result.trace);
  return (
    <section
      aria-label="Episode inspection"
      className="min-w-0 space-y-4 border border-primary/50 p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-medium">
          {episode.stage} · round {episode.round_index} ·{" "}
          {text(result.status, episode.status)}
        </h4>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Close trace
        </Button>
      </div>
      <p className="break-all text-[11px] text-muted-foreground">
        Run {episode.run_id} · Episode {episode.id}
        {episode.candidate_id && <> · Candidate {episode.candidate_id}</>}
      </p>
      <SavedData
        title="Saved case and environment"
        value={{
          case: episode.case_snapshot,
          environment_ref: episode.environment_ref,
        }}
      />
      {episode.evaluation && (
        <SavedData
          title="Task outcome and evaluator evidence"
          value={episode.evaluation}
          open
        />
      )}
      <SavedData title="Final task output" value={result.final_output} open />
      <section aria-label="Evidence access and context" className="space-y-3">
        <h5 className="text-xs font-medium">Evidence access and context</h5>
        <SavedData
          title="Acquisition needs and checks"
          value={decisions.map((decision) => ({
            tool_id: decision.tool_id,
            status: decision.status,
            acquisition: decision.acquisition,
            message: decision.message,
          }))}
        />
        <SavedData
          title="Evidence reads and context budgets"
          value={events.filter((event) =>
            ["evidence_read", "context_usage", "context_capacity"].includes(
              event.kind,
            ),
          )}
        />
      </section>
      {result.request_snapshot !== undefined && (
        <SavedData
          title="Fixed request and unresolved fields"
          value={result.request_snapshot}
        />
      )}
      {result.dispatch_decisions !== undefined && (
        <section aria-label="Dispatch decisions" className="space-y-3">
          <h5 className="text-xs font-medium">
            Dispatch decisions ({decisions.length})
          </h5>
          {decisions.map((decision, index) => (
            <SavedData
              key={text(decision.invocation_id, String(index))}
              title={`${text(decision.tool_id, "Operation")} · ${text(decision.status, "unknown")}`}
              value={decision}
            />
          ))}
          {!decisions.length && (
            <p className="text-xs text-muted-foreground">
              No dispatch decision has been recorded.
            </p>
          )}
        </section>
      )}
      {result.graph_processing !== undefined && (
        <SavedData
          title="Graph processing results"
          value={result.graph_processing}
        />
      )}
      <section aria-label="Tool observations" className="space-y-3">
        <h5 className="text-xs font-medium">
          Tool observations ({observations.length})
        </h5>
        {!observations.length && (
          <p className="text-xs text-muted-foreground">
            No tool result has been recorded.
          </p>
        )}
        {observations.map((item, index) => (
          <article
            key={text(item.id, String(index))}
            className="space-y-2 border p-3 text-xs"
          >
            <p className="break-all font-medium">
              {text(item.tool_id)} · {text(item.status, "unknown")} · coverage{" "}
              {text(item.coverage, "unknown")}
            </p>
            <p className="break-all text-muted-foreground">
              Evidence {text(item.id)} · Invocation {text(item.invocation_id)}
            </p>
            <SavedData title="Call arguments" value={item.arguments} />
            <SavedData
              title="Observed result"
              value={{ data: item.data, raw: item.raw, error: item.error }}
            />
          </article>
        ))}
      </section>
      <section aria-label="Function executions" className="space-y-3">
        <h5 className="text-xs font-medium">
          Function executions ({calls.length})
        </h5>
        {calls.map((call, index) => (
          <article
            key={text(call.invocation_id, String(index))}
            className="space-y-2 border p-3 text-xs"
          >
            <p className="break-all font-medium">
              {text(call.function_id)} ·{" "}
              {text(object(call.result).status, "unknown")}
              {object(call.result).truncated === true
                ? " · Limited result"
                : ""}
            </p>
            <SavedData
              title="Typed result and source records"
              value={{
                type: object(call.result).output_type,
                value: object(call.result).value,
                coverage: object(call.result).coverage,
                records: object(call.result).row_metadata,
                relations: object(call.result).relations,
                evidence: object(call.result).evidence_refs,
                missing: object(call.result).missing_dependencies,
              }}
            />
            <SavedData
              title="Function arguments and operator trace"
              value={call}
            />
          </article>
        ))}
      </section>
      <section aria-label="Observed graph" className="space-y-3">
        <h5 className="text-xs font-medium">
          Observed graph · revision {text(graph.revision, "unavailable")}
        </h5>
        <p className="text-xs text-muted-foreground">
          Facts below come from recorded tool results. Coverage and evidence
          stay attached to each observation.
        </p>
        {entities.map(([id, rows]) => (
          <div key={id} className="space-y-2 border p-3 text-xs">
            <strong>{id}</strong>
            {records(rows).map((row, index) => (
              <SavedData
                key={index}
                title={`Record ${Array.isArray(row.identity) ? row.identity.map((value) => text(value)).join(", ") : text(row.identity, String(index + 1))}`}
                value={{
                  values: row.values,
                  context: row.context,
                  evidence: row.evidence,
                }}
              />
            ))}
          </div>
        ))}
        {!entities.length && (
          <p className="text-xs text-muted-foreground">
            No entity records were materialized.
          </p>
        )}
        <SavedData
          title="Graph coverage and update history"
          value={{
            coverage: graph.coverage ?? graph.complete,
            history: graph.history,
          }}
        />
      </section>
      <details className="border p-3 text-xs">
        <summary className="cursor-pointer">
          Execution trace ({trace.length})
        </summary>
        <ol className="mt-3 max-h-[32rem] space-y-2 overflow-y-auto">
          {trace.map((item, index) => (
            <li key={text(item.id, String(index))}>
              <SavedData
                title={`${text(item.sequence, String(index + 1))} · ${text(item.kind, "event")}`}
                value={item}
              />
            </li>
          ))}
        </ol>
      </details>
      {!!events.length && (
        <SavedData title="Saved episode activity" value={events} />
      )}
      <SavedData title="Complete episode result" value={result} />
    </section>
  );
}

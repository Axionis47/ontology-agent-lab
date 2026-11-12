"use client";

import dynamic from "next/dynamic";
import { useCallback, useMemo, useState } from "react";
import type { Tool, TrainingDetail } from "@/lib/api";
import {
  adaptSchema,
  propertyType,
  type Schema,
  type Selection,
} from "@/features/discovery/schema-adapter";
import { SavedData, object, text } from "@/features/training/saved-data";
import {
  activityLabels,
  displayValue,
  inferenceState,
  relatedEntities,
} from "./inference-state";

const SchemaDiagram = dynamic(
  () => import("@/features/discovery/schema-diagram"),
  {
    ssr: false,
    loading: () => <p role="status">Loading graph...</p>,
  },
);

function Fields({ value }: { value: unknown }) {
  const fields = Object.entries(object(value));
  return fields.length ? (
    <dl className="grid min-w-0 gap-2 text-xs">
      {fields.map(([key, item]) => (
        <div key={key} className="min-w-0">
          <dt className="text-muted-foreground">{key}</dt>
          <dd className="whitespace-pre-wrap break-words">
            {displayValue(item)}
          </dd>
        </div>
      ))}
    </dl>
  ) : (
    <p className="break-words text-xs">{displayValue(value)}</p>
  );
}

export function InferenceRun({
  detail,
  candidate,
  tools,
}: {
  detail: TrainingDetail | null;
  candidate: TrainingDetail["candidates"][number];
  tools: Tool[];
}) {
  const [selection, setSelection] = useState<Selection | null>(null);
  const [activityId, setActivityId] = useState<string | null>(null);
  const [observationId, setObservationId] = useState<string | null>(null);
  const schemaKey = JSON.stringify(candidate.payload.schema ?? {});
  const model = useMemo(() => {
    const schema = JSON.parse(schemaKey) as Schema;
    return adaptSchema({
      ...schema,
      relations: (schema.relations ?? []).map((r) => ({
        ...r,
        name: `Declared: ${r.name}`,
      })),
    });
  }, [schemaKey]);
  const state = useMemo(() => inferenceState(detail), [detail]);
  const activity = state.activity.find((event) => event.id === activityId);
  const highlighted = relatedEntities(
    activity,
    state.activity,
    candidate.payload,
  );
  const selectedEntity =
    selection?.kind === "entity" || selection?.kind === "property"
      ? model.entities.find((entity) => entity.id === selection.id)
      : undefined;
  const relation =
    selection?.kind === "relation"
      ? model.relations.find((r) => r.id === selection.id)
      : undefined;
  const observation = observationId
    ? state.observations.get(observationId)
    : undefined;
  const onSelect = useCallback((item: Selection) => {
    setSelection(item);
    setActivityId(null);
    setObservationId(null);
  }, []);
  const name = (id: unknown) =>
    tools.find((tool) => tool.id === id)?.name ?? text(id);
  return (
    <div className="min-w-0 space-y-4">
      {state.finalOutput && (
        <section
          aria-label="Final answer"
          className="space-y-2 border border-primary/50 bg-primary/5 p-4"
        >
          <h3 className="text-sm font-medium">Final answer</h3>
          <p className="whitespace-pre-wrap break-words text-sm">
            {state.finalOutput}
          </p>
        </section>
      )}
      <p className="break-all text-xs text-muted-foreground">
        Displayed kernel: {candidate.id} · {candidate.digest}
      </p>
      {detail && (
        <p className="whitespace-pre-wrap break-words text-sm">
          {text(
            state.episode?.case_snapshot.query,
            text(object(detail.run.cases[0]).query),
          )}
        </p>
      )}
      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(16rem,1fr)]">
        <section aria-label="Inference graph" className="min-w-0 space-y-3">
          <h3 className="text-sm font-medium">
            Observed graph · revision {state.revision}
          </h3>
          <p className="text-xs text-muted-foreground">
            Cards show accepted entity types and observed-record counts. Edges
            show declared relations.
          </p>
          <SchemaDiagram
            model={model}
            schemaKey={`inference:${candidate.digest}:${schemaKey}`}
            selection={selection}
            onSelect={onSelect}
            query=""
            inference={{
              counts: Object.fromEntries(
                model.entities.map((entity) => [
                  entity.id,
                  state.entities[entity.id]?.length ?? 0,
                ]),
              ),
              highlighted,
            }}
          />
          <div aria-label="Entity records" className="flex flex-wrap gap-2">
            {model.entities.map((entity) => (
              <button
                key={entity.id}
                type="button"
                className="border px-3 py-2 text-xs focus-visible:outline-2 focus-visible:outline-primary"
                aria-pressed={selectedEntity?.id === entity.id}
                onClick={() => onSelect({ kind: "entity", id: entity.id })}
              >
                {entity.name}: {state.entities[entity.id]?.length ?? 0} observed
                records
              </button>
            ))}
          </div>
        </section>
        <section aria-label="Inference activity" className="min-w-0 space-y-3">
          <h3 className="text-sm font-medium">Activity</h3>
          {!state.activity.length && (
            <p className="text-xs text-muted-foreground">
              Activity appears when the task starts.
            </p>
          )}
          <ol className="max-h-[38rem] space-y-2 overflow-y-auto">
            {state.activity.map((event) => {
              const data = event.data;
              const observed = object(data.observation);
              const status = text(
                data.status,
                text(observed.status, text(object(data.result).status)),
              );
              return (
                <li key={event.id}>
                  <button
                    type="button"
                    aria-pressed={event.id === activityId}
                    onClick={() => {
                      setActivityId(event.id);
                      setSelection(null);
                      setObservationId(null);
                    }}
                    className={`w-full min-w-0 space-y-1 border p-3 text-left text-xs focus-visible:outline-2 focus-visible:outline-primary ${event.id === activityId ? "border-primary bg-primary/5" : ""}`}
                  >
                    <span className="block">
                      {event.sequence} · {activityLabels[event.kind]}
                    </span>
                    <span className="block break-words text-muted-foreground">
                      {name(data.tool_id ?? observed.tool_id) ||
                        text(data.function_id, text(data.name))}
                    </span>
                    {status && (
                      <span className="block">
                        {status.replaceAll("_", " ")}
                      </span>
                    )}
                    {Boolean(data.error || data.message) && (
                      <span className="block break-words">
                        {text(data.error, text(data.message))}
                      </span>
                    )}
                  </button>
                </li>
              );
            })}
          </ol>
        </section>
      </div>
      <section
        aria-label="Evidence inspector"
        className="min-w-0 space-y-3 border p-4"
      >
        <h3 className="text-sm font-medium">Evidence inspector</h3>
        {!selection && !activity && (
          <p className="text-xs text-muted-foreground">
            Select an entity or activity to inspect its saved evidence.
          </p>
        )}
        {selectedEntity && (
          <>
            <h4 className="text-sm">{selectedEntity.name}</h4>
            <p className="text-xs text-muted-foreground">
              Identity:{" "}
              {selectedEntity.identity_keys?.join(", ") || "Unspecified"}
            </p>
            {!state.entities[selectedEntity.id]?.length && (
              <p className="text-xs">No records observed yet.</p>
            )}
            <div className="max-h-[36rem] space-y-3 overflow-y-auto">
              {(state.entities[selectedEntity.id] ?? []).map((row, index) => (
                <article
                  key={index}
                  aria-label={`Observed record ${index + 1}`}
                  className="space-y-3 border p-3"
                >
                  <p className="break-words text-xs font-medium">
                    Identity: {displayValue(row.identity)}
                  </p>
                  <div>
                    <p className="mb-1 text-xs font-medium">Evidence context</p>
                    <Fields value={row.context} />
                  </div>
                  <dl className="grid gap-3 sm:grid-cols-2">
                    {selectedEntity.properties.map((property) => {
                      const evidence = object(row.evidence[property.name]);
                      return (
                        <div key={property.name} className="min-w-0 text-xs">
                          <dt className="text-muted-foreground">
                            {property.name} · {propertyType(property)}
                            {property.unit ? ` (${property.unit})` : ""}
                          </dt>
                          <dd className="break-words">
                            {Object.hasOwn(row.values, property.name)
                              ? displayValue(row.values[property.name])
                              : "Missing evidence"}
                          </dd>
                          {Boolean(evidence.observation_id) && (
                            <dd>
                              <button
                                type="button"
                                className="inspection-link break-all text-left"
                                onClick={() =>
                                  setObservationId(
                                    text(evidence.observation_id),
                                  )
                                }
                              >
                                Source {text(evidence.observation_id)}
                                {text(evidence.path)}
                              </button>
                            </dd>
                          )}
                        </div>
                      );
                    })}
                  </dl>
                  <SavedData title="Raw record and evidence" value={row} />
                </article>
              ))}
            </div>
          </>
        )}
        {relation && (
          <div className="space-y-2 text-xs">
            <h4>{relation.name}</h4>
            <p>
              {relation.from_entity}.{relation.from_property} →{" "}
              {relation.to_entity}.{relation.to_property}
            </p>
            <p className="text-muted-foreground">
              This is a schema declaration. It does not establish a connection
              between observed records.
            </p>
          </div>
        )}
        {activity && (
          <div className="space-y-3">
            <h4 className="text-sm">{activityLabels[activity.kind]}</h4>
            <Fields
              value={Object.fromEntries(
                Object.entries(activity.data).filter(([key]) =>
                  [
                    "status",
                    "error",
                    "message",
                    "revision",
                    "final_output",
                  ].includes(key),
                ),
              )}
            />
            {activity.data.arguments !== undefined && (
              <div>
                <h5 className="mb-2 text-xs font-medium">Arguments</h5>
                <Fields value={activity.data.arguments} />
              </div>
            )}
            {activity.data.result !== undefined && (
              <div>
                <h5 className="mb-2 text-xs font-medium">Function result</h5>
                <Fields
                  value={
                    object(activity.data.result).value ?? activity.data.result
                  }
                />
              </div>
            )}
            {activity.data.missing_dependencies !== undefined && (
              <div>
                <h5 className="mb-2 text-xs font-medium">Missing evidence</h5>
                <Fields value={activity.data.missing_dependencies} />
              </div>
            )}
            {activity.kind === "request_prepared" && (
              <Fields value={activity.data.values ?? activity.data} />
            )}
            {Boolean(
              activity.data.observation_id ||
              object(activity.data.observation).id,
            ) && (
              <button
                type="button"
                className="inspection-link text-xs"
                onClick={() =>
                  setObservationId(
                    text(
                      activity.data.observation_id ??
                        object(activity.data.observation).id,
                    ),
                  )
                }
              >
                Inspect source observation
              </button>
            )}
            <SavedData title="Raw activity record" value={activity.data} />
          </div>
        )}
        {observationId && (
          <section
            aria-label="Source observation"
            className="space-y-3 border-t pt-3"
          >
            <h4 className="break-all text-sm">
              Source observation {observationId}
            </h4>
            {observation ? (
              <>
                <p className="text-xs">
                  {name(observation.tool_id)} · {text(observation.status)} ·
                  coverage {text(observation.coverage, "unknown")}
                </p>
                <h5 className="text-xs font-medium">Call arguments</h5>
                <Fields value={observation.arguments} />
                <h5 className="text-xs font-medium">Observed response</h5>
                <Fields value={observation.data} />
                <SavedData title="Raw observation" value={observation} />
              </>
            ) : (
              <p className="text-xs">
                This observation is unavailable in the saved run.
              </p>
            )}
          </section>
        )}
      </section>
    </div>
  );
}

import type { TrainingDetail, TrainingEvent } from "@/lib/api";
import { object, text } from "@/features/training/saved-data";

export const records = (value: unknown): Record<string, unknown>[] =>
  Array.isArray(value) ? value.map(object) : [];

export type ObservedRecord = {
  identity: unknown;
  context: Record<string, unknown>;
  values: Record<string, unknown>;
  evidence: Record<string, unknown>;
};

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value !== null && typeof value === "object")
    return `{${Object.entries(value)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => `${JSON.stringify(k)}:${canonical(v)}`)
      .join(",")}}`;
  return JSON.stringify(value) ?? "null";
}

export const activityLabels: Record<string, string> = {
  request_prepared: "Request prepared",
  tool_proposed: "Tool selected",
  tool_dispatched: "Tool invoked",
  tool_result: "Tool response",
  graph_updated: "Graph updated",
  function_result: "Function result",
  dispatch_decision: "Action decision",
  evidence_read: "Saved evidence inspected",
  context_usage: "Context budget",
  context_capacity: "Context capacity reached",
  tool_rejected: "Tool rejected",
  graph_processing_failed: "Graph update failed",
  model_error: "Model error",
  episode_interrupted: "Execution interrupted",
  episode_finished: "Execution finished",
  run_stopped: "Run stopped",
  run_failed: "Run failed",
};

export function inferenceState(detail: TrainingDetail | null) {
  const episode = detail?.episodes.find((e) => e.stage === "inference");
  const result = episode?.result ?? {};
  const events = [
    ...new Map(
      (detail?.events ?? [])
        .filter(
          (event) =>
            !episode || !event.episode_id || event.episode_id === episode.id,
        )
        .map((event) => [event.id, event]),
    ).values(),
  ].sort((a, b) => a.sequence - b.sequence);
  const entities: Record<string, ObservedRecord[]> = Object.create(null);
  const rows = new Map<string, ObservedRecord>();
  const observations = new Map<string, Record<string, unknown>>();
  let revision = 0;
  for (const event of events) {
    const data = event.data;
    if (event.kind === "tool_result") {
      const observation = object(data.observation);
      observations.set(text(observation.id), observation);
    }
    if (event.kind !== "graph_updated") continue;
    revision = Number(data.revision ?? revision);
    for (const change of records(data.changes)) {
      const entity = text(change.entity_id);
      const context = object(change.context);
      const key = canonical([entity, change.identity, context]);
      let row = rows.get(key);
      if (!row) {
        row = {
          identity: change.identity,
          context,
          values: Object.create(null),
          evidence: Object.create(null),
        };
        rows.set(key, row);
        (entities[entity] ??= []).push(row);
      }
      const property = text(change.property);
      if (change.valid === true) row.values[property] = change.value;
      else delete row.values[property];
      row.evidence[property] = change.evidence;
    }
  }
  for (const observation of records(result.observations))
    observations.set(text(observation.id), observation);
  const graph = object(result.graph);
  if (graph.entities !== undefined) {
    for (const key of Object.keys(entities)) delete entities[key];
    for (const [entity, values] of Object.entries(object(graph.entities)))
      entities[entity] = records(values).map((row) => ({
        identity: row.identity,
        context: object(row.context),
        values: object(row.values),
        evidence: object(row.evidence),
      }));
    revision = Number(graph.revision ?? revision);
  }
  return {
    episode,
    result,
    entities,
    observations,
    revision,
    activity: events.filter((event) => activityLabels[event.kind]),
    finalOutput: text(
      result.final_output,
      text(
        events.findLast((e) => e.kind === "episode_finished")?.data
          .final_output,
      ),
    ),
  };
}

export function relatedEntities(
  event: TrainingEvent | undefined,
  activity: TrainingEvent[],
  candidate: Record<string, unknown>,
) {
  if (!event) return [];
  const entities = new Set<string>();
  const tools = new Set<string>();
  const functions = new Set<string>();
  const mappings = new Set<string>();
  const relations = new Set<string>();
  const observationIds = new Set<string>();
  function collect(value: unknown) {
    if (Array.isArray(value)) {
      value.forEach(collect);
      return;
    }
    const node = object(value);
    for (const [key, target] of [
      ["entity_id", entities],
      ["entity_types", entities],
      ["tool_id", tools],
      ["function_id", functions],
      ["mapping_id", mappings],
      ["relation_id", relations],
      ["relation_ids", relations],
      ["observation_id", observationIds],
    ] as const) {
      const values = Array.isArray(node[key]) ? node[key] : [node[key]];
      for (const item of values) if (typeof item === "string") target.add(item);
    }
    for (const [key, child] of Object.entries(node))
      if (
        ![
          "data",
          "raw",
          "arguments",
          "value",
          "values",
          "identity",
          "context",
        ].includes(key)
      )
        if (child && typeof child === "object") collect(child);
  }
  collect(event.data);
  const invocation =
    event.data.invocation_id ?? object(event.data.observation).invocation_id;
  const observation =
    event.data.observation_id ?? object(event.data.observation).id;
  for (const other of activity) {
    const data = other.data;
    if (
      (invocation &&
        invocation ===
          (data.invocation_id ?? object(data.observation).invocation_id)) ||
      (observation &&
        observation === (data.observation_id ?? object(data.observation).id))
    )
      collect(data);
  }
  for (const fn of records(candidate.functions))
    if (functions.has(text(fn.id))) collect(fn);
  for (const other of activity)
    if (
      other.kind === "graph_updated" &&
      observationIds.has(text(other.data.observation_id))
    )
      collect(other.data);
  for (const mapping of records(candidate.mappings))
    if (tools.has(text(mapping.tool_id)) || mappings.has(text(mapping.id)))
      entities.add(text(mapping.entity_id));
  for (const relation of records(object(candidate.schema).relations))
    if (relations.has(text(relation.id))) {
      entities.add(text(relation.from_entity));
      entities.add(text(relation.to_entity));
    }
  return [...entities];
}

export function displayValue(value: unknown): string {
  if (value === undefined) return "Unavailable";
  if (value === null) return "null";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

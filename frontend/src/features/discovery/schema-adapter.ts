import type { components } from "@/lib/api-types";
import type { DiscoveryDetail, EvidenceRef } from "@/lib/api";

export type Schema = components["schemas"]["SchemaProposal"];
export type Entity = components["schemas"]["EntityProposal"];
export type Relation = components["schemas"]["RelationProposal"];
export type Binding = components["schemas"]["SourceBinding"];
export function propertyType(property: Entity["properties"][number]) {
  return property.type === "array"
    ? `array<${property.item_type ?? "unspecified"}>`
    : property.type;
}
export type Selection =
  | {
      kind:
        | "entity"
        | "relation"
        | "binding"
        | "operation"
        | "requirement"
        | "tool";
      id: string;
    }
  | { kind: "gap"; id: string; scope: "schema" | "requirements" }
  | { kind: "property"; id: string; property: string }
  | { kind: "evidence"; ref: EvidenceRef }
  | { kind: "record"; id: string; title: string; value: unknown };
export type SchemaIssue = { message: string; item: Selection };
export const selectionKey = (item: Selection | null) =>
  item
    ? JSON.stringify(item.kind === "record" ? [item.kind, item.id] : item)
    : "";
export const entityNodeId = (id: string) => JSON.stringify(["entity", id]);
export const propertyHandle = (
  entityId: string,
  property: string,
  side: "in" | "out",
) => JSON.stringify(["property", entityId, property, side]);

export function adaptSchema(schema: Schema) {
  const entities = schema.entities ?? [];
  const relations = schema.relations ?? [];
  const bindings = schema.bindings ?? [];
  const operations = schema.operations ?? [];
  const gaps = schema.gaps ?? [];
  const issues: SchemaIssue[] = [];
  const entityById = new Map(entities.map((entity) => [entity.id, entity]));
  const bindingById = new Map(bindings.map((binding) => [binding.id, binding]));
  function endpoint(id: string, property: string, item: Selection) {
    const entity = entityById.get(id);
    if (!entity) {
      issues.push({ message: `Entity reference unavailable: ${id}.`, item });
      return false;
    }
    if (entity.properties.filter((p) => p.name === property).length !== 1) {
      issues.push({
        message: `Property reference unavailable or ambiguous: ${id}.${property}.`,
        item,
      });
      return false;
    }
    return true;
  }
  for (const entity of entities) {
    for (const property of entity.identity_keys ?? [])
      endpoint(entity.id, property, { kind: "entity", id: entity.id });
  }
  for (const binding of bindings)
    endpoint(binding.entity_id, binding.property, {
      kind: "binding",
      id: binding.id,
    });
  const connectedRelations = relations.filter((relation) => {
    const item: Selection = { kind: "relation", id: relation.id };
    const from = endpoint(relation.from_entity, relation.from_property, item);
    const to = endpoint(relation.to_entity, relation.to_property, item);
    for (const id of relation.binding_ids) {
      if (!bindingById.has(id))
        issues.push({
          message: `Source mapping reference unavailable: ${id}.`,
          item,
        });
    }
    return from && to;
  });
  return {
    entities,
    relations,
    bindings,
    operations,
    gaps,
    entityById,
    bindingById,
    connectedRelations,
    issues,
  };
}
export type SchemaView = ReturnType<typeof adaptSchema>;

export function resolveEvidence(detail: DiscoveryDetail, ref: EvidenceRef) {
  const artifact =
    ref.source === "artifact"
      ? detail.artifacts.find((a) => a.id === ref.id)
      : undefined;
  const record =
    ref.source === "input"
      ? ref.id === "surface"
        ? detail.inputs
        : undefined
      : ref.source === "artifact"
        ? artifact?.payload
        : detail.questions.find((q) => q.id === ref.id);
  let value: unknown = record;
  if (ref.path && !ref.path.startsWith("/")) value = undefined;
  else
    for (const part of ref.path.split("/").slice(1)) {
      const key = part.replaceAll("~1", "/").replaceAll("~0", "~");
      value =
        value !== null && typeof value === "object" && Object.hasOwn(value, key)
          ? (value as Record<string, unknown>)[key]
          : undefined;
    }
  return { value, record, artifact, found: value !== undefined };
}

export function evidenceIssues(detail: DiscoveryDetail): SchemaIssue[] {
  const issues: SchemaIssue[] = [];
  const requirements = new Set(
    detail.requirements?.requirements.map((r) => r.id),
  );
  const schema = detail.schema_proposal;
  for (const [kind, records] of [
    ["entity", schema?.entities],
    ["relation", schema?.relations],
    ["operation", schema?.operations],
  ] as const) {
    for (const record of records ?? [])
      for (const id of record.requirement_ids) {
        if (!requirements.has(id))
          issues.push({
            message: `Requirement reference unavailable: ${id}.`,
            item: { kind, id: record.id },
          });
      }
  }
  const catalog = detail.artifacts
    .filter((artifact) => artifact.kind === "catalog")
    .at(-1);
  const tools = new Set(
    Array.isArray(catalog?.payload.tools)
      ? catalog.payload.tools.flatMap((tool: unknown) =>
          tool && typeof tool === "object" && "id" in tool
            ? [String(tool.id)]
            : [],
        )
      : [],
  );
  const checkTool = (id: string, item: Selection) => {
    if (!tools.has(id))
      issues.push({ message: `Tool reference unavailable: ${id}.`, item });
  };
  for (const binding of schema?.bindings ?? [])
    checkTool(binding.tool_id, { kind: "binding", id: binding.id });
  for (const operation of schema?.operations ?? []) {
    checkTool(operation.tool_id, { kind: "operation", id: operation.id });
    if (operation.confirmation_tool_id)
      checkTool(operation.confirmation_tool_id, {
        kind: "operation",
        id: operation.id,
      });
  }
  for (const requirement of detail.requirements?.requirements ?? [])
    for (const id of requirement.tool_ids ?? [])
      checkTool(id, { kind: "requirement", id: requirement.id });
  const refs = [
    ...(detail.requirements?.requirements.flatMap((r) => r.evidence) ?? []),
    ...(schema?.bindings?.map((b) => b.source) ?? []),
    ...(schema?.gaps?.flatMap((g) => g.evidence ?? []) ?? []),
    ...(detail.requirements?.gaps?.flatMap((g) => g.evidence ?? []) ?? []),
  ];
  for (const ref of refs)
    if (!resolveEvidence(detail, ref).found)
      issues.push({
        message: `Evidence reference unavailable: ${ref.source}:${ref.id}${ref.path}.`,
        item: { kind: "evidence", ref },
      });
  return issues;
}

export function selectedRecord(detail: DiscoveryDetail, item: Selection) {
  const schema = detail.schema_proposal;
  switch (item.kind) {
    case "entity":
      return schema?.entities?.find((e) => e.id === item.id);
    case "property":
      return schema?.entities
        ?.find((e) => e.id === item.id)
        ?.properties.find((p) => p.name === item.property);
    case "relation":
      return schema?.relations?.find((r) => r.id === item.id);
    case "binding":
      return schema?.bindings?.find((b) => b.id === item.id);
    case "operation":
      return schema?.operations?.find((o) => o.id === item.id);
    case "requirement":
      return detail.requirements?.requirements.find((r) => r.id === item.id);
    case "gap":
      return (
        item.scope === "schema" ? schema?.gaps : detail.requirements?.gaps
      )?.find((gap) => gap.id === item.id);
    case "tool": {
      const tools = detail.artifacts
        .filter((artifact) => artifact.kind === "catalog")
        .at(-1)?.payload.tools;
      return Array.isArray(tools)
        ? tools.find(
            (tool) => tool && typeof tool === "object" && tool.id === item.id,
          )
        : undefined;
    }
    case "evidence":
      return resolveEvidence(detail, item.ref).value;
    case "record":
      return item.value;
  }
}

import type { DiscoveryDetail, EvidenceRef } from "@/lib/api";
import {
  adaptSchema,
  evidenceIssues,
  resolveEvidence,
  type Selection,
} from "./schema-adapter";

export const graphKinds = [
  "requirement",
  "tool",
  "observation",
  "entity",
  "operation",
  "question",
  "source",
  "gap",
] as const;
export type GraphKind = (typeof graphKinds)[number];
export const graphLabels: Record<GraphKind, string> = {
  requirement: "Requirements",
  tool: "Tools",
  observation: "Observations",
  entity: "Schema entities",
  operation: "Operations",
  question: "Clarifications",
  source: "Source records",
  gap: "Gaps and issues",
};
export type EvidenceNode = {
  id: string;
  kind: GraphKind;
  title: string;
  status: string;
  description: string;
  item: Selection;
  warning: boolean;
};
export type EvidenceEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
  detail: string;
  item: Selection;
};
export type EvidenceInput = Pick<
  DiscoveryDetail,
  | "requirements"
  | "schema_proposal"
  | "artifacts"
  | "questions"
  | "calls"
  | "inputs"
>;
const object = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" ? (value as Record<string, unknown>) : {};
const words = (value: string) =>
  value.replaceAll("__", " / ").replaceAll("_", " ");

export function buildEvidenceGraph(input: EvidenceInput) {
  const detail = input as DiscoveryDetail;
  const nodes = new Map<string, EvidenceNode>();
  const edges: EvidenceEdge[] = [];
  const schema = adaptSchema(input.schema_proposal ?? {});
  const catalog = input.artifacts.filter((a) => a.kind === "catalog").at(-1);
  const tools = (
    Array.isArray(catalog?.payload.tools) ? catalog.payload.tools : []
  ).map(object);
  const toolName = (id: string) =>
    words(String(tools.find((t) => t.id === id)?.name ?? id));
  const add = (node: EvidenceNode) => nodes.set(node.id, node);
  const edge = (
    source: string,
    target: string,
    label: string,
    item: Selection,
    text = label,
  ) => {
    if (nodes.has(source) && nodes.has(target))
      edges.push({
        id: `link:${edges.length}`,
        source,
        target,
        label,
        detail: text,
        item,
      });
  };
  const nodeForRef = (ref: EvidenceRef): string | null => {
    if (!resolveEvidence(detail, ref).found) return null;
    if (ref.source === "question") return `q:${ref.id}`;
    if (ref.source === "artifact" && nodes.has(`a:${ref.id}`))
      return `a:${ref.id}`;
    const id = JSON.stringify(["source", ref.source, ref.id]);
    if (!nodes.has(id)) {
      const artifact = input.artifacts.find((a) => a.id === ref.id);
      add({
        id,
        kind: "source",
        title:
          ref.source === "input"
            ? "Original task surface"
            : (artifact?.title ?? "Saved source"),
        status:
          ref.source === "input"
            ? "User intent"
            : `Saved ${artifact?.kind ?? "record"}`,
        description:
          "Source content. This does not establish an observed external fact.",
        item: { kind: "evidence", ref: { ...ref, path: "" } },
        warning: false,
      });
    }
    return id;
  };
  for (const r of input.requirements?.requirements ?? [])
    add({
      id: `r:${r.id}`,
      kind: "requirement",
      title: r.statement,
      status: r.ambiguity ? "Open ambiguity" : "Proposed requirement",
      description: r.ambiguity ?? r.id,
      warning: Boolean(r.ambiguity),
      item: { kind: "requirement", id: r.id },
    });
  for (const t of tools)
    add({
      id: `t:${t.id}`,
      kind: "tool",
      title: words(String(t.name ?? t.id)),
      status: "Declared contract",
      description: String(t.description ?? "No description supplied."),
      warning: false,
      item: { kind: "tool", id: String(t.id) },
    });
  for (const a of input.artifacts.filter((a) => a.kind === "observation")) {
    const call = input.calls.find(
      (c) => c.response_artifact_id === a.id || c.id === a.payload.call_id,
    );
    const failed =
      Boolean(a.payload.error) ||
      a.payload.validation === "invalid" ||
      call?.status === "failed" ||
      call?.status === "unknown";
    const status =
      call?.status === "unknown"
        ? "Outcome unknown"
        : failed
          ? "Failed or invalid"
          : a.payload.validation === "valid"
            ? "Observed sample"
            : "Validation unknown";
    add({
      id: `a:${a.id}`,
      kind: "observation",
      title: call?.purpose ?? words(a.title),
      status,
      description: `${a.payload.tool_id ? toolName(String(a.payload.tool_id)) : "Tool unavailable"} · ${a.created_at}`,
      warning: failed || a.payload.validation !== "valid",
      item: {
        kind: "evidence",
        ref: { source: "artifact", id: a.id, path: "" },
      },
    });
  }
  for (const e of schema.entities) {
    const mappings = schema.bindings.filter((b) => b.entity_id === e.id);
    const observed = mappings.filter((b) => b.support === "observed").length;
    add({
      id: `e:${e.id}`,
      kind: "entity",
      title: e.name,
      status: "Proposed entity",
      description: `${e.properties.length} properties · ${observed} observed / ${mappings.length - observed} declared mappings`,
      warning: !mappings.length,
      item: { kind: "entity", id: e.id },
    });
  }
  for (const o of schema.operations)
    add({
      id: `o:${o.id}`,
      kind: "operation",
      title: toolName(o.tool_id),
      status: `Proposed ${o.effect}`,
      description: o.outputs,
      warning: o.effect === "unknown",
      item: { kind: "operation", id: o.id },
    });
  for (const q of input.questions)
    add({
      id: `q:${q.id}`,
      kind: "question",
      title: q.question.text,
      status: q.answer == null ? "Needs an answer" : "Answered intent",
      description: q.question.why_needed,
      warning: q.answer == null,
      item: {
        kind: "evidence",
        ref: { source: "question", id: q.id, path: "" },
      },
    });
  for (const [scope, gaps] of [
    ["schema", schema.gaps],
    ["requirements", input.requirements?.gaps ?? []],
  ] as const)
    for (const g of gaps)
      add({
        id: `g:${scope}:${g.id}`,
        kind: "gap",
        title: g.message,
        status: g.blocking ? "Blocking gap" : "Reported limitation",
        description: g.id,
        warning: true,
        item: { kind: "gap", id: g.id, scope },
      });
  for (const r of input.requirements?.requirements ?? []) {
    for (const id of r.tool_ids ?? [])
      edge(`r:${r.id}`, `t:${id}`, "Uses", { kind: "requirement", id: r.id });
    for (const ref of r.evidence) {
      const source = nodeForRef(ref);
      if (source)
        edge(
          source,
          `r:${r.id}`,
          ref.source === "question" ? "Clarifies intent" : "Supports",
          { kind: "evidence", ref },
        );
    }
  }
  for (const a of input.artifacts.filter((a) => a.kind === "observation"))
    edge(`t:${a.payload.tool_id}`, `a:${a.id}`, "Returned", {
      kind: "evidence",
      ref: { source: "artifact", id: a.id, path: "" },
    });
  for (const b of schema.bindings) {
    const source =
      b.support === "observed" ? nodeForRef(b.source) : `t:${b.tool_id}`;
    if (source)
      edge(
        source,
        `e:${b.entity_id}`,
        `${b.support === "observed" ? "Observed" : "Declared"} mapping`,
        { kind: "binding", id: b.id },
        `${b.property} · ${b.support} · ${b.coverage} coverage`,
      );
  }
  for (const e of schema.entities)
    for (const id of e.requirement_ids)
      edge(`r:${id}`, `e:${e.id}`, "Motivates", { kind: "entity", id: e.id });
  for (const r of schema.connectedRelations)
    edge(
      `e:${r.from_entity}`,
      `e:${r.to_entity}`,
      r.name,
      { kind: "relation", id: r.id },
      `${r.from_entity}.${r.from_property} → ${r.to_entity}.${r.to_property} · Proposed relationship`,
    );
  for (const o of schema.operations) {
    edge(`t:${o.tool_id}`, `o:${o.id}`, "Supplies operation", {
      kind: "operation",
      id: o.id,
    });
    for (const id of o.requirement_ids)
      edge(`r:${id}`, `o:${o.id}`, "Requires", { kind: "operation", id: o.id });
    if (o.confirmation_tool_id)
      edge(
        `o:${o.id}`,
        `t:${o.confirmation_tool_id}`,
        "Proposed confirmation",
        { kind: "operation", id: o.id },
      );
  }
  for (const q of input.questions) {
    for (const ref of q.question.evidence ?? []) {
      const source = nodeForRef(ref);
      if (source)
        edge(source, `q:${q.id}`, "Raises question", { kind: "evidence", ref });
    }
    for (const id of q.question.affected ?? []) {
      const candidates = [`r:${id}`, `e:${id}`, `o:${id}`, `t:${id}`].filter(
        (id) => nodes.has(id),
      );
      if (candidates.length === 1)
        edge(`q:${q.id}`, candidates[0], "Affects", {
          kind: "evidence",
          ref: { source: "question", id: q.id, path: "" },
        });
    }
  }
  for (const [scope, gaps] of [
    ["schema", schema.gaps],
    ["requirements", input.requirements?.gaps ?? []],
  ] as const)
    for (const g of gaps)
      for (const ref of g.evidence ?? []) {
        const source = nodeForRef(ref);
        if (source)
          edge(source, `g:${scope}:${g.id}`, "Documents gap", {
            kind: "evidence",
            ref,
          });
      }
  const callIssues = input.calls.filter(
    (call) =>
      call.kind === "mcp" &&
      ["unknown", "failed"].includes(call.status) &&
      !input.artifacts.some(
        (a) =>
          a.kind === "observation" &&
          (a.id === call.response_artifact_id || a.payload.call_id === call.id),
      ),
  );
  for (const call of callIssues) {
    const item: Selection = {
      kind: "record",
      id: call.id,
      title: call.purpose,
      value: call,
    };
    add({
      id: `call:${call.id}`,
      kind: "gap",
      title: call.purpose,
      status:
        call.status === "unknown"
          ? `${call.effect === "write" ? "Write outcome" : "Outcome"} unknown`
          : "Call failed",
      description:
        "No saved response is available. The graph does not infer an effect.",
      warning: true,
      item,
    });
    if (call.tool_id)
      edge(`t:${call.tool_id}`, `call:${call.id}`, "Unresolved call", item);
  }
  const issues = [...schema.issues, ...evidenceIssues(detail)];
  for (const [i, issue] of issues.entries()) {
    const id = `issue:${i}`;
    add({
      id,
      kind: "gap",
      title: issue.message,
      status: "Missing reference",
      description: "Reference check. No substitute was inferred.",
      warning: true,
      item: issue.item,
    });
    const match = [...nodes.values()].find(
      (n) =>
        n.kind !== "gap" &&
        JSON.stringify(n.item) === JSON.stringify(issue.item),
    );
    if (match) edge(match.id, id, "Reference issue", issue.item);
  }
  return {
    nodes: [...nodes.values()],
    edges,
    reportedGaps: schema.gaps.length + (input.requirements?.gaps?.length ?? 0),
    referenceIssues: issues.length,
    callIssues: callIssues.length,
    observedMappings: schema.bindings.filter((b) => b.support === "observed")
      .length,
    declaredMappings: schema.bindings.filter((b) => b.support === "declared")
      .length,
    unmappedEntities: schema.entities.filter(
      (e) => !schema.bindings.some((b) => b.entity_id === e.id),
    ).length,
    ambiguities:
      input.requirements?.requirements.filter((r) => r.ambiguity).length ?? 0,
  };
}
export type EvidenceGraph = ReturnType<typeof buildEvidenceGraph>;

export function bundleEdges(edges: EvidenceEdge[]) {
  const bundles = new Map<string, EvidenceEdge[]>();
  for (const edge of edges) {
    const key = JSON.stringify([edge.source, edge.target, edge.label]);
    bundles.set(key, [...(bundles.get(key) ?? []), edge]);
  }
  return [...bundles.entries()].map(([id, records]) => ({
    ...records[0],
    id,
    records,
    label: `${records[0].label}${records.length > 1 ? ` ×${records.length}` : ""}`,
  }));
}

"use client";

import { memo, useEffect, useMemo, useState } from "react";
import {
  Background,
  BaseEdge,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import ELK, { type ElkNode } from "elkjs/lib/elk.bundled.js";
import "@xyflow/react/dist/style.css";
import {
  entityNodeId,
  propertyHandle,
  propertyType,
  type Entity,
  type SchemaView,
  type Selection,
} from "./schema-adapter";

const WIDTH = 320;
const HEADER = 76;
const ROW = 44;
type EntityNode = Node<
  {
    entity: Entity;
    selection: Selection | null;
    onSelect: (item: Selection) => void;
    observedCount?: number;
  },
  "entity"
>;
type RoutedEdge = Edge<
  { path: string; labelX: number; labelY: number; related: boolean },
  "savedRelation"
>;

const EntityBox = memo(function EntityBox({ data }: NodeProps<EntityNode>) {
  const { entity, selection, onSelect } = data;
  return (
    <div className="schema-entity">
      <button
        className="nodrag schema-entity-heading"
        onClick={() => onSelect({ kind: "entity", id: entity.id })}
      >
        <strong className="block truncate" title={entity.name}>
          {entity.name}
        </strong>
        <span
          className="block truncate text-[10px] text-muted-foreground"
          title={entity.id}
        >
          {entity.id}
        </span>
        <span className="text-[10px] text-primary">
          {data.observedCount === undefined
            ? "Proposed entity"
            : `Accepted entity · ${data.observedCount} observed records`}
        </span>
      </button>
      {entity.properties.map((property) => (
        <div key={property.name} className="relative" style={{ height: ROW }}>
          <Handle
            id={propertyHandle(entity.id, property.name, "in")}
            type="target"
            position={Position.Left}
            isConnectable={false}
          />
          <button
            className={`nodrag schema-property ${selection?.kind === "property" && selection.id === entity.id && selection.property === property.name ? "bg-primary/15 text-primary" : ""}`}
            aria-label={`${entity.id}.${property.name}`}
            onClick={(event) => {
              event.stopPropagation();
              onSelect({
                kind: "property",
                id: entity.id,
                property: property.name,
              });
            }}
          >
            <span className="min-w-0 flex-1 truncate" title={property.name}>
              {property.name}
              {entity.identity_keys?.includes(property.name)
                ? " · identity"
                : ""}
            </span>
            <span
              className="max-w-36 truncate text-muted-foreground"
              title={`${propertyType(property)}${property.unit ? ` (${property.unit})` : ""}`}
            >
              {propertyType(property)}
              {property.unit ? ` (${property.unit})` : ""}
            </span>
          </button>
          <Handle
            id={propertyHandle(entity.id, property.name, "out")}
            type="source"
            position={Position.Right}
            isConnectable={false}
          />
        </div>
      ))}
      <div
        className="h-10 truncate border-t px-3 py-3 text-[10px] text-muted-foreground"
        title={entity.identity_keys?.join(", ")}
      >
        Identity: {entity.identity_keys?.join(", ") || "Unspecified"}
      </div>
    </div>
  );
});
function SavedRelation({ id, data, label, selected }: EdgeProps<RoutedEdge>) {
  if (!data) return null;
  return (
    <BaseEdge
      id={id}
      path={data.path}
      label={label}
      labelX={data.labelX}
      labelY={data.labelY}
      style={{
        stroke:
          selected || data.related
            ? "var(--primary)"
            : "var(--muted-foreground)",
        strokeWidth: selected ? 3 : data.related ? 2 : 1.5,
      }}
      labelStyle={{ fill: "var(--foreground)", fontSize: 11 }}
      labelBgStyle={{ fill: "var(--card)" }}
      interactionWidth={24}
    />
  );
}
const nodeTypes = { entity: EntityBox };
const edgeTypes = { savedRelation: SavedRelation };
const layouts = new Map<string, Promise<ElkNode>>();
function layoutSchema(model: SchemaView, key: string) {
  const cached = layouts.get(key);
  if (cached) return cached;
  const graph: ElkNode = {
    id: "schema",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "RIGHT",
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.spacing.nodeNode": "70",
      "elk.layered.spacing.nodeNodeBetweenLayers": "100",
      "elk.spacing.edgeEdge": "24",
      "elk.spacing.componentComponent": "100",
      "elk.separateConnectedComponents": "true",
    },
    children: model.entities.map((entity) => ({
      id: entityNodeId(entity.id),
      width: WIDTH,
      height: HEADER + entity.properties.length * ROW + 40,
      layoutOptions: { "elk.portConstraints": "FIXED_POS" },
      ports: entity.properties.flatMap((property, index) =>
        (["in", "out"] as const).map((side) => ({
          id: propertyHandle(entity.id, property.name, side),
          x: side === "in" ? 0 : WIDTH,
          y: HEADER + index * ROW + ROW / 2,
          width: 0,
          height: 0,
          layoutOptions: { "elk.port.side": side === "in" ? "WEST" : "EAST" },
        })),
      ),
    })),
    edges: model.connectedRelations.map((relation) => ({
      id: JSON.stringify(["relation", relation.id]),
      sources: [
        propertyHandle(relation.from_entity, relation.from_property, "out"),
      ],
      targets: [propertyHandle(relation.to_entity, relation.to_property, "in")],
      labels: [
        {
          text: relation.name,
          width: Math.min(280, Math.max(60, relation.name.length * 7)),
          height: 24,
        },
      ],
    })),
  };
  const promise = new ELK().layout(graph);
  layouts.set(key, promise);
  if (layouts.size > 8) layouts.delete(layouts.keys().next().value!);
  return promise;
}

export default function SchemaDiagram({
  model,
  schemaKey,
  selection,
  onSelect,
  query,
  inference,
}: {
  model: SchemaView;
  schemaKey: string;
  selection: Selection | null;
  onSelect: (item: Selection) => void;
  query: string;
  inference?: { counts: Record<string, number>; highlighted: string[] };
}) {
  const [layout, setLayout] = useState<{
    key: string;
    graph?: ElkNode;
    error?: string;
  } | null>(null);
  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (!cancelled)
        setLayout({
          key: schemaKey,
          error:
            "Layout took too long. Use the Table view to inspect all saved records.",
        });
      cancelled = true;
    }, 20000);
    layoutSchema(model, schemaKey)
      .then((graph) => {
        if (!cancelled) setLayout({ key: schemaKey, graph });
      })
      .catch(() => {
        if (!cancelled)
          setLayout({
            key: schemaKey,
            error:
              "Layout is unavailable. Use the Table view to inspect all saved records.",
          });
      })
      .finally(() => window.clearTimeout(timer));
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [model, schemaKey]);
  const graph = layout?.key === schemaKey ? layout.graph : undefined;
  const neighborhood = useMemo(() => {
    const entities = new Set<string>();
    const relations = new Set<string>();
    if (selection?.kind === "entity" || selection?.kind === "property")
      entities.add(selection.id);
    for (const relation of model.connectedRelations) {
      const related =
        (selection?.kind === "relation" && selection.id === relation.id) ||
        (selection?.kind === "entity" &&
          (selection.id === relation.from_entity ||
            selection.id === relation.to_entity)) ||
        (selection?.kind === "property" &&
          ((selection.id === relation.from_entity &&
            selection.property === relation.from_property) ||
            (selection.id === relation.to_entity &&
              selection.property === relation.to_property)));
      if (related) {
        relations.add(relation.id);
        entities.add(relation.from_entity);
        entities.add(relation.to_entity);
      }
    }
    return { entities, relations };
  }, [model.connectedRelations, selection]);
  const nodes: EntityNode[] = useMemo(
    () =>
      (graph?.children ?? []).map((node) => {
        const entity = model.entities.find(
          (entity) => entityNodeId(entity.id) === node.id,
        )!;
        const selected =
          (selection?.kind === "entity" || selection?.kind === "property") &&
          selection.id === entity.id;
        const matches =
          !query ||
          JSON.stringify(entity).toLowerCase().includes(query.toLowerCase());
        return {
          id: node.id,
          type: "entity",
          position: { x: node.x ?? 0, y: node.y ?? 0 },
          width: node.width,
          height: node.height,
          data: {
            entity,
            selection,
            onSelect,
            observedCount:
              inference?.counts[entity.id] ?? (inference ? 0 : undefined),
          },
          selected,
          className:
            !selected &&
            (neighborhood.entities.has(entity.id) ||
              inference?.highlighted.includes(entity.id))
              ? "schema-neighbor"
              : undefined,
          ariaLabel: `${entity.name}, ${entity.id}, ${inference ? "accepted" : "proposed"} entity`,
          style: {
            opacity:
              selected ||
              neighborhood.entities.has(entity.id) ||
              inference?.highlighted.includes(entity.id)
                ? 1
                : matches && !neighborhood.entities.size
                  ? 1
                  : 0.3,
          },
        };
      }),
    [
      graph,
      model.entities,
      selection,
      onSelect,
      query,
      neighborhood,
      inference,
    ],
  );
  const edges: RoutedEdge[] = useMemo(
    () =>
      (graph?.edges ?? []).map((edge) => {
        const relation = model.connectedRelations.find(
          (relation) => JSON.stringify(["relation", relation.id]) === edge.id,
        )!;
        const section = edge.sections?.[0];
        const points = section
          ? [
              section.startPoint,
              ...(section.bendPoints ?? []),
              section.endPoint,
            ]
          : [];
        const label = edge.labels?.[0];
        const midpoint = points[Math.floor(points.length / 2)] ?? {
          x: 0,
          y: 0,
        };
        return {
          id: relation.id,
          type: "savedRelation",
          source: entityNodeId(relation.from_entity),
          target: entityNodeId(relation.to_entity),
          sourceHandle: propertyHandle(
            relation.from_entity,
            relation.from_property,
            "out",
          ),
          targetHandle: propertyHandle(
            relation.to_entity,
            relation.to_property,
            "in",
          ),
          label:
            relation.name.length > 40
              ? `${relation.name.slice(0, 39)}…`
              : relation.name,
          ariaLabel: `${relation.name}, ${relation.id}: ${relation.from_entity}.${relation.from_property} to ${relation.to_entity}.${relation.to_property}`,
          selected:
            selection?.kind === "relation" && selection.id === relation.id,
          className: neighborhood.relations.has(relation.id)
            ? "schema-related"
            : undefined,
          style: {
            opacity:
              neighborhood.entities.size &&
              !neighborhood.relations.has(relation.id)
                ? 0.3
                : 1,
          },
          data: {
            related: neighborhood.relations.has(relation.id),
            path: points
              .map(
                (point, index) => `${index ? "L" : "M"}${point.x},${point.y}`,
              )
              .join(" "),
            labelX:
              label?.x !== undefined
                ? label.x + (label.width ?? 0) / 2
                : midpoint.x,
            labelY:
              label?.y !== undefined
                ? label.y + (label.height ?? 0) / 2
                : midpoint.y,
          },
        };
      }),
    [graph, model.connectedRelations, selection, neighborhood],
  );
  if (layout?.key === schemaKey && layout.error)
    return (
      <p role="alert" className="error-panel">
        {layout.error}
      </p>
    );
  if (!graph)
    return (
      <p role="status" className="p-5 text-xs">
        Arranging saved entities...
      </p>
    );
  if (!nodes.length)
    return (
      <p className="border p-5 text-xs">
        {inference
          ? "This kernel has no declared entities."
          : "No saved entities. Inspect operations below or open Review."}
      </p>
    );
  return (
    <div
      className="schema-canvas border"
      aria-label="Schema diagram"
      onKeyDownCapture={(event) => {
        const target = event.target as Element;
        if (
          (event.key !== "Enter" && event.key !== " ") ||
          !target.matches(".react-flow__node, .react-flow__edge")
        )
          return;
        const id = target.getAttribute("data-id");
        if (!id) return;
        event.preventDefault();
        event.stopPropagation();
        const node = nodes.find((node) => node.id === id);
        if (node) onSelect({ kind: "entity", id: node.data.entity.id });
        else if (edges.some((edge) => edge.id === id))
          onSelect({ kind: "relation", id });
      }}
      data-testid="schema-canvas"
    >
      <ReactFlow
        key={schemaKey}
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.15, maxZoom: 1 }}
        minZoom={0.005}
        maxZoom={2}
        colorMode="dark"
        nodesDraggable={false}
        nodesConnectable={false}
        edgesReconnectable={false}
        deleteKeyCode={null}
        nodesFocusable
        edgesFocusable
        onNodeClick={(_, node) =>
          onSelect({ kind: "entity", id: node.data.entity.id })
        }
        onEdgeClick={(_, edge) => onSelect({ kind: "relation", id: edge.id })}
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

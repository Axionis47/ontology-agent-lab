"use client";

import { memo, useEffect, type CSSProperties } from "react";
import {
  Background,
  BaseEdge,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  getViewportForBounds,
  useReactFlow,
  useStore,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import {
  Boxes,
  FileText,
  HelpCircle,
  Link2,
  ScanEye,
  Settings2,
  TriangleAlert,
  Wrench,
} from "lucide-react";
import "@xyflow/react/dist/style.css";
import { graphLabels, type GraphKind } from "./evidence-graph";

export const graphColors: Record<GraphKind, string> = {
  requirement: "#a5b4fc",
  tool: "#7dd3fc",
  observation: "#6ee7b7",
  entity: "#c4b5fd",
  operation: "#f9a8d4",
  question: "#fcd34d",
  source: "#cbd5e1",
  gap: "#fdba74",
};
const icons = {
  requirement: FileText,
  tool: Wrench,
  observation: ScanEye,
  entity: Boxes,
  operation: Settings2,
  question: HelpCircle,
  source: Link2,
  gap: TriangleAlert,
};
export type CanvasCard = {
  id: string;
  kind: GraphKind;
  title: string;
  subtitle: string;
  status: string;
  idLabel?: string;
  count?: number;
  selected?: boolean;
  warning?: boolean;
  x: number;
  y: number;
};
export type CanvasLink = {
  id: string;
  source: string;
  target: string;
  label: string;
  warning?: boolean;
};
type CardNode = Node<CanvasCard & { onOpen: (id: string) => void }, "evidence">;
type LinkEdge = Edge<
  {
    path: string;
    labelX: number;
    labelY: number;
    text: string;
    warning?: boolean;
  },
  "evidence"
>;
const WIDTH = 240;
const HEIGHT = 138;

const EvidenceCard = memo(function EvidenceCard({ data }: NodeProps<CardNode>) {
  const Icon = icons[data.kind];
  return (
    <div
      className={`evidence-card ${data.selected ? "evidence-card-selected" : ""}`}
      style={{ "--evidence-color": graphColors[data.kind] } as CSSProperties}
    >
      <Handle
        type="target"
        position={Position.Left}
        id="left-in"
        isConnectable={false}
      />
      <Handle
        type="source"
        position={Position.Left}
        id="left-out"
        isConnectable={false}
      />
      <Handle
        type="target"
        position={Position.Right}
        id="right-in"
        isConnectable={false}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="right-out"
        isConnectable={false}
      />
      <div className="evidence-card-type">
        <Icon size={15} aria-hidden />
        <span className="truncate" title={data.idLabel}>
          {graphLabels[data.kind]}
          {data.idLabel ? ` · ${data.idLabel}` : ""}
        </span>
        {data.warning && <TriangleAlert size={14} aria-label="Needs review" />}
      </div>
      <button
        type="button"
        className="nodrag evidence-card-title"
        onClick={(event) => {
          event.stopPropagation();
          data.onOpen(data.id);
        }}
        title={data.title}
      >
        {data.count !== undefined && (
          <strong className="evidence-card-count">{data.count}</strong>
        )}
        <span className="line-clamp-2 break-words">{data.title}</span>
      </button>
      <p className="evidence-card-status" title={data.status}>
        {data.status}
      </p>
      <p className="evidence-card-description" title={data.subtitle}>
        {data.subtitle}
      </p>
    </div>
  );
});
function EvidenceLink({ id, data, markerEnd }: EdgeProps<LinkEdge>) {
  if (!data) return null;
  return (
    <BaseEdge
      id={id}
      path={data.path}
      markerEnd={markerEnd}
      label={data.text}
      labelX={data.labelX}
      labelY={data.labelY}
      style={{
        stroke: data.warning ? "#fdba74" : "#94a3b8",
        strokeWidth: 1.6,
        strokeDasharray: data.warning ? "5 4" : undefined,
      }}
      labelStyle={{ fill: "#e2e8f0", fontSize: 12, fontWeight: 500 }}
      labelBgStyle={{ fill: "#18201c" }}
      labelBgPadding={[7, 5]}
      labelBgBorderRadius={4}
      interactionWidth={22}
    />
  );
}
const nodeTypes = { evidence: EvidenceCard };
const edgeTypes = { evidence: EvidenceLink };

function FitCanvas({ boundsKey }: { boundsKey: string }) {
  const { setViewport, viewportInitialized } = useReactFlow();
  const width = useStore((state) => state.width);
  const height = useStore((state) => state.height);
  useEffect(() => {
    if (!viewportInitialized || !width || !height) return;
    void setViewport(
      getViewportForBounds(JSON.parse(boundsKey), width, height, 0.25, 1, 0.1),
    );
  }, [boundsKey, setViewport, viewportInitialized, width, height]);
  return null;
}

export function EvidenceCanvas({
  cards,
  links,
  onOpen,
  onLink,
  label,
}: {
  cards: CanvasCard[];
  links: CanvasLink[];
  onOpen: (id: string) => void;
  onLink: (id: string) => void;
  label: string;
}) {
  const byId = new Map(cards.map((card) => [card.id, card]));
  const minX = Math.min(0, ...cards.map((card) => card.x));
  const minY = Math.min(0, ...cards.map((card) => card.y));
  const boundsKey = JSON.stringify({
    x: minX,
    y: minY,
    width: Math.max(WIDTH, ...cards.map((card) => card.x + WIDTH)) - minX,
    height: Math.max(HEIGHT, ...cards.map((card) => card.y + HEIGHT)) - minY,
  });
  const nodes: CardNode[] = cards.map((card) => ({
    id: card.id,
    type: "evidence",
    position: { x: card.x, y: card.y },
    width: WIDTH,
    height: HEIGHT,
    data: { ...card, onOpen },
    selected: card.selected,
    ariaLabel: `${graphLabels[card.kind]}: ${card.title}, ${card.status}`,
  }));
  const edges: LinkEdge[] = links.flatMap((link, index) => {
    const source = byId.get(link.source),
      target = byId.get(link.target);
    if (!source || !target) return [];
    const forward =
      target.x > source.x || (target.x === source.x && target.y > source.y);
    const sameColumn = source.x === target.x;
    const sx = source.x + (forward || sameColumn ? WIDTH : 0),
      sy = source.y + HEIGHT / 2;
    const tx = target.x + (sameColumn || !forward ? WIDTH : 0),
      ty = target.y + HEIGHT / 2;
    const parallel = links
      .slice(0, index)
      .filter(
        (e) =>
          (e.source === link.source && e.target === link.target) ||
          (e.source === link.target && e.target === link.source),
      ).length;
    const direction = forward || sameColumn ? 1 : -1;
    const offset = 36 + parallel * 38;
    const cx1 = sameColumn
      ? sx + direction * (100 + parallel * 40)
      : sx + direction * Math.max(72, Math.abs(tx - sx) / 2);
    const cx2 = sameColumn
      ? cx1
      : tx - direction * Math.max(72, Math.abs(tx - sx) / 2);
    const cy1 = sy + (parallel ? offset : 0),
      cy2 = ty + (parallel ? offset : 0);
    const self = source.id === target.id;
    const path = self
      ? `M${source.x + WIDTH},${sy} C${source.x + WIDTH + offset * 2},${sy - HEIGHT * 1.4} ${source.x - offset * 2},${sy - HEIGHT * 1.4} ${source.x},${sy}`
      : `M${sx},${sy} C${cx1},${cy1} ${cx2},${cy2} ${tx},${ty}`;
    return [
      {
        id: link.id,
        type: "evidence",
        source: link.source,
        target: link.target,
        sourceHandle: self || forward || sameColumn ? "right-out" : "left-out",
        targetHandle: self
          ? "left-in"
          : sameColumn || !forward
            ? "right-in"
            : "left-in",
        ariaLabel: `${source.title} → ${target.title}: ${link.label}`,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: link.warning ? "#fdba74" : "#94a3b8",
          width: 18,
          height: 18,
        },
        data: {
          path,
          text:
            link.label.length > 32 ? `${link.label.slice(0, 31)}…` : link.label,
          warning: link.warning,
          labelX: self
            ? source.x + WIDTH / 2
            : (sx + 3 * cx1 + 3 * cx2 + tx) / 8,
          labelY: self ? sy - HEIGHT : (sy + 3 * cy1 + 3 * cy2 + ty) / 8,
        },
      },
    ];
  });
  return (
    <div
      className="evidence-canvas"
      role="region"
      aria-label={label}
      onKeyDownCapture={(event) => {
        const target = event.target as Element;
        if (
          !["Enter", " "].includes(event.key) ||
          !target.matches(".react-flow__node, .react-flow__edge")
        )
          return;
        const id = target.getAttribute("data-id");
        if (!id) return;
        event.preventDefault();
        event.stopPropagation();
        if (byId.has(id)) onOpen(id);
        else onLink(id);
      }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        minZoom={0.25}
        maxZoom={1.6}
        colorMode="dark"
        nodesDraggable={false}
        nodesConnectable={false}
        edgesReconnectable={false}
        deleteKeyCode={null}
        nodesFocusable
        edgesFocusable
        zoomOnScroll={false}
        panOnScroll={false}
        onNodeClick={(_, node) => onOpen(node.id)}
        onEdgeClick={(_, edge) => onLink(edge.id)}
      >
        <FitCanvas boundsKey={boundsKey} />
        <Background gap={24} color="#26352b" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

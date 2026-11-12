"use client";

import { useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { DiscoveryDetail } from "@/lib/api";
import { type Selection } from "./schema-adapter";
import {
  buildEvidenceGraph,
  bundleEdges,
  graphKinds,
  graphLabels,
  type GraphKind,
  type EvidenceNode,
} from "./evidence-graph";
import {
  EvidenceCanvas,
  graphColors,
  type CanvasCard,
} from "./evidence-canvas";

const PAGE = 12;
const NEIGHBORS = 3;

export default function TraceMap({
  detail,
  onInspect,
  onReview,
  onSchema,
}: {
  detail: DiscoveryDetail;
  selection: Selection | null;
  onInspect: (item: Selection) => void;
  onReview: () => void;
  onSchema: () => void;
}) {
  const savedKey = JSON.stringify({
    requirements: detail.requirements,
    schema_proposal: detail.schema_proposal,
    artifacts: detail.artifacts,
    questions: detail.questions,
    calls: detail.calls,
    inputs: detail.inputs,
  });
  const graph = useMemo(() => {
    const saved = buildEvidenceGraph(JSON.parse(savedKey));
    const nodes = saved.nodes.filter(
      (node) => !["question", "gap"].includes(node.kind),
    );
    const ids = new Set(nodes.map((node) => node.id));
    return {
      ...saved,
      nodes,
      edges: saved.edges.filter(
        (edge) => ids.has(edge.source) && ids.has(edge.target),
      ),
    };
  }, [savedKey]);
  const [group, setGroup] = useState<GraphKind>("entity");
  const [focus, setFocus] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [neighborPage, setNeighborPage] = useState(0);
  const [linkPage, setLinkPage] = useState(0);
  const selected = graph.nodes.find((n) => n.id === focus);
  const grouped = new Map(
    graphKinds.map((kind) => [
      kind,
      graph.nodes.filter((n) => n.kind === kind),
    ]),
  );
  const kinds = graphKinds.filter(
    (kind) => grouped.get(kind)!.length || kind === "entity",
  );
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));
  const allLinks = selected
    ? graph.edges.filter(
        (e) => e.source === selected.id || e.target === selected.id,
      )
    : graph.edges.filter(
        (e) =>
          byId.get(e.source)?.kind === group ||
          byId.get(e.target)?.kind === group,
      );
  const incoming = selected
    ? [
        ...new Set(
          allLinks
            .filter((e) => e.target === selected.id && e.source !== selected.id)
            .map((e) => e.source),
        ),
      ]
    : [];
  const outgoing = selected
    ? [
        ...new Set(
          allLinks
            .filter((e) => e.source === selected.id && e.target !== selected.id)
            .map((e) => e.target),
        ),
      ].filter((id) => !incoming.includes(id))
    : [];
  const neighbors = [...incoming, ...outgoing];
  const neighborPages = Math.max(1, Math.ceil(neighbors.length / NEIGHBORS));
  const currentNeighbors = Math.min(neighborPage, neighborPages - 1);
  const visibleNeighbors = neighbors.slice(
    currentNeighbors * NEIGHBORS,
    (currentNeighbors + 1) * NEIGHBORS,
  );
  const visibleIds = new Set([selected?.id, ...visibleNeighbors]);
  const focusedBundles = bundleEdges(
    allLinks.filter(
      (e) => visibleIds.has(e.source) && visibleIds.has(e.target),
    ),
  );
  function chooseGroup(kind: GraphKind) {
    setGroup(kind);
    setFocus(null);
    setPage(0);
    setQuery("");
    setLinkPage(0);
  }
  function chooseRecord(node: EvidenceNode) {
    setFocus(node.id);
    setGroup(node.kind);
    setNeighborPage(0);
    setLinkPage(0);
  }
  const overviewCards: CanvasCard[] = kinds.map((kind, i) => {
    const records = grouped.get(kind)!;
    const status =
      kind === "entity"
        ? "Proposals, not validated facts"
        : kind === "tool"
          ? "Declared tool contracts"
          : kind === "observation"
            ? "Actual tool responses"
            : kind === "requirement"
              ? "Derived from task and evidence"
              : kind === "question"
                ? "User intent, not external proof"
                : kind === "gap"
                  ? "Reported gaps and reference checks"
                  : kind === "operation"
                    ? "Proposed read / write contracts"
                    : "Original inputs and saved artifacts";
    const subtitle =
      kind === "entity"
        ? `${graph.observedMappings} observed / ${graph.declaredMappings} declared mappings`
        : kind === "question"
          ? `${records.filter((n) => n.warning).length} unanswered`
          : kind === "gap"
            ? `${graph.reportedGaps} reported · ${graph.referenceIssues} reference issues`
            : `${records.filter((n) => n.warning).length} items need review`;
    return {
      id: `group:${kind}`,
      kind,
      title: graphLabels[kind],
      count: records.length,
      status,
      subtitle,
      selected: group === kind,
      warning: records.some((n) => n.warning),
      x: (i % 2) * 410 + 30,
      y: Math.floor(i / 2) * 190 + 30,
    };
  });
  const groupLinks = new Map<
    string,
    {
      id: string;
      source: string;
      target: string;
      labels: Set<string>;
      count: number;
    }
  >();
  for (const link of allLinks) {
    const sourceKind = byId.get(link.source)!.kind,
      targetKind = byId.get(link.target)!.kind;
    if (sourceKind === targetKind) continue;
    const id = JSON.stringify([sourceKind, targetKind]);
    const bundle = groupLinks.get(id) ?? {
      id,
      source: `group:${sourceKind}`,
      target: `group:${targetKind}`,
      labels: new Set<string>(),
      count: 0,
    };
    bundle.labels.add(link.label);
    bundle.count++;
    groupLinks.set(id, bundle);
  }
  const overviewLinks = [...groupLinks.values()].map((link) => ({
    ...link,
    label: `${link.labels.size === 1 ? [...link.labels][0] : "Saved links"} · ${link.count}`,
    warning: link.source === "group:gap" || link.target === "group:gap",
  }));
  const recordCard = (
    node: EvidenceNode,
    x: number,
    y: number,
  ): CanvasCard => ({
    id: node.id,
    kind: node.kind,
    title: node.title,
    idLabel: node.kind === "entity" ? node.id.slice(2) : undefined,
    status: node.status,
    subtitle: node.description,
    warning: node.warning,
    selected: selected?.id === node.id,
    x,
    y,
  });
  const focusedCards = selected
    ? [
        recordCard(selected, 30, 228),
        ...visibleNeighbors.map((id, i) =>
          recordCard(byId.get(id)!, 440, 30 + i * 198),
        ),
      ]
    : [];
  const searched = query.trim().toLowerCase();
  const records = (searched ? graph.nodes : grouped.get(group)!).filter((n) =>
    `${n.title} ${n.description} ${n.status} ${n.id}`
      .toLowerCase()
      .includes(searched),
  );
  const pages = Math.max(1, Math.ceil(records.length / PAGE));
  const currentPage = Math.min(page, pages - 1);
  const visibleRecords = records.slice(
    currentPage * PAGE,
    (currentPage + 1) * PAGE,
  );
  const connectionPages = Math.max(1, Math.ceil(allLinks.length / PAGE));
  const currentLinks = Math.min(linkPage, connectionPages - 1);
  const reviewCount = graph.nodes.filter((n) => n.warning).length;

  return (
    <section className="min-w-0 space-y-4" aria-label="Evidence graph explorer">
      <div className="evidence-summary">
        <div>
          <p className="text-sm font-semibold">Evidence behind the draft</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Follow links between requirements, tool responses, and proposed
            schema items.
          </p>
        </div>
        <div className="evidence-summary-counts">
          <span>
            <strong>{grouped.get("entity")!.length}</strong> proposed entities
          </span>
          <span>
            <strong>{grouped.get("observation")!.length}</strong> observations
          </span>
          <span>
            <strong>{graph.observedMappings}</strong> observed mappings
          </span>
          <span>
            <strong>{graph.declaredMappings}</strong> declared mappings
          </span>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
        <button className="inspection-link" onClick={onSchema}>
          Open ontology structure (S₀)
        </button>
        <button className="inspection-link" onClick={onReview}>
          Review questions, evidence gaps, and checks
        </button>
      </div>
      <div
        className="flex flex-wrap gap-2"
        role="group"
        aria-label="Evidence groups"
      >
        {kinds.map((kind) => (
          <button
            type="button"
            key={kind}
            className="evidence-group-button"
            aria-pressed={group === kind && !selected}
            onClick={() => chooseGroup(kind)}
          >
            <span
              className="size-2 rounded-full"
              style={{ background: graphColors[kind] }}
              aria-hidden
            />
            {graphLabels[kind]} <strong>{grouped.get(kind)!.length}</strong>
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-medium break-words line-clamp-2">
            {selected
              ? `Connections: ${selected.title}`
              : `Overview: ${graphLabels[group]}`}
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            {selected
              ? `${incoming.length + outgoing.length} connected records · ${allLinks.length} saved links. Arrows follow the saved link direction.`
              : `Showing connections to ${graphLabels[group].toLowerCase()}. Select another group to see its links.`}
          </p>
        </div>
        {selected && (
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => chooseGroup(group)}
            >
              <ArrowLeft aria-hidden />
              Overview
            </Button>
            <Button size="sm" onClick={() => onInspect(selected.item)}>
              Inspect selected record
            </Button>
          </div>
        )}
      </div>
      <EvidenceCanvas
        key={selected ? `${selected.id}:${currentNeighbors}` : "overview"}
        cards={selected ? focusedCards : overviewCards}
        links={
          selected
            ? focusedBundles.map((e) => ({
                ...e,
                warning:
                  byId.get(e.source)?.warning || byId.get(e.target)?.warning,
              }))
            : overviewLinks
        }
        label="Discovery evidence map"
        onOpen={(id) => {
          if (id.startsWith("group:")) chooseGroup(id.slice(6) as GraphKind);
          else {
            const node = byId.get(id);
            if (node) chooseRecord(node);
          }
        }}
        onLink={(id) => {
          if (selected) {
            const bundle = focusedBundles.find((e) => e.id === id);
            if (bundle?.records.length === 1) onInspect(bundle.item);
            else if (bundle)
              onInspect({
                kind: "record",
                id,
                title: `${bundle.records.length} saved connections`,
                value: bundle.records.map((r) => ({
                  connection: r.label,
                  meaning: r.detail,
                  source: byId.get(r.source)?.title,
                  target: byId.get(r.target)?.title,
                })),
              });
          } else {
            const bundle = overviewLinks.find((e) => e.id === id);
            if (bundle)
              onInspect({
                kind: "record",
                id,
                title: bundle.label,
                value: allLinks
                  .filter(
                    (e) =>
                      `group:${byId.get(e.source)?.kind}` === bundle.source &&
                      `group:${byId.get(e.target)?.kind}` === bundle.target,
                  )
                  .map((e) => ({
                    connection: e.label,
                    source: byId.get(e.source)?.title,
                    target: byId.get(e.target)?.title,
                    meaning: e.detail,
                  })),
              });
          }
        }}
      />
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <p>
          {selected
            ? `Showing ${visibleNeighbors.length} of ${incoming.length + outgoing.length} connected records. Use the list below for every saved link.`
            : `${graph.nodes.length} saved records · ${graph.edges.length} links · ${reviewCount} records flagged in this map. Group totals include all map records.`}{" "}
          Dashed amber links mark items that need review. Pan to explore. Use +
          / − to zoom.
        </p>
        {selected && neighborPages > 1 && (
          <Pager
            label="Connected records"
            page={currentNeighbors}
            pages={neighborPages}
            onChange={setNeighborPage}
          />
        )}
      </div>
      <section className="space-y-3" aria-label="Evidence records">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-medium">
            {searched ? "Matching records" : graphLabels[group]}{" "}
            <span className="text-muted-foreground">({records.length})</span>
          </h3>
          <Pager
            label="Evidence records"
            page={currentPage}
            pages={pages}
            onChange={setPage}
          />
        </div>
        <div className="relative">
          <Search
            className="absolute top-3 left-3 size-4 text-muted-foreground"
            aria-hidden
          />
          <Input
            aria-label="Find evidence record"
            placeholder="Find a name, saved ID, status, or description"
            className="pl-10"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(0);
            }}
          />
        </div>
        <div
          className="max-h-80 space-y-2 overflow-auto"
          tabIndex={0}
          aria-label="Evidence record list"
        >
          {visibleRecords.map((node) => (
            <article
              key={node.id}
              className="evidence-record"
              data-kind={node.kind}
            >
              <div className="min-w-0">
                <p
                  className="text-[11px]"
                  style={{ color: graphColors[node.kind] }}
                >
                  {graphLabels[node.kind]} · {node.status}
                </p>
                <p className="mt-1 break-words text-sm">{node.title}</p>
                <p className="mt-1 line-clamp-2 break-words text-xs text-muted-foreground">
                  {node.description}
                </p>
                <p className="mt-1 break-all text-[10px] text-muted-foreground">
                  {node.id.slice(node.id.indexOf(":") + 1)}
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  aria-label={`Connections for ${node.id}`}
                  onClick={() => chooseRecord(node)}
                >
                  Connections
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  aria-label={`Inspect ${node.id}`}
                  onClick={() => onInspect(node.item)}
                >
                  Inspect
                </Button>
              </div>
            </article>
          ))}
          {!records.length && (
            <p className="border p-4 text-xs">
              {searched
                ? "No records match this search."
                : "No saved records in this group. Missing records do not establish confirmed absence."}
            </p>
          )}
        </div>
      </section>
      <section className="space-y-3" aria-label="Saved graph connections">
        <div className="flex flex-wrap justify-between gap-2">
          <h3 className="text-sm font-medium">
            Saved connections ({allLinks.length})
          </h3>
          <Pager
            label="Saved connections"
            page={currentLinks}
            pages={connectionPages}
            onChange={setLinkPage}
          />
        </div>
        <div className="max-h-80 space-y-2 overflow-auto" tabIndex={0}>
          {allLinks
            .slice(currentLinks * PAGE, (currentLinks + 1) * PAGE)
            .map((link) => (
              <article key={link.id} className="evidence-connection">
                <p className="text-xs font-medium text-primary">{link.label}</p>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <button
                    type="button"
                    className="inspection-link max-w-full break-words text-left"
                    onClick={() => chooseRecord(byId.get(link.source)!)}
                  >
                    {byId.get(link.source)?.title}
                  </button>
                  <ArrowRight size={14} aria-label="to" />
                  <button
                    type="button"
                    className="inspection-link max-w-full break-words text-left"
                    onClick={() => chooseRecord(byId.get(link.target)!)}
                  >
                    {byId.get(link.target)?.title}
                  </button>
                </div>
                <p className="break-words text-xs text-muted-foreground">
                  {link.detail}
                </p>
                <button
                  type="button"
                  className="inspection-link text-xs"
                  aria-label={`Inspect connection ${link.id}`}
                  onClick={() => onInspect(link.item)}
                >
                  Inspect evidence
                </button>
              </article>
            ))}
          {!allLinks.length && (
            <p className="border p-4 text-xs">
              No explicit connections are saved for this selection. No
              relationship was inferred.
            </p>
          )}
        </div>
      </section>
    </section>
  );
}

function Pager({
  label,
  page,
  pages,
  onChange,
}: {
  label: string;
  page: number;
  pages: number;
  onChange: (page: number) => void;
}) {
  return (
    <div
      className="flex items-center gap-2 text-xs"
      role="group"
      aria-label={`${label} pages`}
    >
      <Button
        type="button"
        size="sm"
        variant="ghost"
        aria-label={`Previous ${label.toLowerCase()}`}
        disabled={page === 0}
        onClick={() => onChange(page - 1)}
      >
        Previous
      </Button>
      <span aria-live="polite">
        {page + 1} / {pages}
      </span>
      <Button
        type="button"
        size="sm"
        variant="ghost"
        aria-label={`Next ${label.toLowerCase()}`}
        disabled={page + 1 >= pages}
        onClick={() => onChange(page + 1)}
      >
        Next
      </Button>
    </div>
  );
}

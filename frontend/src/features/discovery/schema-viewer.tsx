"use client";

import dynamic from "next/dynamic";
import { Component, useMemo, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { DiscoveryDetail } from "@/lib/api";
import {
  adaptSchema,
  evidenceIssues,
  propertyType,
  selectionKey,
  type Schema,
  type Selection,
} from "./schema-adapter";

const SchemaDiagram = dynamic(() => import("./schema-diagram"), {
  ssr: false,
  loading: () => <p className="p-5 text-xs">Loading diagram...</p>,
});
class DiagramBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <p role="alert" className="error-panel">
        The diagram is unavailable. Use the Table view to inspect all saved
        records.
      </p>
    ) : (
      this.props.children
    );
  }
}

export function SchemaViewer({
  detail,
  selection,
  onSelect,
  onReview,
}: {
  detail: DiscoveryDetail;
  selection: Selection | null;
  onSelect: (item: Selection) => void;
  onReview: () => void;
}) {
  const [view, setView] = useState("diagram");
  const [query, setQuery] = useState("");
  const schemaKey = JSON.stringify(detail.schema_proposal ?? {});
  const model = useMemo(
    () => adaptSchema(JSON.parse(schemaKey) as Schema),
    [schemaKey],
  );
  const issues = [...model.issues, ...evidenceIssues(detail)];
  const matches = (value: unknown) =>
    JSON.stringify(value).toLowerCase().includes(query.trim().toLowerCase());
  const selectButton = (item: Selection, label: ReactNode) => (
    <button
      type="button"
      className="inspection-link text-left"
      aria-pressed={selectionKey(selection) === selectionKey(item)}
      onClick={() => onSelect(item)}
    >
      {label}
    </button>
  );
  if (!detail.schema_proposal)
    return (
      <p className="text-xs text-muted-foreground">
        Schema proposals will appear after requirement analysis.
      </p>
    );
  return (
    <section aria-label="Schema (S₀)" className="min-w-0 space-y-4">
      <p className="text-xs text-muted-foreground">
        Schema records are proposals. Source mappings keep their saved declared
        or observed support. Cardinality is unspecified.
      </p>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="group" aria-label="Schema view" className="flex gap-1">
          {["diagram", "table"].map((value) => (
            <Button
              key={value}
              size="sm"
              variant={view === value ? "secondary" : "outline"}
              aria-pressed={view === value}
              onClick={() => setView(value)}
            >
              {value === "diagram" ? "Diagram" : "Table"}
            </Button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          {model.entities.length} entities · {model.relations.length}{" "}
          relationships
        </p>
      </div>
      <Input
        aria-label="Search schema"
        placeholder="Search saved names, IDs, types, or fields"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {query && (
        <div
          className="max-h-40 overflow-auto border p-3 text-xs"
          aria-label="Schema search results"
        >
          {model.entities.filter(matches).map((entity) => (
            <p key={entity.id}>
              {selectButton(
                { kind: "entity", id: entity.id },
                `${entity.name} · ${entity.id}`,
              )}
            </p>
          ))}
          {model.relations.filter(matches).map((relation) => (
            <p key={relation.id}>
              {selectButton(
                { kind: "relation", id: relation.id },
                `${relation.name} · ${relation.id}`,
              )}
            </p>
          ))}
          {!model.entities.some(matches) && !model.relations.some(matches) && (
            <p>No matching entities or relationships.</p>
          )}
        </div>
      )}
      {issues.length > 0 && (
        <details className="border border-amber-500/40 p-3 text-xs" open>
          <summary>Reference issues ({issues.length})</summary>
          <ul className="mt-2 max-h-40 space-y-2 overflow-auto">
            {issues.map((issue, i) => (
              <li key={i}>{selectButton(issue.item, issue.message)}</li>
            ))}
          </ul>
        </details>
      )}
      {view === "diagram" ? (
        <DiagramBoundary key={schemaKey}>
          <SchemaDiagram
            model={model}
            schemaKey={schemaKey}
            query={query.trim()}
            selection={selection}
            onSelect={onSelect}
          />
        </DiagramBoundary>
      ) : (
        <div
          role="region"
          aria-label="Schema table"
          tabIndex={0}
          className="max-h-[560px] overflow-auto border focus-visible:outline-2 focus-visible:outline-primary"
        >
          <table className="schema-table">
            <caption className="p-3 text-left text-xs">
              Saved entities and properties
            </caption>
            <thead>
              <tr>
                <th>Entity / saved ID</th>
                <th>Property</th>
                <th>Type</th>
                <th>Unit</th>
                <th>Identity declaration</th>
              </tr>
            </thead>
            <tbody>
              {model.entities.filter(matches).flatMap((entity) =>
                entity.properties.length
                  ? entity.properties.map((property, index) => (
                      <tr key={JSON.stringify([entity.id, property.name])}>
                        <td>
                          {index === 0 &&
                            selectButton(
                              { kind: "entity", id: entity.id },
                              <>
                                {entity.name}
                                <span className="block text-muted-foreground">
                                  {entity.id}
                                </span>
                              </>,
                            )}
                        </td>
                        <td>
                          {selectButton(
                            {
                              kind: "property",
                              id: entity.id,
                              property: property.name,
                            },
                            property.name,
                          )}
                        </td>
                        <td>{propertyType(property)}</td>
                        <td>{property.unit ?? "Unspecified"}</td>
                        <td>
                          {entity.identity_keys?.includes(property.name)
                            ? "Identity property"
                            : "Not declared"}
                        </td>
                      </tr>
                    ))
                  : [
                      <tr key={entity.id}>
                        <td>
                          {selectButton(
                            { kind: "entity", id: entity.id },
                            <>
                              {entity.name}
                              <span className="block text-muted-foreground">
                                {entity.id}
                              </span>
                            </>,
                          )}
                        </td>
                        <td colSpan={4}>No properties supplied.</td>
                      </tr>,
                    ],
              )}
            </tbody>
          </table>
          {!model.entities.some(matches) && (
            <p className="p-4 text-xs">No matching entities.</p>
          )}
        </div>
      )}
      <details
        className="border p-3 text-xs"
        open={view === "table" || Boolean(query)}
      >
        <summary>Relationships ({model.relations.length})</summary>
        <div className="mt-3 max-h-64 space-y-3 overflow-auto">
          {model.relations.filter(matches).map((relation) => (
            <article
              className="space-y-1 border-b pb-3 break-words"
              key={relation.id}
            >
              {selectButton(
                { kind: "relation", id: relation.id },
                `${relation.name} · ${relation.id}`,
              )}
              <p>
                {relation.from_entity}.{relation.from_property} →{" "}
                {relation.to_entity}.{relation.to_property}
              </p>
              <p className="text-muted-foreground">
                Proposed relationship · Cardinality: unspecified
              </p>
            </article>
          ))}
          {!model.relations.some(matches) && <p>No matching relationships.</p>}
        </div>
      </details>
      <details
        className="border p-3 text-xs"
        open={view === "table" || Boolean(query)}
      >
        <summary>Source mappings ({model.bindings.length})</summary>
        <div className="mt-3 max-h-64 space-y-3 overflow-auto">
          {model.bindings.filter(matches).map((binding) => (
            <article
              key={binding.id}
              className="space-y-1 border-b pb-3 break-words"
            >
              {selectButton(
                { kind: "binding", id: binding.id },
                `${binding.entity_id}.${binding.property} · ${binding.id}`,
              )}
              <p>
                Source support: {binding.support} · Coverage: {binding.coverage}
              </p>
              {selectButton(
                { kind: "evidence", ref: binding.source },
                `${binding.source.source}: ${binding.source.path || binding.source.id}`,
              )}
            </article>
          ))}
          {!model.bindings.some(matches) && <p>No matching source mappings.</p>}
        </div>
      </details>
      <section aria-label="Operations and prerequisites" className="space-y-3">
        <h3 className="text-sm">Operations and prerequisites</h3>
        <p className="text-xs text-muted-foreground">
          Prerequisites are saved text. They do not define links between
          operations.
        </p>
        <div className="max-h-80 space-y-3 overflow-auto">
          {model.operations.filter(matches).map((operation) => (
            <article
              className="space-y-2 border p-3 text-xs break-words"
              key={operation.id}
            >
              {selectButton(
                { kind: "operation", id: operation.id },
                operation.id,
              )}
              <p>
                Tool: {operation.tool_id} · Proposed effect: {operation.effect}
              </p>
              <p>Outputs: {operation.outputs}</p>
              <p className="font-medium">Prerequisites</p>
              {operation.prerequisites.length ? (
                <ul className="list-inside list-disc space-y-1">
                  {operation.prerequisites.map((text, i) => (
                    <li key={i}>{text}</li>
                  ))}
                </ul>
              ) : (
                <p>None supplied.</p>
              )}
              {operation.confirmation_tool_id && (
                <p>Confirmation tool: {operation.confirmation_tool_id}</p>
              )}
              {operation.limitations.length > 0 && (
                <>
                  <p className="font-medium">Limitations</p>
                  <ul className="list-inside list-disc">
                    {operation.limitations.map((text, i) => (
                      <li key={i}>{text}</li>
                    ))}
                  </ul>
                </>
              )}
            </article>
          ))}
        </div>
        {!model.operations.some(matches) && (
          <p className="text-xs text-muted-foreground">
            No matching operations.
          </p>
        )}
      </section>
      {model.gaps.length > 0 && (
        <button className="inspection-link text-xs" onClick={onReview}>
          Review evidence gaps ({model.gaps.length})
        </button>
      )}
    </section>
  );
}

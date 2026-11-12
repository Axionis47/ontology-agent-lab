"use client";

import { useEffect, useId, useState } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { Agent, Connection, Tool } from "@/lib/api";

export function ToolCatalog({
  tools,
  connections,
  agent,
  onSave,
  selection,
}: {
  tools: Tool[];
  connections: Connection[];
  agent?: Agent;
  onSave?: (ids: string[]) => Promise<void>;
  selection?: {
    toolIds: string[];
    savedToolIds: string[];
    onChange: (ids: string[]) => void;
  };
}) {
  const id = useId();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [toolIds, setToolIds] = useState(agent?.tool_ids ?? []);
  const savedKey = JSON.stringify(agent?.tool_ids ?? []);
  const [previousSavedKey, setPreviousSavedKey] = useState(savedKey);
  if (savedKey !== previousSavedKey) {
    setPreviousSavedKey(savedKey);
    setToolIds(agent?.tool_ids ?? []);
  }
  const selected = new Set(selection?.toolIds ?? toolIds);
  const original = new Set(selection?.savedToolIds ?? agent?.tool_ids ?? []);
  const editable = Boolean(agent || selection);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [inspected, setInspected] = useState<Tool | null>(null);
  const dirty =
    selected.size !== original.size ||
    [...selected].some((id) => !original.has(id));
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  const connectionMap = new Map(
    connections.map((connection) => [connection.id, connection]),
  );
  const visible = tools.filter(
    (tool) =>
      (filter === "all" || selected.has(tool.id)) &&
      `${tool.name} ${tool.description} ${connectionMap.get(tool.connection_id)?.name ?? tool.connection_name}`
        .toLowerCase()
        .includes(query.trim().toLowerCase()),
  );
  const groups = new Map<string, Tool[]>();
  for (const tool of visible) {
    const group = groups.get(tool.connection_id) ?? [];
    group.push(tool);
    groups.set(tool.connection_id, group);
  }
  if (filter === "all")
    for (const connection of connections) {
      if (
        !tools.some((tool) => tool.connection_id === connection.id) &&
        connection.name.toLowerCase().includes(query.trim().toLowerCase())
      )
        groups.set(connection.id, []);
    }
  const selectedServers = new Set(
    tools
      .filter((tool) => selected.has(tool.id))
      .map((tool) => tool.connection_id),
  ).size;
  async function save() {
    if (!onSave) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await onSave([...selected]);
      setMessage("Tool selections saved.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      aria-label={editable ? "Agent tool access" : "Shared tool catalog"}
      className="min-w-0 space-y-3"
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="section-title">
            {selection
              ? "MCP servers and tools"
              : agent
                ? "Tool access"
                : "Shared tool catalog"}
          </h2>
          <p className="mt-2 text-xs text-muted-foreground">
            Tools from this task&apos;s Model Context Protocol (MCP)
            connections.
          </p>
        </div>
        {editable && (
          <span className="text-xs text-primary" data-testid="selected-count">
            {selected.size} selected{dirty ? " / unsaved" : " / saved"}
          </span>
        )}
      </div>
      {editable && (
        <p aria-label="Selected MCP servers and tools" className="text-xs">
          {selectedServers} MCP servers / {selected.size} tools selected
        </p>
      )}
      <div className="relative">
        <Search
          aria-hidden
          className="absolute top-3 left-3 size-4 text-muted-foreground"
        />
        <Input
          aria-label="Search tools"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="h-10 pl-10"
          placeholder="Search tools, descriptions, or MCPs..."
        />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <span aria-live="polite">
          {visible.length} of {tools.length} tools
        </span>
        {editable && (
          <div role="group" aria-label="Tool filter" className="flex gap-1">
            {["all", "selected"].map((value) => (
              <Button
                key={value}
                type="button"
                size="sm"
                variant={filter === value ? "secondary" : "ghost"}
                aria-pressed={filter === value}
                onClick={() => setFilter(value)}
              >
                {value === "all" ? "All" : "Selected"}
              </Button>
            ))}
          </div>
        )}
      </div>
      <div
        role="region"
        aria-label="Tool list"
        tabIndex={0}
        className="max-h-[min(420px,50dvh)] overflow-y-auto overscroll-contain border focus-visible:outline-2 focus-visible:outline-primary [scrollbar-gutter:stable]"
      >
        {visible.length === 0 && (
          <p className="p-5 text-xs text-muted-foreground">
            {!tools.length
              ? "No tools discovered yet."
              : filter === "selected" && !selected.size
                ? "No tools selected."
                : "No tools match your search or filter."}
          </p>
        )}
        {[...groups].map(([connectionId, group]) => {
          const connection = connectionMap.get(connectionId);
          const name =
            connection?.name ?? group[0]?.connection_name ?? connectionId;
          return (
            <section key={connectionId} aria-label={`Tools from ${name}`}>
              <div className="flex items-center justify-between gap-3 border-y bg-secondary/40 px-3 py-2 text-xs">
                <span className="min-w-0 break-words font-semibold">
                  <span>{name}</span>{" "}
                  <span className="ml-2 font-normal text-muted-foreground">
                    {connection?.status.replaceAll("_", " ") ??
                      "Connection unavailable"}
                  </span>
                </span>
                <span className="shrink-0 text-muted-foreground">
                  {group.length} tools
                </span>
              </div>
              {!group.length && (
                <p className="p-4 text-xs text-muted-foreground">
                  No tools discovered. Open the task&apos;s MCPs tab to connect
                  or refresh this server.
                </p>
              )}
              {group.map((tool) => (
                <div
                  key={tool.id}
                  className={`tool-row ${selected.has(tool.id) && editable ? "tool-selected" : ""}`}
                >
                  {editable && (
                    <Checkbox
                      aria-label={`${name}:${tool.name}`}
                      id={`${id}-tool-${tool.id}`}
                      checked={selected.has(tool.id)}
                      disabled={
                        busy ||
                        (!tool.available &&
                          !original.has(tool.id) &&
                          !selected.has(tool.id))
                      }
                      onCheckedChange={(checked) => {
                        const next = new Set(selected);
                        if (checked) next.add(tool.id);
                        else next.delete(tool.id);
                        if (selection) selection.onChange([...next]);
                        else setToolIds([...next]);
                        setMessage("");
                      }}
                    />
                  )}
                  <div className="min-w-0 flex-1">
                    <label
                      className="block break-all text-xs font-medium"
                      htmlFor={editable ? `${id}-tool-${tool.id}` : undefined}
                    >
                      {tool.name}
                    </label>
                    <p className="mt-1 line-clamp-2 break-words text-xs leading-5 text-muted-foreground">
                      {tool.description || "No description supplied."}
                    </p>
                    <span
                      className={`text-[10px] ${tool.available ? "text-muted-foreground" : "text-amber-300"}`}
                    >
                      {tool.available ? "Available" : "Unavailable"}
                    </span>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    aria-label={`Details for ${name}:${tool.name}`}
                    onClick={() => setInspected(tool)}
                  >
                    Details
                  </Button>
                </div>
              ))}
            </section>
          );
        })}
      </div>
      {agent && (
        <div className="flex flex-wrap items-center justify-between gap-3 border bg-card p-3">
          <p className="text-xs text-muted-foreground">
            New tools stay unselected after discovery.
          </p>
          <div className="flex items-center gap-3">
            <span role="status" className="text-xs text-primary">
              {message}
            </span>
            <Button type="button" disabled={busy || !dirty} onClick={save}>
              {busy ? "Saving..." : "Save tools"}
            </Button>
          </div>
        </div>
      )}
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
      <Dialog
        open={Boolean(inspected)}
        onOpenChange={(open) => {
          if (!open) setInspected(null);
        }}
      >
        <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle className="break-all pr-8">
              {inspected?.name}
            </DialogTitle>
            <DialogDescription>
              {inspected?.connection_name} ·{" "}
              {inspected?.available ? "Available" : "Unavailable"}
            </DialogDescription>
          </DialogHeader>
          <p className="whitespace-pre-wrap break-words text-sm">
            {inspected?.description || "No description supplied."}
          </p>
          <details className="text-xs">
            <summary>Input schema</summary>
            <pre className="mt-3 max-h-64 overflow-auto">
              {JSON.stringify(inspected?.input_schema, null, 2)}
            </pre>
          </details>
        </DialogContent>
      </Dialog>
    </section>
  );
}

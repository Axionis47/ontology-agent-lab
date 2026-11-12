"use client";

import { useEffect, useState } from "react";
import { Search, Terminal, ChevronDown } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import type { Agent, Connection, Tool } from "@/lib/api";

export function ToolCatalog({
  tools,
  connections,
  agent,
  onSave,
}: {
  tools: Tool[];
  connections: Connection[];
  agent?: Agent;
  onSave?: (ids: string[]) => Promise<void>;
}) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(new Set(agent?.tool_ids ?? []));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const original = new Set(agent?.tool_ids ?? []);
  const dirty =
    selected.size !== original.size ||
    [...selected].some((id) => !original.has(id));
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  const visible = tools.filter((tool) =>
    `${tool.name} ${tool.description} ${tool.connection_name}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
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
      aria-label={agent ? "Agent tool access" : "Shared tool catalog"}
      className="space-y-5"
    >
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="section-title">
            {agent ? "Tool access" : "Shared tool catalog"}
          </h2>
          <p className="mt-2 text-xs text-muted-foreground">
            {agent
              ? "Select individual tools for this agent's responsibilities."
              : "Tools discovered from this task's MCP connections."}
          </p>
        </div>
        {agent && (
          <span className="text-xs text-primary" data-testid="selected-count">
            {selected.size} selected{dirty ? " / unsaved" : " / saved"}
          </span>
        )}
      </div>
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
      {visible.length === 0 && (
        <div className="empty-state">
          <Terminal className="mb-4 size-6 text-muted-foreground" />
          <p>
            {tools.length
              ? "No tools match your search."
              : "No tools discovered yet."}
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            {tools.length
              ? "Try another search term."
              : "Add an MCP in the task's MCPs tab to populate this catalog."}
          </p>
        </div>
      )}
      <div className="space-y-5">
        {connections.map((connection) => {
          const group = visible.filter(
            (tool) => tool.connection_id === connection.id,
          );
          if (!group.length) return null;
          return (
            <div className="overflow-hidden border" key={connection.id}>
              <div className="flex items-center justify-between gap-3 border-b bg-secondary/40 px-4 py-3 text-xs">
                <span className="flex min-w-0 items-center gap-2">
                  <ChevronDown className="size-3" />
                  <span className="truncate font-semibold">
                    {connection.name}
                  </span>
                  <span
                    className={`status-dot ${connection.status === "connected" ? "status-online" : ""}`}
                  />
                  <span className="text-muted-foreground">
                    {connection.status.replaceAll("_", " ")}
                  </span>
                </span>
                <span className="shrink-0 text-muted-foreground">
                  {group.length} tools
                </span>
              </div>
              {group.map((tool) => (
                <div
                  key={tool.id}
                  className={`tool-row ${selected.has(tool.id) && agent ? "tool-selected" : ""}`}
                >
                  {agent && (
                    <Checkbox
                      aria-label={`${connection.name}:${tool.name}`}
                      id={`tool-${tool.id}`}
                      checked={selected.has(tool.id)}
                      disabled={
                        busy || (!tool.available && !original.has(tool.id))
                      }
                      onCheckedChange={(checked) => {
                        const next = new Set(selected);
                        if (checked) next.add(tool.id);
                        else next.delete(tool.id);
                        setSelected(next);
                        setMessage("");
                      }}
                    />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <label
                        className="cursor-pointer text-sm"
                        htmlFor={agent ? `tool-${tool.id}` : undefined}
                      >
                        {tool.name}
                      </label>
                      {!tool.available && (
                        <span className="text-[10px] text-amber-300">
                          UNAVAILABLE
                        </span>
                      )}
                    </div>
                    <p className="mt-1 break-words text-xs leading-6 text-muted-foreground">
                      {tool.description ||
                        "No description provided by this MCP."}
                    </p>
                    <details className="mt-2 text-[10px] text-muted-foreground">
                      <summary className="w-fit cursor-pointer hover:text-foreground">
                        Input schema
                      </summary>
                      <pre className="mt-2 max-h-48 overflow-auto border bg-background p-3">
                        {JSON.stringify(tool.input_schema, null, 2)}
                      </pre>
                    </details>
                  </div>
                </div>
              ))}
            </div>
          );
        })}
      </div>
      {agent && (
        <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-3 border bg-card px-4 py-4 shadow-lg">
          <div className="text-xs">
            <span className="text-muted-foreground">ACCESS IS EXPLICIT</span>
            <p className="mt-1">New tools stay unselected after discovery.</p>
          </div>
          <div className="flex items-center gap-3">
            <span role="status" className="text-xs text-primary">
              {message}
            </span>
            <Button disabled={busy || !dirty} onClick={save}>
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
    </section>
  );
}

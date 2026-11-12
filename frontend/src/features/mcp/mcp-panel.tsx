import { Network } from "lucide-react";
import type { Connection, Tool } from "@/lib/api";
import { ToolCatalog } from "@/features/tools/tool-catalog";
import { ConnectionDialog } from "./connection-dialogs";
import { ConnectionCard } from "./connection-card";
import type { McpActions } from "./use-mcp-actions";

export function McpPanel({
  connections,
  tools,
  actions,
}: {
  connections: Connection[];
  tools: Tool[];
  actions: McpActions;
}) {
  const { busy, reconnect, createConnection, updateToken, removeConnection } =
    actions;
  return (
    <>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="section-title">MCP connections</h2>
          <p className="mt-2 text-xs text-muted-foreground">
            Connect a server to discover its tools.
          </p>
        </div>
        <ConnectionDialog onSave={createConnection} />
      </div>
      {connections.length === 0 && (
        <div className="empty-state mb-8">
          <Network className="mb-4 size-6 text-muted-foreground" />
          <p>No MCPs connected.</p>
          <p className="mt-2 text-xs text-muted-foreground">
            Add a remote MCP endpoint to discover tools.
          </p>
        </div>
      )}
      <div className="mb-10 space-y-3">
        {connections.map((connection) => (
          <ConnectionCard
            key={connection.id}
            connection={connection}
            busy={busy === connection.id}
            onRefresh={() => reconnect(connection.id)}
            onUpdateToken={(token) => updateToken(connection.id, token)}
            onRemove={() => removeConnection(connection)}
          />
        ))}
      </div>
      <ToolCatalog tools={tools} connections={connections} />
    </>
  );
}

import { ArrowUpRight, Bot, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Agent, AgentInput, Connection, Tool } from "@/lib/api";
import { AgentDialog } from "./agent-dialog";

export function AgentsPanel({
  agents,
  connections,
  tools,
  onCreate,
  onOpen,
}: {
  agents: Agent[];
  connections: Connection[];
  tools: Tool[];
  onCreate: (configuration: AgentInput) => Promise<void>;
  onOpen: (id: string) => void;
}) {
  return (
    <>
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <h2 className="section-title">Agents</h2>
          <p className="mt-2 text-xs text-muted-foreground">
            Each agent has its own task surface and tool access.
          </p>
        </div>
        <AgentDialog
          trigger={
            <Button>
              <Plus />
              Add agent
            </Button>
          }
          onSave={onCreate}
          connections={connections}
          tools={tools}
        />
      </div>
      {agents.length === 0 ? (
        <div className="empty-state">
          <Bot className="mb-4 size-6 text-muted-foreground" />
          <p>No agents in this task.</p>
          <p className="mt-2 text-xs text-muted-foreground">
            Add an agent. Complete its task surface. Select its tools.
          </p>
        </div>
      ) : (
        <div className="border">
          {agents.map((a, index) => (
            <button
              key={a.id}
              className="task-row"
              onClick={() => onOpen(a.id)}
            >
              <span className="text-xs text-muted-foreground">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div className="min-w-0 flex-1 text-left">
                <p>{a.name}</p>
                <p className="mt-2 truncate text-xs text-muted-foreground">
                  {a.responsibilities}
                </p>
              </div>
              <span className="shrink-0 text-xs text-primary">
                {a.tool_ids?.length || 0} tools
              </span>
              <ArrowUpRight className="size-4 text-muted-foreground" />
            </button>
          ))}
        </div>
      )}
    </>
  );
}

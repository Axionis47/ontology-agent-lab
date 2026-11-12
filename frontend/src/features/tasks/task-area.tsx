"use client";

import {
  Bot,
  ChevronRight,
  FileText,
  Layers,
  LockKeyhole,
  Network,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, type Agent, type AgentInput, type Task } from "@/lib/api";
import { AgentDialog } from "@/features/agents/agent-dialog";
import { AgentsPanel } from "@/features/agents/agents-panel";
import { ModelConnectionPanel } from "@/features/agents/model-connection-panel";
import { DiscoveryPanel } from "@/features/discovery/discovery-panel";
import { TrainingPanel } from "@/features/training/training-panel";
import { InferencePanel } from "@/features/inference/inference-panel";
import { useMcpActions } from "@/features/mcp/use-mcp-actions";
import { McpPanel } from "@/features/mcp/mcp-panel";
import { ToolCatalog } from "@/features/tools/tool-catalog";
import { RenameTaskDialog } from "./rename-task-dialog";
import { TaskScopeView } from "./scope/task-scope-view";
import { useTaskData } from "./use-task-data";

export type TaskTab = "scope" | "agents" | "mcps";

export function TaskArea({
  user,
  task,
  agentId,
  tab,
  agentPage,
  runId,
  agents,
  onAgentsLoaded,
  onAgentCreated,
  onAgentUpdated,
  onTaskUpdated,
  onHome,
  onTaskHome,
  onOpenAgent,
  onTabChange,
  onAgentPageChange,
  onRunChange,
}: {
  user: string;
  task: Task;
  agentId: string | null;
  tab: TaskTab;
  agentPage: "discovery" | "training" | "inference";
  runId: string | null;
  agents: Agent[];
  onAgentsLoaded: (taskId: string, agents: Agent[]) => void;
  onAgentCreated: (agent: Agent) => void;
  onAgentUpdated: (agent: Agent) => void;
  onTaskUpdated: (task: Task) => void;
  onHome: () => void;
  onTaskHome: () => void;
  onOpenAgent: (id: string) => void;
  onTabChange: (tab: TaskTab) => void;
  onAgentPageChange: (page: "discovery" | "training" | "inference") => void;
  onRunChange: (id: string) => void;
}) {
  const { connections, tools, loaded, error, reload, reportError } =
    useTaskData(user, task.id, onAgentsLoaded);
  const connectionActions = useMcpActions(user, task.id, reload, reportError);
  const agent = agents.find((item) => item.id === agentId);
  const base = `/tasks/${task.id}`;

  async function createAgent(configuration: AgentInput) {
    const agent = await api<Agent>(
      user,
      `${base}/agents`,
      "POST",
      configuration,
    );
    onAgentCreated(agent);
    onOpenAgent(agent.id);
  }

  if (!loaded)
    return (
      <p role={error ? "alert" : "status"}>{error || "Loading task..."}</p>
    );

  return (
    <>
      <div className="breadcrumb">
        <button onClick={onHome}>oak</button>
        <ChevronRight />
        <button onClick={onTaskHome}>{task.name}</button>
        {agent && (
          <>
            <ChevronRight />
            <span>{agent.name}</span>
          </>
        )}
      </div>
      <div className="page-heading">
        <div className="min-w-0">
          <p className="eyebrow text-primary">
            {agent ? "AGENT TASK SURFACE" : "TASK SURFACE"}
          </p>
          <h1 className="break-words">
            {agent?.name || task.name}
            <span className="text-primary">_</span>
          </h1>
          <p
            className={`page-description whitespace-pre-wrap ${agent ? "" : "line-clamp-3"}`}
          >
            {agent
              ? "Discover the task, train its kernel, and run new queries."
              : task.objective}
          </p>
        </div>
        {agent ? (
          <AgentDialog
            initial={agent}
            connections={connections}
            tools={tools}
            trigger={<Button variant="outline">Edit configuration</Button>}
            onSave={async (configuration) =>
              onAgentUpdated(
                await api<Agent>(
                  user,
                  `${base}/agents/${agent.id}`,
                  "PATCH",
                  configuration,
                ),
              )
            }
          />
        ) : (
          <RenameTaskDialog
            name={task.name}
            onSave={async (name) =>
              onTaskUpdated(
                await api<Task>(user, base, "PATCH", {
                  name,
                  objective: task.objective,
                }),
              )
            }
          />
        )}
      </div>
      {error && (
        <p role="alert" className="error-panel mb-5">
          {error}
        </p>
      )}
      {agentId && !agent && (
        <p role="alert" className="error-panel mb-5">
          This agent is not part of this task.
        </p>
      )}
      {agent ? (
        <div className="space-y-8">
          <nav aria-label="Agent pages" className="flex gap-2 border-b pb-3">
            {(["discovery", "training", "inference"] as const).map((page) => (
              <Button
                key={page}
                variant={agentPage === page ? "secondary" : "ghost"}
                aria-current={agentPage === page ? "page" : undefined}
                onClick={() => onAgentPageChange(page)}
              >
                {page === "discovery"
                  ? "Discovery"
                  : page === "training"
                    ? "Training"
                    : "Inference"}
              </Button>
            ))}
          </nav>
          {agentPage === "inference" ? (
            <InferencePanel
              key={`${user}:${agent.id}`}
              user={user}
              taskId={task.id}
              agent={agent}
              tools={tools}
              connections={connections}
              runId={runId}
              onRunChange={onRunChange}
            />
          ) : agentPage === "training" ? (
            <TrainingPanel
              key={`${user}:${agent.id}`}
              user={user}
              taskId={task.id}
              agent={agent}
              tools={tools}
              connections={connections}
              runId={runId}
              onRunChange={onRunChange}
              onInference={() => onAgentPageChange("inference")}
            />
          ) : (
            <>
              <ModelConnectionPanel user={user} />
              <DiscoveryPanel
                key={`${user}:${agent.id}`}
                user={user}
                taskId={task.id}
                agent={agent}
                tools={tools}
              />
              <section aria-label="Saved task surface" className="space-y-4">
                <h2 className="section-title">Task surface</h2>
                {!agent.scope && (
                  <p className="text-xs text-muted-foreground">
                    This agent has saved responsibilities. Add context,
                    boundaries, and success criteria in Edit configuration.
                  </p>
                )}
                <TaskScopeView
                  scope={
                    agent.scope ?? {
                      responsibilities: agent.responsibilities,
                      context_and_rules: "",
                      boundaries: "",
                      success_criteria: "",
                    }
                  }
                />
              </section>
              <details className="border p-4">
                <summary className="text-sm">
                  Tool access settings · {agent.tool_ids?.length ?? 0} granted
                  tools
                </summary>
                <div className="mt-5">
                  <ToolCatalog
                    key={agent.id}
                    tools={tools}
                    connections={connections}
                    agent={agent}
                    onSave={async (tool_ids) =>
                      onAgentUpdated(
                        await api<Agent>(
                          user,
                          `${base}/agents/${agent.id}/tools`,
                          "PUT",
                          { tool_ids },
                        ),
                      )
                    }
                  />
                </div>
              </details>
            </>
          )}
        </div>
      ) : (
        <>
          <div className="stats-grid">
            <div>
              <Bot />
              <span>{String(agents.length).padStart(2, "0")}</span>
              <p>Agents</p>
            </div>
            <div>
              <Network />
              <span>{String(connections.length).padStart(2, "0")}</span>
              <p>MCP connections</p>
            </div>
            <div>
              <Layers />
              <span>
                {String(tools.filter((tool) => tool.available).length).padStart(
                  2,
                  "0",
                )}
              </span>
              <p>Available tools</p>
            </div>
          </div>
          <Tabs
            value={tab}
            onValueChange={(value) => onTabChange(value as TaskTab)}
          >
            <TabsList className="mb-7 w-full justify-start gap-6 rounded-none border-b bg-transparent p-0">
              <TabsTrigger value="scope" className="oak-tab">
                <FileText className="size-4" /> Scope
              </TabsTrigger>
              <TabsTrigger value="agents" className="oak-tab">
                <Bot className="size-4" />
                Agents <span className="tab-count">{agents.length}</span>
              </TabsTrigger>
              <TabsTrigger value="mcps" className="oak-tab">
                <Network className="size-4" />
                MCPs <span className="tab-count">{connections.length}</span>
              </TabsTrigger>
            </TabsList>
            <TabsContent value="scope">
              <p className="mb-6 flex items-center gap-2 text-xs text-muted-foreground">
                <LockKeyhole className="size-4" />
                This scope is read-only.
              </p>
              {!task.scope && (
                <p className="mb-6 text-sm text-muted-foreground">
                  This task contains an original objective. Additional scope
                  sections are unspecified.
                </p>
              )}
              <TaskScopeView objective={task.objective} scope={task.scope} />
            </TabsContent>
            <TabsContent value="agents">
              <AgentsPanel
                agents={agents}
                connections={connections}
                tools={tools}
                onCreate={createAgent}
                onOpen={onOpenAgent}
              />
            </TabsContent>
            <TabsContent value="mcps">
              <McpPanel
                connections={connections}
                tools={tools}
                actions={connectionActions}
              />
            </TabsContent>
          </Tabs>
        </>
      )}
    </>
  );
}

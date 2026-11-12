"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowUpRight,
  Bot,
  ChevronRight,
  Folder,
  Layers,
  LockKeyhole,
  Network,
  Plus,
  RefreshCw,
  Terminal,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ConfigurationDialog,
  ConnectionDialog,
  TokenDialog,
} from "./configuration-dialogs";
import { ToolCatalog } from "./tool-catalog";
import {
  api,
  type Agent,
  type Connection,
  type Task,
  type Tool,
  type User,
} from "@/lib/api";

type Navigate = (
  task?: string,
  agent?: string,
  tab?: string,
  user?: string,
) => void;

export function Workspace() {
  const params = useSearchParams();
  const router = useRouter();
  const user = params.get("user") === "demo-sam" ? "demo-sam" : "demo-alex";
  const navigate: Navigate = (task, agent, tab, identity = user) => {
    const query = new URLSearchParams({ user: identity });
    if (task) query.set("task", task);
    if (agent) query.set("agent", agent);
    if (tab) query.set("tab", tab);
    router.push(`/?${query.toString()}`);
  };
  return (
    <Session
      key={user}
      user={user}
      taskId={params.get("task")}
      agentId={params.get("agent")}
      tab={params.get("tab") || "agents"}
      navigate={navigate}
    />
  );
}

function Session({
  user,
  taskId,
  agentId,
  tab,
  navigate,
}: {
  user: string;
  taskId: string | null;
  agentId: string | null;
  tab: string;
  navigate: Navigate;
}) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    Promise.all([api<Task[]>(user, "/tasks"), api<User[]>(user, "/users")])
      .then(([tasks, users]) => {
        if (active) {
          setTasks(tasks);
          setUsers(users);
          setLoaded(true);
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [user]);
  const task = tasks.find((task) => task.id === taskId);
  async function createTask(name: string, objective: string) {
    const task = await api<Task>(user, "/tasks", "POST", { name, objective });
    setTasks((tasks) => [...tasks, task]);
    navigate(task.id);
  }
  return (
    <div className="oak-shell">
      <aside className="oak-sidebar">
        <button
          className="brand"
          onClick={() => navigate()}
          aria-label="Oak home"
        >
          <span className="brand-mark">
            <Terminal className="size-5" />
          </span>
          <span>
            oak<span className="ml-1 text-primary">_</span>
          </span>
          <Badge variant="outline" className="ml-auto text-[9px]">
            PREVIEW
          </Badge>
        </button>
        <div className="sidebar-section">
          <span className="eyebrow">Workspace</span>
          <span className="text-[10px] text-muted-foreground">01</span>
        </div>
        <nav
          aria-label="Tasks"
          className="min-h-0 flex-1 space-y-1 overflow-y-auto px-3"
        >
          {tasks.map((item) => (
            <div key={item.id}>
              <button
                className={`nav-row ${taskId === item.id && !agentId ? "nav-active" : ""}`}
                onClick={() => navigate(item.id)}
              >
                <Folder className="size-4 shrink-0" />
                <span className="truncate">{item.name}</span>
              </button>
              {taskId === item.id &&
                agents
                  .filter((a) => a.task_id === item.id)
                  .map((agent) => (
                    <button
                      key={agent.id}
                      className={`nav-row ml-4 w-[calc(100%-1rem)] text-xs ${agentId === agent.id ? "nav-active" : ""}`}
                      onClick={() => navigate(item.id, agent.id)}
                    >
                      <span className="text-muted-foreground">└</span>
                      <Bot className="size-3.5 shrink-0" />
                      <span className="truncate">{agent.name}</span>
                    </button>
                  ))}
            </div>
          ))}
          <ConfigurationDialog
            kind="task"
            onSave={createTask}
            trigger={
              <button className="nav-row mt-3 text-muted-foreground">
                <Plus className="size-4" />
                Create task
              </button>
            }
          />
        </nav>
        <div className="sidebar-footer">
          <div className="flex items-center gap-2 text-xs">
            <span className="status-dot status-online" />
            Configuration workspace
          </div>
          <p className="mt-2 text-[10px] leading-5 text-muted-foreground">
            Make implicit task relationships explicit.
          </p>
        </div>
      </aside>
      <div className="min-w-0 flex-1">
        <header className="topbar">
          <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
            <LockKeyhole className="size-3.5" />
            <span>PRIVATE PREVIEW</span>
          </div>
          <label className="flex flex-wrap items-center gap-3 text-[11px]">
            <span className="text-muted-foreground">DEMO USER</span>
            <select
              aria-label="Demo user"
              className="demo-select"
              value={user}
              onChange={(event) => {
                setAgents([]);
                navigate(undefined, undefined, undefined, event.target.value);
              }}
            >
              {(users.length ? users : [{ id: user, name: "Loading..." }]).map(
                (u) => (
                  <option key={u.id} value={u.id}>
                    {u.name}
                  </option>
                ),
              )}
            </select>
          </label>
        </header>
        <div className="preview-note">
          Demo identities show task access. Application sign-in is a
          placeholder.
        </div>
        <main className="main-content">
          {error && (
            <div role="alert" className="error-panel">
              {error}
              <Button
                variant="outline"
                className="ml-4"
                onClick={() => window.location.reload()}
              >
                Retry
              </Button>
            </div>
          )}
          {!loaded && !error && (
            <p role="status" className="text-sm text-muted-foreground">
              Loading workspace...
            </p>
          )}
          {loaded && task && (
            <TaskArea
              key={task.id}
              user={user}
              task={task}
              agentId={agentId}
              tab={tab}
              navigate={navigate}
              onAgents={setAgents}
              onTask={(updated) =>
                setTasks(
                  tasks.map((item) =>
                    item.id === updated.id ? updated : item,
                  ),
                )
              }
            />
          )}
          {loaded && !task && (
            <>
              <p className="breadcrumb">
                oak <ChevronRight /> workspace
              </p>
              <div className="page-heading">
                <div>
                  <p className="eyebrow text-primary">TASK CONTROL</p>
                  <h1>
                    Your tasks<span className="text-primary">.</span>
                  </h1>
                  <p className="page-description">
                    Define the objective. Connect tools. Give each agent
                    explicit access.
                  </p>
                </div>
                <ConfigurationDialog
                  kind="task"
                  onSave={createTask}
                  trigger={
                    <Button>
                      <Plus />
                      Create task
                    </Button>
                  }
                />
              </div>
              {taskId && (
                <p role="alert" className="error-panel mb-6">
                  This task is not available to the selected demo user.
                </p>
              )}
              {tasks.length === 0 ? (
                <div className="welcome-panel">
                  <div className="terminal-line">
                    $ oak task create
                    <span className="terminal-cursor" />
                  </div>
                  <h2 className="mt-7 text-xl">Start with one objective.</h2>
                  <p className="mt-3 max-w-md text-sm leading-7 text-muted-foreground">
                    A task contains its agents and a shared MCP tool catalog.
                    You decide which tools each agent can access.
                  </p>
                  <div className="mt-8 flex flex-wrap gap-4 text-[11px] text-muted-foreground">
                    <span>01 / DEFINE TASK</span>
                    <ChevronRight className="size-4" />
                    <span>02 / CONNECT MCPs</span>
                    <ChevronRight className="size-4" />
                    <span>03 / SELECT TOOLS</span>
                  </div>
                </div>
              ) : (
                <div className="border">
                  {tasks.map((task, i) => (
                    <button
                      key={task.id}
                      onClick={() => navigate(task.id)}
                      className="task-row"
                    >
                      <span className="text-xs text-muted-foreground">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <div className="min-w-0 flex-1 text-left">
                        <p className="font-medium">{task.name}</p>
                        <p className="mt-2 truncate text-xs text-muted-foreground">
                          {task.objective}
                        </p>
                      </div>
                      <ArrowUpRight className="size-4 text-muted-foreground" />
                    </button>
                  ))}
                </div>
              )}
              <p className="mt-8 text-[10px] text-muted-foreground">
                TASK → AGENTS → EACH AGENT&apos;S TASK SURFACE
              </p>
            </>
          )}
        </main>
      </div>
    </div>
  );
}

function TaskArea({
  user,
  task,
  agentId,
  tab,
  navigate,
  onAgents,
  onTask,
}: {
  user: string;
  task: Task;
  agentId: string | null;
  tab: string;
  navigate: Navigate;
  onAgents: (agents: Agent[]) => void;
  onTask: (task: Task) => void;
}) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const base = `/tasks/${task.id}`;
  const load = useCallback(async () => {
    const [agents, connections, tools] = await Promise.all([
      api<Agent[]>(user, `${base}/agents`),
      api<Connection[]>(user, `${base}/connections`),
      api<Tool[]>(user, `${base}/tools`),
    ]);
    return { agents, connections, tools };
  }, [base, user]);
  const apply = useCallback(
    (data: Awaited<ReturnType<typeof load>>) => {
      setAgents(data.agents);
      onAgents(data.agents);
      setConnections(data.connections);
      setTools(data.tools);
      setLoaded(true);
    },
    [onAgents],
  );
  useEffect(() => {
    let active = true;
    load()
      .then((data) => {
        if (active) apply(data);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [load, apply]);
  const pending = connections.some(
    (c) => c.status === "auth_required" || c.status === "connecting",
  );
  useEffect(() => {
    if (!pending) return;
    let active = true;
    const interval = setInterval(() => {
      load()
        .then((data) => {
          if (active) apply(data);
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    }, 2500);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [pending, load, apply]);
  const agent = agents.find((a) => a.id === agentId);
  async function reconnect(id: string) {
    setBusy(id);
    setError("");
    try {
      await api<Connection>(user, `${base}/connections/${id}/refresh`, "POST");
      apply(await load());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }
  function updateAgent(updated: Agent) {
    const next = agents.map((a) => (a.id === updated.id ? updated : a));
    setAgents(next);
    onAgents(next);
  }
  if (!loaded)
    return (
      <p role={error ? "alert" : "status"}>{error || "Loading task..."}</p>
    );
  return (
    <>
      <div className="breadcrumb">
        <button onClick={() => navigate()}>oak</button>
        <ChevronRight />
        <button onClick={() => navigate(task.id)}>{task.name}</button>
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
          <p className="page-description whitespace-pre-wrap">
            {agent?.responsibilities || task.objective}
          </p>
        </div>
        {agent ? (
          <ConfigurationDialog
            kind="agent"
            initial={{ name: agent.name, text: agent.responsibilities }}
            trigger={<Button variant="outline">Edit responsibilities</Button>}
            onSave={async (name, responsibilities) => {
              updateAgent(
                await api<Agent>(user, `${base}/agents/${agent.id}`, "PATCH", {
                  name,
                  responsibilities,
                }),
              );
            }}
          />
        ) : (
          <ConfigurationDialog
            kind="task"
            initial={{ name: task.name, text: task.objective }}
            trigger={<Button variant="outline">Edit task</Button>}
            onSave={async (name, objective) => {
              onTask(await api<Task>(user, base, "PATCH", { name, objective }));
            }}
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
        <ToolCatalog
          key={agent.id}
          tools={tools}
          connections={connections}
          agent={agent}
          onSave={async (tool_ids) => {
            updateAgent(
              await api<Agent>(
                user,
                `${base}/agents/${agent.id}/tools`,
                "PUT",
                { tool_ids },
              ),
            );
          }}
        />
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
                {String(tools.filter((t) => t.available).length).padStart(
                  2,
                  "0",
                )}
              </span>
              <p>Available tools</p>
            </div>
          </div>
          <Tabs
            value={tab === "mcps" ? "mcps" : "agents"}
            onValueChange={(value) => navigate(task.id, undefined, value)}
          >
            <TabsList className="mb-7 w-full justify-start gap-6 rounded-none border-b bg-transparent p-0">
              <TabsTrigger value="agents" className="oak-tab">
                <Bot className="size-4" />
                Agents <span className="tab-count">{agents.length}</span>
              </TabsTrigger>
              <TabsTrigger value="mcps" className="oak-tab">
                <Network className="size-4" />
                MCPs <span className="tab-count">{connections.length}</span>
              </TabsTrigger>
            </TabsList>
            <TabsContent value="agents">
              <div className="mb-5 flex items-center justify-between gap-4">
                <div>
                  <h2 className="section-title">Agents</h2>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Each agent has its own responsibilities and tool access.
                  </p>
                </div>
                <ConfigurationDialog
                  kind="agent"
                  trigger={
                    <Button>
                      <Plus />
                      Add agent
                    </Button>
                  }
                  onSave={async (name, responsibilities) => {
                    const a = await api<Agent>(user, `${base}/agents`, "POST", {
                      name,
                      responsibilities,
                    });
                    apply(await load());
                    navigate(task.id, a.id);
                  }}
                />
              </div>
              {agents.length === 0 ? (
                <div className="empty-state">
                  <Bot className="mb-4 size-6 text-muted-foreground" />
                  <p>No agents in this task.</p>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Add an agent and define its responsibilities.
                  </p>
                </div>
              ) : (
                <div className="border">
                  {agents.map((a, index) => (
                    <button
                      key={a.id}
                      className="task-row"
                      onClick={() => navigate(task.id, a.id)}
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
            </TabsContent>
            <TabsContent value="mcps">
              <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="section-title">MCP connections</h2>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Connect a server to discover its tools.
                  </p>
                </div>
                <ConnectionDialog
                  onSave={async (body) => {
                    const c = await api<Connection>(
                      user,
                      `${base}/connections`,
                      "POST",
                      body,
                    );
                    await reconnect(c.id);
                  }}
                />
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
                {connections.map((c) => (
                  <article
                    key={c.id}
                    aria-label={`MCP ${c.name}`}
                    className="border bg-card p-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-3">
                          <h3 className="text-sm">{c.name}</h3>
                          <span
                            className={`status-label ${c.status === "connected" ? "text-primary" : "text-muted-foreground"}`}
                          >
                            <span
                              className={`status-dot ${c.status === "connected" ? "status-online" : ""}`}
                            />
                            {c.status.replaceAll("_", " ")}
                          </span>
                        </div>
                        <p className="mt-2 break-all text-[11px] text-muted-foreground">
                          {c.url}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {c.auth_url && (
                          <Button asChild size="sm">
                            <a
                              href={c.auth_url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              Authorize
                              <ArrowUpRight />
                            </a>
                          </Button>
                        )}
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={
                            busy === c.id ||
                            ["connecting", "auth_required"].includes(c.status)
                          }
                          onClick={() => reconnect(c.id)}
                        >
                          <RefreshCw
                            className={busy === c.id ? "animate-spin" : ""}
                          />
                          {busy === c.id ? "Connecting..." : "Refresh tools"}
                        </Button>
                        {c.auth_mode === "token" &&
                          !["connecting", "auth_required"].includes(
                            c.status,
                          ) && (
                            <TokenDialog
                              onSave={async (token) => {
                                await api(
                                  user,
                                  `${base}/connections/${c.id}/token`,
                                  "PUT",
                                  { token },
                                );
                                await reconnect(c.id);
                              }}
                            />
                          )}
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={
                            busy === c.id ||
                            ["connecting", "auth_required"].includes(c.status)
                          }
                          onClick={async () => {
                            if (
                              !window.confirm(
                                `Remove ${c.name}? Its tools will be removed from all agents in this task.`,
                              )
                            )
                              return;
                            try {
                              await api(
                                user,
                                `${base}/connections/${c.id}`,
                                "DELETE",
                              );
                              apply(await load());
                            } catch (e) {
                              setError((e as Error).message);
                            }
                          }}
                        >
                          Remove
                        </Button>
                      </div>
                    </div>
                    {c.error && (
                      <p className="error-text mt-3" role="alert">
                        {c.error}
                      </p>
                    )}
                  </article>
                ))}
              </div>
              <ToolCatalog tools={tools} connections={connections} />
            </TabsContent>
          </Tabs>
        </>
      )}
    </>
  );
}

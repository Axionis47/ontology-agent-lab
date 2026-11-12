import type { ReactNode } from "react";
import { Bot, Folder, LockKeyhole, Plus, Terminal } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { Task, User, Agent } from "@/lib/api";
import type { WorkspaceNavigation } from "./use-workspace-navigation";

export function WorkspaceShell({
  navigation,
  tasks,
  users,
  agents,
  savingTask,
  children,
}: {
  navigation: WorkspaceNavigation;
  tasks: Task[];
  users: User[];
  agents: Agent[];
  savingTask: boolean;
  children: ReactNode;
}) {
  const { user, taskId, agentId, navigate } = navigation;
  return (
    <div className="oak-shell">
      <aside className="oak-sidebar" inert={savingTask}>
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
                onClick={() => navigate({ taskId: item.id })}
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
                      onClick={() =>
                        navigate({ taskId: item.id, agentId: agent.id })
                      }
                    >
                      <span className="text-muted-foreground">└</span>
                      <Bot className="size-3.5 shrink-0" />
                      <span className="truncate">{agent.name}</span>
                    </button>
                  ))}
            </div>
          ))}
          <button
            className="nav-row mt-3 text-muted-foreground"
            onClick={() => navigate({ view: "create-task" })}
          >
            <Plus className="size-4" />
            Create task
          </button>
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
        <header className="topbar" inert={savingTask}>
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
              onChange={(event) => navigate({ user: event.target.value })}
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
        <main className="main-content">{children}</main>
      </div>
    </div>
  );
}

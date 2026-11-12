import { ArrowUpRight, ChevronRight, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Task } from "@/lib/api";

export function TasksHome({
  tasks,
  unavailable,
  onCreate,
  onOpen,
}: {
  tasks: Task[];
  unavailable: boolean;
  onCreate: () => void;
  onOpen: (id: string) => void;
}) {
  return (
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
            Define the task scope. Connect tools. Give each agent explicit
            access.
          </p>
        </div>
        <Button onClick={onCreate}>
          <Plus />
          Create task
        </Button>
      </div>
      {unavailable && (
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
          <h2 className="mt-7 text-xl">
            Define the work your task must support.
          </h2>
          <p className="mt-3 max-w-md text-sm leading-7 text-muted-foreground">
            A task contains its agents and a shared MCP tool catalog. You decide
            which tools each agent can access.
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
              onClick={() => onOpen(task.id)}
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
  );
}

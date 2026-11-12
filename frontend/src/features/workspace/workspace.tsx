"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  api,
  type Agent,
  type Task,
  type TaskInput,
  type User,
} from "@/lib/api";
import { TaskScopeForm } from "@/features/tasks/scope/task-scope-form";
import { TaskArea } from "@/features/tasks/task-area";
import { TasksHome } from "@/features/tasks/tasks-home";
import { WorkspaceShell } from "./workspace-shell";
import {
  useWorkspaceNavigation,
  type WorkspaceNavigation,
} from "./use-workspace-navigation";

export function Workspace() {
  const navigation = useWorkspaceNavigation();
  return <Session key={navigation.user} navigation={navigation} />;
}

function Session({ navigation }: { navigation: WorkspaceNavigation }) {
  const { user, taskId, agentId, tab, agentPage, runId, creating, navigate } =
    navigation;
  const [tasks, setTasks] = useState<Task[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [savingTask, setSavingTask] = useState(false);

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

  const replaceTaskAgents = useCallback((taskId: string, next: Agent[]) => {
    setAgents((current) => [
      ...current.filter((a) => a.task_id !== taskId),
      ...next,
    ]);
  }, []);

  async function createTask(input: TaskInput) {
    setSavingTask(true);
    try {
      const task = await api<Task>(user, "/tasks", "POST", input);
      setTasks((tasks) => [...tasks, task]);
      navigate({ taskId: task.id, tab: "scope" });
    } finally {
      setSavingTask(false);
    }
  }

  const task = tasks.find((task) => task.id === taskId);
  return (
    <WorkspaceShell
      navigation={navigation}
      tasks={tasks}
      users={users}
      agents={agents}
      savingTask={savingTask}
    >
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
      {loaded && creating && (
        <TaskScopeForm
          user={user}
          onSave={createTask}
          onCancel={() => navigate()}
        />
      )}
      {loaded && !creating && task && (
        <TaskArea
          key={task.id}
          user={user}
          task={task}
          agentId={agentId}
          tab={tab}
          agentPage={agentPage}
          runId={runId}
          agents={agents.filter((agent) => agent.task_id === task.id)}
          onAgentsLoaded={replaceTaskAgents}
          onAgentCreated={(agent) =>
            setAgents((current) => [...current, agent])
          }
          onAgentUpdated={(agent) =>
            setAgents((current) =>
              current.map((item) => (item.id === agent.id ? agent : item)),
            )
          }
          onTaskUpdated={(task) =>
            setTasks((current) =>
              current.map((item) => (item.id === task.id ? task : item)),
            )
          }
          onHome={() => navigate()}
          onTaskHome={() => navigate({ taskId: task.id })}
          onOpenAgent={(agentId) => navigate({ taskId: task.id, agentId })}
          onTabChange={(tab) => navigate({ taskId: task.id, tab })}
          onAgentPageChange={(agentPage) =>
            navigate({
              taskId: task.id,
              agentId: agentId ?? undefined,
              agentPage,
            })
          }
          onRunChange={(runId) =>
            navigate({
              taskId: task.id,
              agentId: agentId ?? undefined,
              agentPage: agentPage === "inference" ? "inference" : "training",
              runId,
            })
          }
        />
      )}
      {loaded && !creating && !task && (
        <TasksHome
          tasks={tasks}
          unavailable={Boolean(taskId)}
          onCreate={() => navigate({ view: "create-task" })}
          onOpen={(taskId) => navigate({ taskId })}
        />
      )}
    </WorkspaceShell>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type Agent, type Connection, type Tool } from "@/lib/api";

export function useTaskData(
  user: string,
  taskId: string,
  onAgentsLoaded: (taskId: string, agents: Agent[]) => void,
) {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const base = `/tasks/${taskId}`;
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
      onAgentsLoaded(taskId, data.agents);
      setConnections(data.connections);
      setTools(data.tools);
      setLoaded(true);
    },
    [onAgentsLoaded, taskId],
  );
  const pending = connections.some(
    (c) => c.status === "auth_required" || c.status === "connecting",
  );
  useEffect(() => {
    let active = true;
    const refresh = () => {
      load()
        .then((data) => {
          if (active) apply(data);
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    };
    if (!loaded) refresh();
    const interval = pending ? setInterval(refresh, 2500) : undefined;
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [loaded, pending, load, apply]);
  const reload = useCallback(async () => {
    apply(await load());
  }, [apply, load]);
  const reportError = useCallback((message: string) => setError(message), []);
  return { connections, tools, loaded, error, reload, reportError };
}

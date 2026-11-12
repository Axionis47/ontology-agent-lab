"use client";

import { useRouter, useSearchParams } from "next/navigation";
import type { TaskTab } from "@/features/tasks/task-area";

type Destination = {
  taskId?: string;
  agentId?: string;
  tab?: TaskTab;
  user?: string;
  view?: "create-task";
  agentPage?: "discovery" | "training" | "inference";
  runId?: string;
};

export function useWorkspaceNavigation() {
  const params = useSearchParams();
  const router = useRouter();
  const user = params.get("user") === "demo-sam" ? "demo-sam" : "demo-alex";
  const tabParam = params.get("tab");
  const tab: TaskTab =
    tabParam === "agents" || tabParam === "mcps" ? tabParam : "scope";

  function navigate(destination: Destination = {}) {
    const query = new URLSearchParams({ user: destination.user ?? user });
    if (destination.taskId) query.set("task", destination.taskId);
    if (destination.agentId) query.set("agent", destination.agentId);
    if (destination.tab) query.set("tab", destination.tab);
    if (destination.view) query.set("view", destination.view);
    if (destination.agentPage && destination.agentPage !== "discovery")
      query.set("page", destination.agentPage);
    if (destination.runId) query.set("run", destination.runId);
    router.push(`/?${query.toString()}`);
  }

  return {
    user,
    taskId: params.get("task"),
    agentId: params.get("agent"),
    tab,
    agentPage:
      params.get("page") === "inference"
        ? ("inference" as const)
        : params.get("page") === "training"
          ? ("training" as const)
          : ("discovery" as const),
    runId: params.get("run"),
    creating: params.get("view") === "create-task",
    navigate,
  };
}

export type WorkspaceNavigation = ReturnType<typeof useWorkspaceNavigation>;

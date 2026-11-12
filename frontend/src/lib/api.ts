import type { components } from "./api-types";

export type Task = components["schemas"]["Task"];
export type TaskInput = components["schemas"]["TaskInput"];
export type TaskScope = components["schemas"]["TaskScope"];
export type ScopeExample = components["schemas"]["ScopeExample"];
export type Agent = components["schemas"]["Agent"];
export type AgentInput = components["schemas"]["AgentInput"];
export type Connection = components["schemas"]["Connection"];
export type Tool = components["schemas"]["Tool"];
export type User = components["schemas"]["User"];
export type ConnectionInput = components["schemas"]["ConnectionInput"];
export type ModelRuntime = components["schemas"]["ModelRuntime"];
export type DiscoveryOverview = components["schemas"]["DiscoveryOverview"];
export type DiscoveryDetail = components["schemas"]["DiscoveryDetail"];
export type DiscoveryRun = components["schemas"]["DiscoveryRun"];
export type DiscoveryLimits = components["schemas"]["DiscoveryLimits-Input"];
export type EvidenceRef = components["schemas"]["EvidenceRef"];
export type TrainingCase = components["schemas"]["TrainingCase"];
export type TrainingCaseInput = components["schemas"]["TrainingCaseInput"];
export type TrainingLimits = Required<
  components["schemas"]["TrainingLimits-Input"]
>;
export type TrainingOverview = components["schemas"]["TrainingOverview"];
export type TrainingDetail = components["schemas"]["TrainingDetail"];
export type TrainingEpisode = components["schemas"]["TrainingEpisode"];
export type TrainingEvent = components["schemas"]["TrainingEvent"];

export async function api<T>(
  user: string,
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers: { "Content-Type": "application/json", "X-Oak-User": user },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => ({}));
    throw new Error(
      typeof problem.detail === "string"
        ? problem.detail
        : "Check the form and try again.",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

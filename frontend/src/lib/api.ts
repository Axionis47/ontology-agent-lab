import type { components } from "./api-types";

export type Task = components["schemas"]["Task"];
export type Agent = components["schemas"]["Agent"];
export type Connection = components["schemas"]["Connection"];
export type Tool = components["schemas"]["Tool"];
export type User = components["schemas"]["User"];
export type ConnectionInput = components["schemas"]["ConnectionInput"];

export async function api<T>(
  user: string,
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers: { "Content-Type": "application/json", "X-Oak-User": user },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
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

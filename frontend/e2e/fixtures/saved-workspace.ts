import { expect, type Page } from "@playwright/test";
import type { DiscoveryDetail } from "../../src/lib/api";

export async function mockWorkspace(
  page: Page,
  detail: DiscoveryDetail,
  toolCount = 2,
) {
  const scope = {
    responsibilities: "Inspect saved records.",
    context_and_rules: "Use saved evidence.",
    boundaries: "Do not change source records.",
    success_criteria: "Show explicit links.",
    examples: [],
  };
  const task = {
    id: "fixture-task",
    name: "Saved fixtures",
    objective: "Inspect saved records.",
    scope,
    created_at: detail.run.created_at,
    agent_count: 1,
    connection_count: 2,
    tool_count: toolCount,
  };
  let agent = {
    id: "fixture-agent",
    task_id: task.id,
    name: "Fixture agent",
    responsibilities: scope.responsibilities,
    scope,
    tool_ids: ["tool-0"],
    created_at: detail.run.created_at,
  };
  const connections = ["server-a", "server-b"].map((id) => ({
    id,
    task_id: task.id,
    name: id === "server-a" ? "Records / primary" : "Records / secondary",
    url: "https://example.invalid/mcp",
    status: "connected",
    auth_mode: "none",
    error: null,
    auth_url: null,
    created_at: detail.run.created_at,
  }));
  const tools = Array.from({ length: toolCount }, (_, i) => ({
    id: `tool-${i}`,
    connection_id: connections[i % 2].id,
    connection_name: connections[i % 2].name,
    name: i < 2 ? "duplicate_name" : `tool_${i}`,
    description: `Description for tool ${i}. `.repeat(12),
    available: i !== 4,
    input_schema: { type: "object", properties: { query: { type: "string" } } },
  }));
  const writes: { path: string; body: unknown }[] = [];
  const unexpected: string[] = [];
  let polls = 0;
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() !== "GET") {
      writes.push({ path, body: request.postDataJSON() });
      if (path.endsWith("/agents/fixture-agent/tools"))
        agent = { ...agent, tool_ids: request.postDataJSON().tool_ids };
      else if (
        path.endsWith("/agents/fixture-agent") &&
        request.method() === "PATCH"
      )
        agent = { ...agent, ...request.postDataJSON() };
      else {
        unexpected.push(`${request.method()} ${path}`);
        return route.fulfill({
          status: 400,
          json: { detail: "No calls are permitted for saved fixtures." },
        });
      }
      return route.fulfill({ json: agent });
    }
    const responses: Record<string, unknown> = {
      "/api/tasks": [task],
      "/api/users": [{ id: "demo-alex", name: "Alex" }],
      "/api/model-runtime": {
        status: "not_configured",
        remaining_usd: 1,
        budget_usd: 1,
        can_check: false,
        model: null,
        provider: null,
        last_check: null,
      },
      "/api/tasks/fixture-task/agents": [agent],
      "/api/tasks/fixture-task/connections": connections,
      "/api/tasks/fixture-task/tools": tools,
      "/api/tasks/fixture-task/agents/fixture-agent/discovery": {
        ready: false,
        blocked_reason: "Saved fixtures only.",
        ceilings: detail.run.limits,
        runs: [detail.run],
        has_more: false,
      },
      "/api/tasks/fixture-task/agents/fixture-agent/discovery/runs/saved-run":
        detail,
    };
    if (path.endsWith("/runs/saved-run")) polls++;
    if (!(path in responses)) {
      unexpected.push(`GET ${path}`);
      return route.fulfill({
        status: 404,
        json: { detail: "Unknown fixture route." },
      });
    }
    return route.fulfill({ json: responses[path] });
  });
  return {
    writes,
    unexpected,
    tools,
    polls: () => polls,
    agent: () => agent,
    open: async () => {
      await page.goto("/?task=fixture-task&agent=fixture-agent");
      await expect(
        page.getByRole("region", { name: "Discovery", exact: true }),
      ).toBeVisible();
    },
  };
}

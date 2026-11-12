import { randomUUID } from "node:crypto";
import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import type {
  Agent,
  DiscoveryDetail,
  Task,
  Tool,
  TrainingDetail,
} from "../src/lib/api";
import { domains, savedDiscovery } from "./fixtures/saved-discovery";
import { mockWorkspace } from "./fixtures/saved-workspace";

const headers = { Origin: "http://localhost:3047" };
const writeQuery =
  "Create a note named Training note and report its identifier.";
const readQuery = "Read the initial note and report its identifier.";

async function setup(request: APIRequestContext) {
  await request.post("http://127.0.0.1:9147/probe-reset");
  await request.post("http://127.0.0.1:8047/test-discovery?mode=success");
  await request.post("http://127.0.0.1:8047/test-training?mode=success");
  const task: Task = await (
    await request.post("/api/tasks", {
      headers,
      data: {
        name: "Training acceptance",
        objective: "Inspect notes and create test notes. Do not delete notes.",
      },
    })
  ).json();
  const base = `/api/tasks/${task.id}`;
  const connection = await (
    await request.post(`${base}/connections`, {
      headers,
      data: {
        name: "Training test world",
        url: "http://127.0.0.1:9147/discovery/mcp",
      },
    })
  ).json();
  await request.post(`${base}/connections/${connection.id}/refresh`, {
    headers,
  });
  const tools: Tool[] = await (await request.get(`${base}/tools`)).json();
  const toolIds = tools
    .filter((tool) => ["list_notes", "create_note"].includes(tool.name))
    .map((tool) => tool.id);
  const agent: Agent = await (
    await request.post(`${base}/agents`, {
      headers,
      data: {
        name: "Note agent",
        responsibilities:
          "Inspect notes and create only test notes. Do not delete notes.",
        tool_ids: toolIds,
      },
    })
  ).json();
  const agentBase = `${base}/agents/${agent.id}`;
  const discovery = `${agentBase}/discovery`;
  let detail: DiscoveryDetail = await (
    await request.post(`${discovery}/runs`, {
      headers,
      data: {
        request_id: randomUUID(),
        environment: "Controlled training fixture",
        limits: { cost_usd: "1" },
      },
    })
  ).json();
  const discoveryRun = `${discovery}/runs/${detail.run.id}`;
  await expect
    .poll(
      async () => {
        detail = await (await request.get(discoveryRun)).json();
        return detail.run.status;
      },
      { timeout: 30_000 },
    )
    .toBe("paused");
  const resumed = await request.post(`${discoveryRun}/resume`, {
    headers,
    data: {
      request_id: randomUUID(),
      expected_revision: detail.run.revision,
      answers: Object.fromEntries(
        detail.questions.map((question) => [question.id, "Billing contact"]),
      ),
    },
  });
  expect(resumed.ok()).toBeTruthy();
  await expect
    .poll(
      async () => (await (await request.get(discoveryRun)).json()).run.status,
      { timeout: 30_000 },
    )
    .toBe("completed");
  return {
    url: `/?task=${task.id}&agent=${agent.id}&page=training`,
    api: `${agentBase}/training`,
    toolIds,
  };
}

async function calls(request: APIRequestContext) {
  return (
    await (await request.get("http://127.0.0.1:8047/test-training")).json()
  ).calls;
}

async function addCase(page: Page, query: string) {
  await page
    .getByRole("button", { name: "Add test case", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Add test case" });
  await dialog.getByRole("textbox", { name: "Query", exact: true }).fill(query);
  await dialog
    .getByRole("textbox", { name: "Task success", exact: true })
    .fill(
      "The requested note exists and the final answer gives its identifier.",
    );
  await dialog
    .getByRole("checkbox", {
      name: "Training test world:list_notes",
      exact: true,
    })
    .check();
  await dialog
    .getByRole("checkbox", {
      name: "Training test world:create_note",
      exact: true,
    })
    .check();
  await dialog
    .getByRole("button", { name: "Save test case", exact: true })
    .click();
  await expect(dialog).toBeHidden();
}

async function start(page: Page) {
  const form = page.getByRole("form", { name: "Start training" });
  await form
    .getByLabel("Prepared environment reference", { exact: true })
    .fill("Controlled fixture");
  await form.getByLabel("Maximum model cost (USD)", { exact: true }).fill("1");
  await form.getByLabel("Maximum model calls", { exact: true }).fill("100");
  await form
    .getByRole("button", { name: "Start training", exact: true })
    .click();
  await expect(page).toHaveURL(/run=/);
  return new URL(page.url()).searchParams.get("run")!;
}

test("saved cases train with actual read and write evidence, then fixed inference", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  const data = await setup(request);
  const before = await calls(request);
  await page.goto(data.url);
  const panel = page.getByRole("region", { name: "Training", exact: true });
  await expect(
    page
      .getByRole("navigation", { name: "Agent pages" })
      .getByRole("button", { name: "Training", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  await addCase(page, writeQuery);
  await addCase(page, readQuery);
  const readCase = panel.getByRole("article", {
    name: `Test case: ${readQuery}`,
    exact: true,
  });
  await readCase
    .getByRole("button", { name: "Edit test case", exact: true })
    .click();
  const edit = page.getByRole("dialog", {
    name: "Edit test case",
    exact: true,
  });
  await edit
    .getByRole("textbox", { name: "Task success", exact: true })
    .fill("The answer gives the identifier of the initial note.");
  await edit
    .getByRole("button", { name: "Save test case", exact: true })
    .click();
  await expect(edit).toBeHidden();
  await addCase(page, "Temporary case");
  await panel
    .getByRole("article", { name: "Test case: Temporary case", exact: true })
    .getByRole("button", { name: "Delete test case", exact: true })
    .click();
  await page
    .getByRole("dialog", { name: "Delete test case", exact: true })
    .getByRole("button", { name: "Delete test case", exact: true })
    .click();
  await expect(
    panel.getByRole("article", {
      name: "Test case: Temporary case",
      exact: true,
    }),
  ).toHaveCount(0);
  await page.reload();
  await expect(
    panel.getByRole("region", { name: "Test cases", exact: true }),
  ).toContainText(readQuery);
  expect(await calls(request)).toBe(before);
  const runId = await start(page);
  const results = panel.getByRole("region", {
    name: "Run results",
    exact: true,
  });
  await expect(results.getByRole("status")).toHaveText("completed", {
    timeout: 45_000,
  });
  await expect(
    panel.getByRole("region", { name: "Accepted version", exact: true }),
  ).toBeVisible();
  const detail: TrainingDetail = await (
    await request.get(`${data.api}/runs/${runId}`)
  ).json();
  expect(detail.episodes).toHaveLength(4);
  expect(detail.episodes.map((episode) => episode.evaluation?.status)).toEqual([
    "passed",
    "passed",
    "passed",
    "passed",
  ]);
  const writeResult = results.getByRole("article", {
    name: `Case result: ${writeQuery}`,
    exact: true,
  });
  await writeResult
    .getByRole("button", { name: "Inspect harness trace", exact: true })
    .click();
  const inspection = results.getByRole("region", {
    name: "Episode inspection",
    exact: true,
  });
  await expect(
    inspection.getByRole("region", { name: "Tool observations", exact: true }),
  ).toContainText("succeeded");
  const access = inspection.getByRole("region", {
    name: "Evidence access and context",
  });
  await expect(access).toBeVisible();
  await access
    .getByText("Evidence reads and context budgets", { exact: true })
    .click();
  await expect(access).toContainText("context_usage");
  await access
    .getByText("Acquisition needs and checks", { exact: true })
    .click();
  await expect(access).toContainText("source_access");
  await expect(
    inspection.getByRole("region", {
      name: "Function executions",
      exact: true,
    }),
  ).toContainText("observed_notes");
  const graph = inspection.getByRole("region", {
    name: "Observed graph",
    exact: true,
  });
  await graph.getByText("Record note-2", { exact: true }).click();
  await expect(graph).toContainText("Training note");
  const previousCalls = await calls(request);
  await page.reload();
  await expect(results.getByRole("status")).toHaveText("completed");
  expect(new URL(page.url()).searchParams.get("run")).toBe(runId);
  expect(await calls(request)).toBe(previousCalls);
  const savedCase = panel.getByRole("article", {
    name: `Test case: ${writeQuery}`,
    exact: true,
  });
  await savedCase
    .getByRole("button", { name: "Edit test case", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("textbox", { name: "Task success", exact: true })
    .fill("A revised success description for future runs.");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Save test case", exact: true })
    .click();
  const retained: TrainingDetail = await (
    await request.get(`${data.api}/runs/${runId}`)
  ).json();
  expect(retained.run.cases).toEqual(detail.run.cases);
  expect(await calls(request)).toBe(previousCalls);
  const lastEvent = detail.events.at(-1)!.sequence;
  expect(
    await (
      await request.get(`${data.api}/runs/${runId}/events?after=${lastEvent}`)
    ).json(),
  ).toEqual([]);

  await panel
    .getByRole("button", { name: "Try a new query", exact: true })
    .click();
  const dialog = page.getByRole("region", { name: "Inference", exact: true });
  await expect(page).toHaveURL(/page=inference/);
  await dialog
    .getByRole("textbox", { name: "Query", exact: true })
    .fill("Create a note named Inference note and report its identifier.");
  await dialog
    .getByText("Run limits · Set a cost limit before running", { exact: true })
    .click();
  await dialog
    .getByLabel("Maximum model cost (USD)", { exact: true })
    .fill("1");
  await dialog
    .getByRole("button", { name: "Run inference", exact: true })
    .click();
  await expect(dialog.getByLabel("Inference status")).toHaveText("completed", {
    timeout: 30_000,
  });
  await expect(
    dialog.getByRole("region", { name: "Final answer" }),
  ).toContainText("Inference note");
  const inferenceId = new URL(page.url()).searchParams.get("run")!;
  expect(inferenceId).not.toBe(runId);
  const inference: TrainingDetail = await (
    await request.get(`${data.api}/runs/${inferenceId}`)
  ).json();
  expect(inference.run.accepted_candidate_id).toBe(
    detail.run.accepted_candidate_id,
  );
  expect(inference.episodes[0].result.function_ids).toContain("observed_notes");
  expect(inference.candidates.map((candidate) => candidate.id)).toEqual([
    detail.run.accepted_candidate_id,
  ]);
  await page.goto(`${data.url}&run=${runId}`);
  await expect(results.getByRole("status")).toHaveText("completed");
  await page.screenshot({
    path: "test-results/training-completed-full.png",
    fullPage: true,
  });
  await panel.screenshot({ path: "test-results/training-desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() => panel.evaluate((node) => node.scrollWidth <= node.clientWidth))
    .toBe(true);
  await panel.screenshot({ path: "test-results/training-mobile.png" });
});

test("a targeted repair preserves versions and exposes its real diff", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  const data = await setup(request);
  await request.post("http://127.0.0.1:8047/test-training?mode=repair");
  await request.post(`${data.api}/cases`, {
    headers,
    data: {
      query: writeQuery,
      tool_ids: data.toolIds,
      task_success: "The requested note exists and its identifier is returned.",
    },
  });
  await page.goto(data.url);
  const runId = await start(page);
  const results = page.getByRole("region", {
    name: "Run results",
    exact: true,
  });
  await expect(results.getByRole("status")).toHaveText("completed", {
    timeout: 45_000,
  });
  const detail: TrainingDetail = await (
    await request.get(`${data.api}/runs/${runId}`)
  ).json();
  expect(detail.candidates).toHaveLength(2);
  expect(detail.candidates[1].status).toBe("accepted");
  const history = results.getByRole("region", {
    name: "Change history",
    exact: true,
  });
  await expect(history).toContainText("Repair review");
  await expect(history).toContainText("Proposed cause:");
  await expect(history).toContainText("recorded input replay");
  const catalog = results.getByRole("region", {
    name: "Definition catalog",
    exact: true,
  });
  await expect(catalog).toContainText("functions / observed_notes");
  await catalog
    .getByText("functions / observed_notes", { exact: true })
    .click();
  await expect(catalog).toContainText("Recorded use:");
  await catalog
    .getByRole("link", { name: /^Evidence/ })
    .first()
    .click();
  await expect(page).toHaveURL(/#record-/);
  await page.reload();
  await expect(history).toContainText("recorded input replay");
  await expect(catalog).toContainText(detail.candidates[1].digest);

  await results.getByRole("button", { name: /Targeted repair/ }).click();
  const candidate = results.getByRole("region", {
    name: "Candidate inspection",
    exact: true,
  });
  await expect(candidate).toContainText("Exact before and after changes");
  await expect(candidate).toContainText('"name": "id"');
  await expect(candidate).toContainText('"name": "title"');
  await results
    .getByRole("combobox", { name: "Harness round", exact: true })
    .selectOption("1");
  await expect(results.getByRole("article").first()).toContainText("failed");
  await results
    .getByRole("combobox", { name: "Harness round", exact: true })
    .selectOption("2");
  await expect(results.getByRole("article").first()).not.toContainText(
    "failed",
  );
  await results.getByRole("button", { name: /Initial construction/ }).click();
  await expect(candidate).toContainText(detail.candidates[0].id);
});

test("stop preserves the selected run and reload does not resume it", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  const data = await setup(request);
  await request.post(
    "http://127.0.0.1:8047/test-training?mode=success&delay=1",
  );
  await request.post(`${data.api}/cases`, {
    headers,
    data: {
      query: writeQuery,
      tool_ids: data.toolIds,
      task_success: "The requested note exists and its identifier is returned.",
    },
  });
  await page.goto(data.url);
  await start(page);
  await page.getByRole("button", { name: "Stop run", exact: true }).click();
  const results = page.getByRole("region", {
    name: "Run results",
    exact: true,
  });
  await expect(results.getByRole("status")).toHaveText("stopped");
  const stoppedCalls = await calls(request);
  await page.reload();
  await expect(results.getByRole("status")).toHaveText("stopped");
  expect(await calls(request)).toBe(stoppedCalls);
  await page.goto(`${data.url}&run=${randomUUID()}`);
  await expect(
    page
      .getByRole("region", { name: "Training", exact: true })
      .getByRole("alert"),
  ).toContainText("Training run not found");
  await expect(results).toHaveCount(0);
  expect(await calls(request)).toBe(stoppedCalls);
});

test("saved history keeps every loaded run when polling receives a newer run", async ({
  page,
}) => {
  const fixture = await mockWorkspace(page, savedDiscovery(domains.empty));
  const base = "/api/tasks/fixture-task/agents/fixture-agent/training";
  const seed: TrainingDetail["run"] = {
    id: "run-0",
    task_id: "fixture-task",
    agent_id: "fixture-agent",
    mode: "training",
    status: "completed",
    stage: "finished",
    message: "Saved fixture",
    discovery_run_id: null,
    input_digest: "a".repeat(64),
    cases: [],
    limits: {
      cost_usd: "1",
      model_calls: 40,
      mcp_calls: 30,
      max_steps: 12,
      max_rounds: 3,
      active_seconds: 600,
    },
    environment_ref: null,
    evaluator_version: "fixture",
    accepted_candidate_id: null,
    model_calls: 0,
    mcp_calls: 0,
    accounted_usd: 0,
    created_at: "2026-11-09T12:00:00Z",
    updated_at: "2026-11-09T12:00:00Z",
  };
  const runs = Array.from({ length: 65 }, (_, index) => ({
    ...seed,
    id: `run-${index}`,
    created_at: new Date(
      Date.parse(seed.created_at) - index * 1000,
    ).toISOString(),
  }));
  let newest = false;
  const offsets: number[] = [];
  await page.route("**/training**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === base) {
      const offset = Number(url.searchParams.get("offset") ?? 0);
      offsets.push(offset);
      const current = newest ? [{ ...seed, id: "new-run" }, ...runs] : runs;
      await route.fulfill({
        json: {
          cases: [],
          runs: current.slice(offset, offset + 30),
          has_more: current.length > offset + 30,
          accepted_candidate: null,
          ready: false,
          message: "Saved records only.",
        },
      });
    } else {
      const id = url.pathname.split("/").at(-1);
      await route.fulfill({
        json: {
          run: runs.find((run) => run.id === id) ?? seed,
          episodes: [],
          candidates: [],
          events: [],
        },
      });
    }
  });
  await page.goto(
    "/?task=fixture-task&agent=fixture-agent&page=training&run=run-0",
  );
  const history = page.getByRole("region", { name: "Saved runs", exact: true });
  await history
    .getByRole("button", { name: "Load older runs", exact: true })
    .click();
  await expect(history.getByRole("heading")).toHaveText("Saved runs (60+)");
  newest = true;
  await expect(history.getByRole("heading")).toHaveText("Saved runs (61+)", {
    timeout: 10_000,
  });
  await history
    .getByRole("button", { name: "Load older runs", exact: true })
    .click();
  await expect(history.getByRole("heading")).toHaveText("Saved runs (66)");
  expect(offsets).toContain(61);
  for (let pageIndex = 0; pageIndex < 3; pageIndex++)
    await history
      .getByRole("button", { name: "Next runs", exact: true })
      .click();
  await expect(history.getByRole("button", { name: /run-29$/ })).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Run results", exact: true }),
  ).toContainText("Run run-0");
  await expect(
    page.getByRole("region", { name: "Change history", exact: true }),
  ).toContainText("Earlier records can lack a review.");
  expect(fixture.writes).toEqual([]);
  expect(fixture.unexpected).toEqual([]);
});

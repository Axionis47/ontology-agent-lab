import { expect, test, type Page } from "@playwright/test";
import { domains, savedDiscovery } from "./fixtures/saved-discovery";
import type { TrainingDetail, TrainingEvent } from "../src/lib/api";
import { mockWorkspace } from "./fixtures/saved-workspace";

async function savedKernel(page: Page, ready: boolean) {
  const fixture = await mockWorkspace(page, savedDiscovery(domains.empty));
  const base = "/api/tasks/fixture-task/agents/fixture-agent/training";
  const time = "2026-11-09T12:00:00Z";
  const candidate = {
    id: "accepted-kernel",
    run_id: "kernel-run",
    parent_id: null,
    digest: "a".repeat(64),
    status: "accepted",
    payload: {
      version: ready ? "oak.candidate.v3" : "oak.candidate.v2",
      schema: { entities: [], relations: [] },
      operation_bindings: [{ id: "read_records", tool_id: "tool-0" }],
    },
    decision: { validation: { formal_event_id: "formal-check" } },
    patch: null,
    created_at: time,
  };
  const run = {
    id: "kernel-run",
    task_id: "fixture-task",
    agent_id: "fixture-agent",
    mode: "training",
    status: "completed",
    stage: "finished",
    message: "Saved kernel fixture.",
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
    accepted_candidate_id: candidate.id,
    model_calls: 0,
    mcp_calls: 0,
    accounted_usd: 0,
    created_at: time,
    updated_at: time,
  };
  const detail = {
    run,
    candidates: [candidate],
    episodes: [
      {
        id: "kernel-episode",
        run_id: run.id,
        case_id: "case-0",
        candidate_id: candidate.id,
        stage: "harness",
        round_index: 0,
        status: "completed",
        case_snapshot: { query: "Read the saved record." },
        environment_ref: null,
        result: {
          final_output: "The required record is missing.",
          function_calls: [
            {
              invocation_id: "function-1",
              function_id: "grouped_average",
              result: {
                status: "complete",
                output_type: {
                  kind: "rows",
                  fields: [{ name: "value", type: "decimal", unit: "USD" }],
                },
                value: [{ group: "customer-7", value: "15.15" }],
                coverage: "observed",
                truncated: true,
                row_metadata: [
                  {
                    identity: { id: "record-7" },
                    score: "0.9",
                    evidence_refs: [{ observation_id: "source-7" }],
                  },
                ],
              },
            },
          ],
          request_snapshot: {
            fields: { record_id: "record-7" },
            unresolved: [],
          },
          dispatch_decisions: [
            {
              invocation_id: "call-1",
              tool_id: "tool-0",
              status: "missing_evidence",
              required_facts: ["record_exists"],
              available_sources: ["tool-0"],
            },
          ],
          graph_processing: [
            { invocation_id: "call-1", status: "quarantined" },
          ],
        },
        evaluation: null,
        created_at: time,
        finished_at: time,
      },
    ],
    events: [
      {
        id: "formal-check",
        run_id: run.id,
        episode_id: null,
        sequence: 1,
        kind: "candidate.formal_validation",
        message: "Formal schema validation passed.",
        data: { status: "passed", versions: { reasoner: "HermiT" } },
        created_at: time,
      },
    ],
  };
  await page.route("**/api/tasks/fixture-task/agents", (route) =>
    route.fulfill({
      json: [{ ...fixture.agent(), tool_ids: ["tool-0", "tool-1"] }],
    }),
  );
  const writes: unknown[] = [];
  let currentRun = run;
  let displayed: TrainingDetail | null = null;
  let latest = candidate as unknown as TrainingDetail["candidates"][number];
  await page.route("**/training**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "POST") {
      if (path.endsWith("/stop") && displayed) {
        displayed = {
          ...displayed,
          run: { ...displayed.run, status: "stopped" },
        };
        return route.fulfill({ json: displayed });
      }
      writes.push(request.postDataJSON());
      currentRun = { ...run, id: "inference-run", mode: "inference" };
      return route.fulfill({
        json: {
          ...detail,
          run: currentRun,
        },
      });
    }
    return route.fulfill({
      json:
        path === base
          ? {
              cases: [],
              runs: displayed
                ? [displayed.run, run]
                : currentRun.id === run.id
                  ? [run]
                  : [currentRun, run],
              has_more: false,
              accepted_candidate: latest,
              ready: false,
              message: "Saved records only.",
              inference_ready: ready,
              inference_message: ready
                ? "The accepted kernel is ready."
                : "This saved version requires kernel validation.",
              inference_tool_ids: ready ? ["tool-0"] : [],
            }
          : displayed && path.endsWith(displayed.run.id)
            ? displayed
            : {
                ...detail,
                run: path.endsWith(currentRun.id) ? currentRun : run,
              },
    });
  });
  await page.goto(
    "/?task=fixture-task&agent=fixture-agent&page=training&run=kernel-run",
  );
  return {
    ...fixture,
    inferenceWrites: writes,
    detail: detail as unknown as TrainingDetail,
    show: (value: TrainingDetail) => {
      displayed = value;
    },
    accept: (value: TrainingDetail["candidates"][number]) => {
      latest = value;
    },
  };
}

test("an unavailable kernel remains inspectable and explains why inference is disabled", async ({
  page,
}) => {
  const fixture = await savedKernel(page, false);
  await expect(
    page.getByRole("button", { name: "Try a new query", exact: true }),
  ).toBeEnabled();
  await expect(page.getByLabel("Inference availability")).toHaveText(
    "This saved version requires kernel validation.",
  );
  await page.getByRole("button", { name: /Initial construction/ }).click();
  await expect(
    page.getByRole("region", { name: "Candidate inspection" }),
  ).toContainText("accepted-kernel");
  await page
    .getByRole("button", { name: "Try a new query", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Run inference", exact: true }),
  ).toBeDisabled();
  await expect(page.getByLabel("Inference availability")).toHaveText(
    "This saved version requires kernel validation.",
  );
  expect(fixture.inferenceWrites).toEqual([]);
  expect(fixture.unexpected).toEqual([]);
});

test("inference selects only tools enabled by the accepted kernel", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const fixture = await savedKernel(page, true);
  await page
    .getByRole("button", { name: "Try a new query", exact: true })
    .click();
  const dialog = page.getByRole("region", { name: "Inference", exact: true });
  await expect(page).toHaveURL(/page=inference/);
  await dialog.getByText("MCP tools · 1 selected", { exact: true }).click();
  await expect(
    dialog.getByRole("checkbox", {
      name: "Records / primary:duplicate_name",
      exact: true,
    }),
  ).toBeChecked();
  await expect(
    dialog.getByRole("checkbox", {
      name: "Records / secondary:duplicate_name",
      exact: true,
    }),
  ).toHaveCount(0);
  await dialog
    .getByRole("textbox", { name: "Query", exact: true })
    .fill("Read record 7.");
  await dialog
    .getByText("Run limits · Set a cost limit before running", { exact: true })
    .click();
  await dialog
    .getByLabel("Maximum model cost (USD)", { exact: true })
    .fill("1");
  await dialog
    .getByRole("button", { name: "Run inference", exact: true })
    .click();
  expect(errors).toEqual([]);
  await expect
    .poll(() => fixture.inferenceWrites)
    .toEqual([
      expect.objectContaining({
        accepted_candidate_id: "accepted-kernel",
        tool_ids: ["tool-0"],
        query: "Read record 7.",
      }),
    ]);
  expect(fixture.unexpected).toEqual([]);
  await expect(page).toHaveURL(/page=inference.*run=inference-run/);
});

test("saved inspection shows the fixed request, dispatch decision, graph result, and formal check", async ({
  page,
}) => {
  const fixture = await savedKernel(page, true);
  await page
    .getByRole("button", { name: "Inspect harness trace", exact: true })
    .click();
  const inspection = page.getByRole("region", {
    name: "Episode inspection",
    exact: true,
  });
  await inspection
    .getByText("Fixed request and unresolved fields", { exact: true })
    .click();
  await expect(inspection).toContainText("record-7");
  const decisions = inspection.getByRole("region", {
    name: "Dispatch decisions",
    exact: true,
  });
  await decisions
    .getByText("tool-0 · missing_evidence", { exact: true })
    .click();
  await expect(decisions).toContainText("record_exists");
  await expect(decisions).toContainText("available_sources");
  await inspection
    .getByText("Graph processing results", { exact: true })
    .click();
  await expect(inspection).toContainText("quarantined");
  await inspection
    .getByText("Typed result and source records", { exact: true })
    .click();
  await expect(inspection).toContainText("15.15");
  await expect(inspection).toContainText("decimal");
  await expect(inspection).toContainText("source-7");
  await expect(inspection).toContainText("0.9");
  await expect(inspection).toContainText("Limited result");
  await page.getByText("Run activity (1)", { exact: true }).click();
  await expect(
    page.getByText("Formal schema validation passed.", { exact: true }),
  ).toBeVisible();
  await page
    .getByText("candidate.formal_validation record", { exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Run results", exact: true }),
  ).toContainText("HermiT");
  expect(fixture.inferenceWrites).toEqual([]);
  expect(fixture.unexpected).toEqual([]);
});

function liveRun(source: TrainingDetail) {
  const detail = structuredClone(source);
  detail.run = {
    ...detail.run,
    id: "live-run",
    mode: "inference",
    status: "running",
    stage: "inference",
    message: "Executing the query.",
  };
  detail.candidates[0].payload.schema = {
    entities: [
      {
        id: "record",
        name: "Records",
        identity_keys: ["id"],
        requirement_ids: [],
        properties: [
          { name: "id", type: "string" },
          { name: "title", type: "string" },
          { name: "owner_id", type: "string" },
          { name: "amount", type: "decimal", unit: "USD" },
        ],
      },
      {
        id: "owner",
        name: "Owners",
        identity_keys: ["id"],
        requirement_ids: [],
        properties: [{ name: "id", type: "string" }],
      },
    ],
    bindings: [],
    relations: [
      {
        id: "owned_by",
        name: "Owned by",
        from_entity: "record",
        from_property: "owner_id",
        to_entity: "owner",
        to_property: "id",
        binding_ids: [],
        requirement_ids: [],
      },
    ],
  };
  detail.candidates[0].payload.mappings = [
    { id: "records", tool_id: "tool-0", entity_id: "record" },
  ];
  detail.episodes = [
    {
      ...detail.episodes[0],
      id: "live-episode",
      run_id: "live-run",
      stage: "inference",
      status: "running",
      result: {},
      finished_at: null,
    },
  ];
  detail.events = [];
  return detail;
}

function event(
  sequence: number,
  kind: string,
  data: Record<string, unknown>,
): TrainingEvent {
  return {
    id: `event-${sequence}`,
    run_id: "live-run",
    episode_id: "live-episode",
    sequence,
    kind,
    data,
    message: "",
    created_at: "2026-11-10T12:00:00Z",
  };
}

function observation(id: string, scope: string, title: string) {
  return {
    id,
    invocation_id: `call-${id}`,
    tool_id: "tool-0",
    status: "succeeded",
    coverage: "unknown",
    arguments: { scope },
    data: { id: "shared-id", title, amount: "15.15" },
  };
}

function changes(id: string, scope: string, title: string) {
  return Object.entries({ id: "shared-id", title, amount: "15.15" }).map(
    ([property, value]) => ({
      entity_id: "record",
      identity: ["shared-id"],
      context: { scope },
      property,
      value,
      valid: true,
      evidence: {
        observation_id: id,
        tool_id: "tool-0",
        mapping_id: "records",
        path: `/${property}`,
        context: { scope },
      },
    }),
  );
}

const inferenceUrl =
  "/?task=fixture-task&agent=fixture-agent&page=inference&run=live-run";

test("inference reveals saved evidence live, preserves layout and contexts, and recovers after refresh", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const fixture = await savedKernel(page, true);
  const detail = liveRun(fixture.detail);
  detail.events = [
    event(1, "tool_proposed", {
      invocation_id: "call-source-a",
      name: "opaque_operation_0",
      arguments: { scope: "A" },
    }),
    event(2, "dispatch_decision", {
      invocation_id: "call-source-a",
      tool_id: "tool-0",
      status: "allowed",
    }),
    event(3, "tool_result", {
      observation: observation("source-a", "A", "First value"),
    }),
    event(4, "graph_updated", {
      observation_id: "source-a",
      revision: 1,
      changes: changes("source-a", "A", "First value"),
    }),
  ];
  fixture.show(detail);
  fixture.accept({
    ...detail.candidates[0],
    id: "newer-kernel",
    digest: "b".repeat(64),
    payload: { schema: { entities: [], relations: [] } },
  });
  await page.goto(inferenceUrl);
  const panel = page.getByRole("region", { name: "Inference", exact: true });
  await expect(panel.getByLabel("Inference status")).toHaveText("running");
  await expect(panel).toContainText("Displayed kernel: accepted-kernel");
  const recordCard = page.getByRole("group", {
    name: "Records, record, accepted entity",
    exact: true,
  });
  await expect(recordCard).toContainText("1 observed records");
  await expect(page.locator(".react-flow__edge")).toContainText(
    "Declared: Owned by",
  );
  const transform = await recordCard.evaluate(
    (element) => (element as HTMLElement).style.transform,
  );
  await panel
    .getByRole("button", { name: "Records: 1 observed records", exact: true })
    .click();
  const inspector = page.getByRole("region", { name: "Evidence inspector" });
  await expect(inspector).toContainText("First value");
  await expect(inspector).toContainText("15.15");
  await inspector
    .getByRole("button", { name: "Source source-a/title", exact: true })
    .click();
  const source = inspector.getByRole("region", { name: "Source observation" });
  await expect(source).toContainText("First value");
  await expect(source).toContainText("coverage unknown");
  const updates = changes("source-b", "B", "Second context");
  const removed = {
    ...changes("source-c", "A", "")[1],
    valid: false,
    value: null,
  };
  detail.events.push(
    event(5, "tool_result", {
      observation: observation("source-b", "B", "Second context"),
    }),
    event(6, "graph_updated", {
      observation_id: "source-b",
      revision: 2,
      changes: [...updates, removed],
    }),
  );
  // Repeated polling and duplicate events must not add records.
  detail.events.push(detail.events[5]);
  fixture.show(structuredClone(detail));
  await expect(recordCard).toContainText("2 observed records");
  expect(
    await recordCard.evaluate(
      (element) => (element as HTMLElement).style.transform,
    ),
  ).toBe(transform);
  await expect(
    inspector.getByRole("article", { name: "Observed record 1" }),
  ).not.toContainText("First value");
  await expect(
    inspector.getByRole("article", { name: "Observed record 1" }),
  ).toContainText("Missing evidence");
  await expect(
    inspector.getByRole("article", { name: "Observed record 2" }),
  ).toContainText("Second context");
  await panel.getByRole("button", { name: /6 · Graph updated/ }).click();
  await expect(recordCard).toHaveClass(/schema-neighbor/);
  await page.reload();
  await expect(recordCard).toContainText("2 observed records");
  await expect(page.getByRole("region", { name: "Final answer" })).toHaveCount(
    0,
  );
  await page.screenshot({
    path: "test-results/inference-live-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() => panel.evaluate((node) => node.scrollWidth <= node.clientWidth))
    .toBe(true);
  await page.screenshot({
    path: "test-results/inference-live-mobile.png",
    fullPage: true,
  });
  await panel.getByRole("button", { name: "Stop run", exact: true }).click();
  await expect(panel.getByLabel("Inference status")).toHaveText("stopped");
  await expect(recordCard).toContainText("2 observed records");
  expect(errors).toEqual([]);
  expect(fixture.inferenceWrites).toEqual([]);
  expect(fixture.unexpected).toEqual([]);
});

test("inference shows missing evidence and failures, then uses the final graph snapshot", async ({
  page,
}) => {
  const fixture = await savedKernel(page, true);
  const detail = liveRun(fixture.detail);
  detail.events = [
    event(1, "graph_updated", {
      revision: 1,
      observation_id: "source-a",
      changes: changes("source-a", "A", "Old value"),
    }),
    event(2, "dispatch_decision", {
      invocation_id: "blocked",
      tool_id: "tool-0",
      status: "missing_evidence",
      missing_dependencies: [
        {
          entity_id: "record",
          property: "owner_id",
          reason: "property_missing",
        },
      ],
    }),
    event(3, "tool_rejected", {
      invocation_id: "blocked",
      error: "Required arguments are missing.",
    }),
    event(4, "graph_processing_failed", {
      observation_id: "invalid",
      error: "Response type is invalid.",
    }),
  ];
  fixture.show(detail);
  await page.goto(inferenceUrl);
  const panel = page.getByRole("region", { name: "Inference", exact: true });
  const activity = panel.getByRole("region", { name: "Inference activity" });
  await expect(activity).toContainText("missing evidence");
  await expect(activity).toContainText("Tool rejected");
  await expect(activity).toContainText("Response type is invalid.");
  await activity.getByRole("button", { name: /Action decision/ }).click();
  await expect(
    panel.getByRole("region", { name: "Evidence inspector" }),
  ).toContainText("owner_id");
  detail.run.status = "completed";
  detail.episodes[0].status = "completed";
  detail.episodes[0].result = {
    final_output: "The result uses the final saved graph.",
    graph: {
      revision: 4,
      entities: {
        record: [
          {
            identity: ["final-id"],
            context: { scope: "final" },
            values: { id: "final-id", title: "Final value" },
            evidence: {},
          },
        ],
      },
    },
  };
  fixture.show(structuredClone(detail));
  await expect(
    panel.getByRole("region", { name: "Final answer" }),
  ).toContainText("final saved graph");
  await expect(
    panel.getByRole("heading", { name: "Observed graph · revision 4" }),
  ).toBeVisible();
  await panel
    .getByRole("button", { name: "Records: 1 observed records", exact: true })
    .click();
  const inspector = panel.getByRole("region", { name: "Evidence inspector" });
  await expect(inspector).toContainText("Final value");
  await expect(inspector).not.toContainText("Old value");
  await page.reload();
  await expect(
    panel.getByRole("region", { name: "Final answer" }),
  ).toBeVisible();
  expect(fixture.unexpected).toEqual([]);
});

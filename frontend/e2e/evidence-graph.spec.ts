import { expect, test } from "@playwright/test";
import {
  buildEvidenceGraph,
  bundleEdges,
} from "../src/features/discovery/evidence-graph";
import { domains, savedDiscovery } from "./fixtures/saved-discovery";
import { mockWorkspace } from "./fixtures/saved-workspace";

test("the graph preserves domain records, distinct IDs, directed relations, and source status", () => {
  for (const schema of Object.values(domains)) {
    const detail = savedDiscovery(schema);
    const before = JSON.stringify(detail);
    const graph = buildEvidenceGraph(detail);
    expect(graph.nodes.filter((n) => n.kind === "entity").length).toBe(
      schema.entities?.length ?? 0,
    );
    expect(graph.nodes.some((n) => n.kind === "gap")).toBe(true);
    expect(
      graph.edges.every(
        (e) =>
          graph.nodes.some((n) => n.id === e.source) &&
          graph.nodes.some((n) => n.id === e.target),
      ),
    ).toBe(true);
    expect(bundleEdges(graph.edges).flatMap((e) => e.records).length).toBe(
      graph.edges.length,
    );
    expect(JSON.stringify(detail)).toBe(before);
  }
  const services = buildEvidenceGraph(savedDiscovery(domains.services));
  expect(
    services.nodes.filter((n) => n.title === "Service").map((n) => n.id),
  ).toEqual(["e:gateway", "e:worker"]);
  expect(
    services.edges
      .filter((e) => e.item.kind === "relation")
      .map((e) => [e.source, e.target, e.label]),
  ).toEqual([
    ["e:gateway", "e:worker", "Forwards"],
    ["e:gateway", "e:worker", "Retries"],
    ["e:worker", "e:gateway", "Callback"],
    ["e:gateway", "e:gateway", "Self reference"],
  ]);
  expect(services.edges.some((e) => e.label === "Declared mapping")).toBe(true);
  expect(services.edges.some((e) => e.label === "Observed mapping")).toBe(true);
  expect(services.edges.some((e) => e.label.includes("prerequisite"))).toBe(
    false,
  );
  const missing = buildEvidenceGraph(savedDiscovery(domains.missing));
  expect(missing.referenceIssues).toBeGreaterThanOrEqual(2);
  expect(missing.edges.some((e) => e.item.kind === "relation")).toBe(false);
});

for (const name of ["commerce", "projects", "long", "empty"]) {
  test(`${name} evidence is readable, inspectable, and read-only`, async ({
    page,
  }) => {
    const detail = savedDiscovery(domains[name]);
    const fixture = await mockWorkspace(page, detail);
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await fixture.open();
    await page.getByRole("tab", { name: "Evidence map", exact: true }).click();
    const map = page.getByRole("region", { name: "Discovery evidence map" });
    await expect(map.locator(".react-flow__node")).toHaveCount(6);
    await expect(map.getByText("Clarifications", { exact: true })).toHaveCount(
      0,
    );
    await expect(map.getByText("Gaps and issues", { exact: true })).toHaveCount(
      0,
    );
    const before = fixture.polls();
    const viewport = map.locator(".react-flow__viewport");
    const transform = await viewport.getAttribute("style");
    await expect
      .poll(fixture.polls, { timeout: 10000 })
      .toBeGreaterThan(before);
    expect(await viewport.getAttribute("style")).toBe(transform);
    await expect(
      page.getByLabel("Evidence record list").locator("article"),
    ).toHaveCount(domains[name].entities?.length ?? 0);
    if (name === "commerce") {
      await page
        .getByRole("button", { name: "Connections for e:invoice", exact: true })
        .click();
      await expect(map.locator(".react-flow__node")).toHaveCount(4);
      await expect(
        page.getByRole("heading", { name: "Connections: Invoice" }),
      ).toBeVisible();
      await expect(
        page.getByRole("region", { name: "Saved graph connections" }),
      ).toContainText("invoice.customer_id → customer.customer_id");
      await map.screenshot({ path: "test-results/evidence-commerce.png" });
      await page
        .getByRole("button", { name: "Inspect selected record" })
        .click();
      await expect(page.getByRole("dialog")).toContainText("Saved ID: invoice");
      await page.keyboard.press("Escape");
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await expect
      .poll(() =>
        map.evaluate((element) => {
          const bounds = element.getBoundingClientRect();
          return [...element.querySelectorAll(".react-flow__node")].every(
            (node) => {
              const rect = node.getBoundingClientRect();
              return (
                rect.left >= bounds.left &&
                rect.right <= bounds.right &&
                rect.top >= bounds.top &&
                rect.bottom <= bounds.bottom
              );
            },
          );
        }),
      )
      .toBe(true);
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBe(true);
    await page.getByRole("tab", { name: "Review", exact: true }).click();
    const gaps = page.getByRole("region", {
      name: "Evidence gaps",
      exact: true,
    });
    await expect(gaps).toContainText("Complete source coverage is unknown.");
    await gaps
      .getByRole("button", {
        name: "Complete source coverage is unknown.",
        exact: true,
      })
      .click();
    await expect(page.getByRole("dialog")).toContainText(
      "Complete source coverage is unknown.",
    );
    await expect(
      page.getByRole("dialog").getByRole("heading", { name: "Run gaps" }),
    ).toHaveCount(0);
    expect(errors).toEqual([]);
    expect(fixture.writes).toEqual([]);
    expect(fixture.unexpected).toEqual([]);
  });
}

test("large graphs use bounded record lists and explicit neighbor pages", async ({
  page,
}) => {
  const detail = savedDiscovery(domains.large);
  const fixture = await mockWorkspace(page, detail);
  await fixture.open();
  await page.getByRole("tab", { name: "Evidence map", exact: true }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(6);
  const list = page.getByLabel("Evidence record list");
  await expect(list.locator("article")).toHaveCount(12);
  expect(await list.evaluate((node) => node.clientHeight)).toBeLessThanOrEqual(
    320,
  );
  await page
    .getByRole("button", { name: "Next evidence records", exact: true })
    .click();
  await expect(list).toContainText("Entity 12");
  await page.getByLabel("Find evidence record").fill("r-inspect");
  await page
    .getByRole("button", { name: "Connections for r:r-inspect", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Evidence graph explorer" }),
  ).toContainText("Showing 3 of 103 connected records");
  await expect(page.locator(".react-flow__node")).toHaveCount(4);
  await page
    .getByRole("button", { name: "Next connected records", exact: true })
    .click();
  await expect(page.getByLabel("Connected records pages")).toContainText(
    "2 / 35",
  );
  await expect(page.locator(".react-flow__node")).toHaveCount(4);
  await page.reload();
  await page.getByRole("tab", { name: "Evidence map", exact: true }).click();
  await expect(
    page.getByLabel("Evidence record list").locator("article"),
  ).toHaveCount(12);
  expect(fixture.writes).toEqual([]);
});

test("missing references, unanswered intent, and an uncertain write remain visible", async ({
  page,
}) => {
  const detail = savedDiscovery(domains.missing);
  detail.questions.push({
    id: "question-1",
    round: 1,
    question: {
      key: "workspace",
      text: "Which workspace?",
      why_needed: "Select the intended records.",
      evidence: [
        { source: "input", id: "surface", path: "/agent/responsibilities" },
      ],
      affected: ["r-inspect"],
      unresolved_detail: "",
    },
    answer: null,
    answered_by: null,
    answered_at: null,
  });
  detail.calls.push({
    id: "uncertain-write",
    kind: "mcp",
    purpose: "Update a supplied record",
    tool_id: "saved-tool",
    effect: "write",
    status: "unknown",
    request: {},
    response_artifact_id: null,
    error_code: "timeout",
    duration_ms: 1000,
    usage: null,
    reserved_nanos: 0,
    accounted_nanos: 0,
    created_at: detail.run.created_at,
  });
  const graph = buildEvidenceGraph(detail);
  expect(graph.nodes.find((n) => n.id === "q:question-1")?.status).toBe(
    "Needs an answer",
  );
  expect(graph.nodes.find((n) => n.id === "call:uncertain-write")?.status).toBe(
    "Write outcome unknown",
  );
  const fixture = await mockWorkspace(page, detail);
  await fixture.open();
  await page.getByRole("tab", { name: "Evidence map", exact: true }).click();
  await expect(page.getByTestId("rf__node-group:gap")).toHaveCount(0);
  await expect(page.getByTestId("rf__node-group:question")).toHaveCount(0);
  await page.getByRole("tab", { name: "Review", exact: true }).click();
  const questions = page.getByRole("region", {
    name: "Questions for you",
    exact: true,
  });
  const gaps = page.getByRole("region", { name: "Evidence gaps", exact: true });
  const checks = page.getByRole("region", {
    name: "Package checks",
    exact: true,
  });
  await expect(questions).toContainText("Which workspace?");
  await expect(gaps).not.toContainText("Which workspace?");
  await expect(gaps).toContainText("Complete source coverage is unknown.");
  await expect(checks).toContainText("Entity reference unavailable: absent.");
  await expect(checks).toContainText("Outcome unknown");
  await expect(gaps.getByRole("textbox")).toHaveCount(0);
  await checks
    .getByRole("button", { name: "Update a supplied record", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "Update a supplied record",
  );
  await page.keyboard.press("Escape");
  await questions
    .getByRole("button", { name: "Inspect question and source", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "User clarification about task intent",
  );
  await expect(page.getByRole("dialog")).not.toContainText(
    "Complete source coverage is unknown.",
  );
  expect(fixture.writes).toEqual([]);
});

test("same-name entities keep cycle, parallel, and self links inspectable", async ({
  page,
}) => {
  const fixture = await mockWorkspace(page, savedDiscovery(domains.services));
  await fixture.open();
  await page.getByRole("tab", { name: "Evidence map", exact: true }).click();
  await page
    .getByRole("button", { name: "Connections for e:gateway", exact: true })
    .click();
  const links = page.getByRole("region", { name: "Saved graph connections" });
  for (const label of ["Forwards", "Retries", "Callback", "Self reference"])
    await expect(links.getByText(label, { exact: true })).toBeVisible();
  await expect(links).toContainText("gateway.fallback → worker.key");
  await expect(links).toContainText("worker.peer → gateway.key");
  await page
    .getByRole("button", { name: "Next connected records", exact: true })
    .click();
  await expect(page.getByTestId("rf__node-e:worker")).toBeVisible();
  await expect(page.getByTestId("rf__node-e:worker")).toContainText("worker");
  await expect(page.getByTestId("rf__node-e:gateway")).toContainText("gateway");
  await page
    .getByRole("region", { name: "Discovery evidence map" })
    .screenshot({ path: "test-results/evidence-service-cycle.png" });
  await page.getByTestId("rf__node-e:worker").focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Inspect selected record" }).click();
  await expect(page.getByRole("dialog")).toContainText("Saved ID: worker");
  expect(fixture.writes).toEqual([]);
});

test("answered intent stays separate from missing evidence after navigation and reload", async ({
  page,
}) => {
  const detail = savedDiscovery(domains.single);
  detail.questions.push({
    id: "intent",
    round: 1,
    question: {
      key: "workspace",
      text: "Which workspace should be used?",
      why_needed: "Choose the intended records.",
      evidence: [
        { source: "input", id: "surface", path: "/agent/responsibilities" },
      ],
      affected: ["r-inspect"],
      unresolved_detail: "The workspace has not been selected.",
    },
    answer: "Primary workspace",
    answered_by: "demo-alex",
    answered_at: detail.run.created_at,
  });
  detail.requirements!.requirements[0].evidence.push({
    source: "question",
    id: "intent",
    path: "/answer",
  });
  const fixture = await mockWorkspace(page, detail);
  await fixture.open();
  await page.getByRole("tab", { name: "Evidence map", exact: true }).click();
  await page
    .getByRole("button", { name: "Inspect e:sample", exact: true })
    .click();
  const inspector = page.getByRole("dialog");
  await expect(
    inspector.getByRole("heading", {
      name: "Linked user clarifications",
      exact: true,
    }),
  ).toBeVisible();
  await expect(inspector).not.toContainText(
    "Complete source coverage is unknown.",
  );
  await inspector
    .getByRole("button", {
      name: "Which workspace should be used?",
      exact: true,
    })
    .click();
  await expect(inspector).toContainText("Answer: Primary workspace");
  await expect(inspector).not.toContainText("Still unresolved");
  expect(await inspector.innerText()).not.toContain(
    "The workspace has not been selected.",
  );
  await expect(inspector).toContainText("This is not a tool observation");
  await page.keyboard.press("Escape");
  await page.getByRole("tab", { name: "Review", exact: true }).click();
  const questions = page.getByRole("region", {
    name: "Questions for you",
    exact: true,
  });
  const gaps = page.getByRole("region", { name: "Evidence gaps", exact: true });
  await expect(questions).toContainText("0 awaiting an answer · 1 answered");
  await expect(questions).toContainText("Primary workspace");
  await expect(questions).not.toContainText("Still unresolved");
  await expect(questions).not.toContainText(
    "The workspace has not been selected.",
  );
  await expect(questions).not.toContainText("Cardinality was not supplied.");
  await expect(gaps).toContainText("Complete source coverage is unknown.");
  await expect(gaps.getByRole("textbox")).toHaveCount(0);
  await page.reload();
  await page.getByRole("tab", { name: "Review", exact: true }).click();
  await expect(questions).toContainText("Primary workspace");
  await expect(gaps).toContainText("Complete source coverage is unknown.");
  await page
    .getByRole("tabpanel", { name: "Review", exact: true })
    .screenshot({ path: "test-results/discovery-review.png" });
  expect(fixture.writes).toEqual([]);
  expect(fixture.unexpected).toEqual([]);
});

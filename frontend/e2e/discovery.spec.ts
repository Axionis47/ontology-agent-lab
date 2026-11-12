import { expect, test, type APIRequestContext } from "@playwright/test";

async function setup(request: APIRequestContext) {
  const headers = { Origin: "http://localhost:3047" };
  await request.post("http://127.0.0.1:9147/probe-reset");
  await request.post("http://127.0.0.1:8047/test-discovery?mode=success");
  const task = await (
    await request.post("/api/tasks", {
      headers,
      data: {
        name: "Discovery controls",
        objective:
          "Inspect notes and create one test note. Do not delete notes.",
      },
    })
  ).json();
  const base = `/api/tasks/${task.id}`;
  const connection = await (
    await request.post(`${base}/connections`, {
      headers,
      data: {
        name: "Supplied test world",
        url: "http://127.0.0.1:9147/discovery/mcp",
      },
    })
  ).json();
  await request.post(`${base}/connections/${connection.id}/refresh`, {
    headers,
  });
  const tools = await (await request.get(`${base}/tools`)).json();
  const agent = await (
    await request.post(`${base}/agents`, {
      headers,
      data: {
        name: "Surface discovery",
        responsibilities:
          "Inspect notes and create only a test note. Do not delete notes.",
        tool_ids: tools
          .filter((t: { name: string }) => t.name !== "search")
          .map((t: { id: string }) => t.id),
      },
    })
  ).json();
  return {
    url: `/?task=${task.id}&agent=${agent.id}`,
    api: `${base}/agents/${agent.id}/discovery`,
  };
}

async function modelCalls(request: APIRequestContext) {
  return (
    await (await request.get("http://127.0.0.1:8047/test-discovery")).json()
  ).calls;
}

test("discovery answers resume with saved evidence and no write replay", async ({
  page,
  request,
}) => {
  const setupData = await setup(request);
  const before = await modelCalls(request);
  await page.goto(setupData.url);
  const panel = page.getByRole("region", { name: "Discovery", exact: true });
  await expect(panel.getByRole("status")).toHaveText("Not started");
  await page.reload();
  await expect(
    panel.getByRole("button", { name: "Start discovery", exact: true }),
  ).toBeDisabled();
  expect(await modelCalls(request)).toBe(before);
  await panel
    .getByLabel("Supplied test environment")
    .fill("Official test workspace");
  await panel.getByLabel("Maximum model cost (USD)").fill("1");
  await panel
    .getByRole("button", { name: "Start discovery", exact: true })
    .click();
  await expect(panel.getByRole("status")).toHaveText("Running");
  await expect(panel.getByRole("status")).toHaveText("Paused for review", {
    timeout: 30000,
  });
  await expect(panel).toContainText("MCP calls: 3 / 12");
  const pausedCalls = await modelCalls(request);
  await panel.getByRole("tab", { name: "Schema (S₀)", exact: true }).click();
  await expect(
    panel.getByRole("region", { name: "Proposed functions" }),
  ).toContainText("note_fields");
  await panel
    .getByRole("button", { name: "note_fields · rows", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("Modeling reasons");
  await expect(page.getByRole("dialog")).toContainText(
    "Project the fields from observed records.",
  );
  await page.keyboard.press("Escape");
  expect(await modelCalls(request)).toBe(pausedCalls);
  await page.reload();
  await expect(
    panel.getByLabel("Which contact receives the note?"),
  ).toBeVisible();
  await panel.getByRole("tab", { name: "Review", exact: true }).click();
  await expect(
    panel.getByRole("region", { name: "Discovery modeling" }),
  ).toContainText("Discovery revision 4");
  await panel.getByText("entity: note", { exact: true }).click();
  await panel.getByText("Source access capabilities", { exact: true }).click();
  await expect(
    panel.getByRole("region", { name: "Discovery modeling" }),
  ).toContainText("pagination");
  await expect(panel.getByLabel("Modeling decisions")).toContainText(
    "Each note has its own identifier and title.",
  );
  await panel.getByRole("region", { name: "Discovery modeling" }).screenshot({
    path: "test-results/discovery-modeling.png",
  });
  await panel.getByRole("button", { name: "Go to answer fields" }).click();
  await expect(
    panel.getByLabel("Which contact receives the note?"),
  ).toBeFocused();
  await panel
    .getByLabel("Which contact receives the note?")
    .fill("Billing contact");
  expect(await modelCalls(request)).toBe(pausedCalls);
  await panel.getByRole("button", { name: "Answer and resume" }).click();
  await expect(panel.getByRole("status")).toHaveText("Discovery complete", {
    timeout: 30000,
  });
  await expect(panel).toContainText("MCP calls: 3 / 12");
  await expect(
    panel.getByRole("region", { name: "Discovery modeling" }),
  ).toContainText("Discovery revision 5");
  await expect(
    panel.getByRole("region", { name: "Questions for you", exact: true }),
  ).toContainText("Answer: Billing contact");
  const probes = await (
    await request.get("http://127.0.0.1:9147/probe-state")
  ).json();
  expect(
    probes.calls.filter((name: string) => name === "create_note"),
  ).toHaveLength(1);
  await panel
    .getByRole("tab", { name: "Requirements (R₀)", exact: true })
    .click();
  await expect(panel).toContainText(
    "Inspect notes and create only a test note",
  );
  await panel
    .getByRole("button", {
      name: "input: /agent/responsibilities",
      exact: true,
    })
    .click();
  await expect(page.getByRole("dialog")).toContainText("Do not delete notes");
  await page.keyboard.press("Escape");
  await panel.getByRole("tab", { name: "Evidence map" }).click();
  await expect(panel.getByLabel("Discovery evidence map")).toBeVisible();
  await expect(panel.getByLabel("Evidence record list")).toContainText("Note");
  await expect(panel.getByLabel("Evidence record list")).toContainText(
    "Proposed entity",
  );
  const completedCalls = await modelCalls(request);
  await page.reload();
  await expect(panel.getByRole("status")).toHaveText("Discovery complete");
  expect(await modelCalls(request)).toBe(completedCalls);
  await panel.screenshot({ path: "test-results/discovery-desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() => panel.evaluate((node) => node.scrollWidth <= node.clientWidth))
    .toBe(true);
  await panel.screenshot({ path: "test-results/discovery-mobile.png" });
});

test("a reached limit pauses until the user increases it and resumes", async ({
  page,
  request,
}) => {
  const { url } = await setup(request);
  await page.goto(url);
  const panel = page.getByRole("region", { name: "Discovery", exact: true });
  await panel.getByLabel("Supplied test environment").fill("Test workspace");
  await panel.getByLabel("Maximum model cost (USD)").fill("0.001");
  await panel
    .getByRole("button", { name: "Start discovery", exact: true })
    .click();
  await expect(panel.getByRole("status")).toHaveText("Paused for review");
  await expect(panel).toContainText("cost limit was reached");
  const before = await modelCalls(request);
  await panel.getByLabel("Maximum model cost (USD)").fill("1");
  expect(await modelCalls(request)).toBe(before);
  await panel
    .getByRole("button", { name: "Resume discovery", exact: true })
    .click();
  await expect(panel.getByRole("status")).toHaveText("Running");
  await panel.getByRole("button", { name: "Pause", exact: true }).click();
  await expect(panel.getByRole("status")).toHaveText("Paused for review");
  const overview = await (
    await request.get(await setupPathFromUrl(url))
  ).json();
  expect(overview.runs[0].limits.cost_usd).toBe("1");
  await panel.getByRole("button", { name: "Stop", exact: true }).click();
  await expect(panel.getByRole("status")).toHaveText("Stopped");
});

async function setupPathFromUrl(url: string) {
  const params = new URL(url, "http://localhost").searchParams;
  return `/api/tasks/${params.get("task")}/agents/${params.get("agent")}/discovery`;
}

test("a conflicting answer preserves the partial package and stops", async ({
  page,
  request,
}) => {
  const { url } = await setup(request);
  await request.post("http://127.0.0.1:8047/test-discovery?mode=conflict");
  await page.goto(url);
  const panel = page.getByRole("region", { name: "Discovery", exact: true });
  await panel.getByLabel("Supplied test environment").fill("Test workspace");
  await panel.getByLabel("Maximum model cost (USD)").fill("1");
  await panel
    .getByRole("button", { name: "Start discovery", exact: true })
    .click();
  await expect(panel.getByRole("status")).toHaveText("Paused for review", {
    timeout: 30000,
  });
  await panel
    .getByLabel("Which contact receives the note?")
    .fill("Delete the notes");
  await panel.getByRole("button", { name: "Answer and resume" }).click();
  await expect(panel.getByRole("status")).toHaveText("Stopped");
  await expect(panel).toContainText("contradicts the saved boundary");
  await panel.getByRole("tab", { name: "Tools and probes" }).click();
  await expect(
    panel.getByRole("button", { name: "Inspect response" }).first(),
  ).toBeVisible();
});

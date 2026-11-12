import { expect, test } from "@playwright/test";

test("agent configuration saves a task surface and tools from multiple MCP servers", async ({
  page,
  request,
}) => {
  await request.post("http://127.0.0.1:9147/catalog/original");
  const task = await (
    await request.post("/api/tasks", {
      headers: { Origin: "http://localhost:3047" },
      data: {
        name: "Agent configuration",
        objective: "Check source evidence.",
      },
    })
  ).json();
  const base = `/api/tasks/${task.id}`;
  for (const [name, endpoint] of [
    ["Research library", "alpha"],
    ["Source index", "beta"],
    ["Empty server", "missing"],
  ]) {
    const connection = await (
      await request.post(`${base}/connections`, {
        headers: { Origin: "http://localhost:3047" },
        data: { name, url: `http://127.0.0.1:9147/${endpoint}/mcp` },
      })
    ).json();
    if (endpoint !== "missing") {
      expect(
        (
          await request.post(`${base}/connections/${connection.id}/refresh`, {
            headers: { Origin: "http://localhost:3047" },
          })
        ).ok(),
      ).toBeTruthy();
    }
  }
  await page.goto(`/?task=${task.id}&tab=agents`);
  await page.getByRole("button", { name: "Add agent", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Empty server", { exact: true })).toBeVisible();
  await expect(dialog.getByText(/No tools discovered. Open/)).toBeVisible();
  await expect(dialog.getByTestId("selected-count")).toContainText(
    "0 selected",
  );
  await dialog
    .getByRole("textbox", { name: "Name", exact: true })
    .fill("Source analyst");
  await dialog
    .getByLabel("Responsibilities", { exact: true })
    .fill("Find sources.\nInspect each claim.");
  await dialog
    .getByLabel("Context and rules", { exact: true })
    .fill("Each claim must refer to a source.");
  await dialog
    .getByLabel("Boundaries", { exact: true })
    .fill("Ask when a source is missing.");
  await dialog
    .getByLabel("Success criteria", { exact: true })
    .fill("Each claim has supporting evidence.");
  await dialog
    .getByRole("button", { name: "Add example", exact: true })
    .click();
  await dialog
    .getByLabel("Situation and request")
    .fill("A report contains an unsupported claim.");
  await dialog
    .getByLabel("Expected behavior")
    .fill("Find the source or report the missing evidence.");
  await dialog
    .getByLabel("Prohibited behavior")
    .fill("Do not invent a source.");
  await dialog
    .getByRole("checkbox", { name: "Research library:search", exact: true })
    .check();
  await dialog
    .getByRole("checkbox", { name: "Source index:search", exact: true })
    .focus();
  await page.keyboard.press("Space");
  await expect(
    dialog.getByLabel("Selected MCP servers and tools"),
  ).toContainText("2 MCP servers / 2 tools selected");
  await dialog
    .getByRole("textbox", { name: "Search tools" })
    .fill("source index");
  await expect(dialog.getByRole("checkbox")).toHaveCount(1);
  await expect(
    dialog.getByLabel("Selected MCP servers and tools"),
  ).toContainText("2 MCP servers / 2 tools selected");
  await dialog.getByRole("textbox", { name: "Search tools" }).clear();
  await dialog.screenshot({
    path: "test-results/agent-configuration-desktop.png",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      dialog.evaluate((element) => element.scrollWidth <= element.clientWidth),
    )
    .toBe(true);
  await dialog
    .getByRole("textbox", { name: "Name", exact: true })
    .scrollIntoViewIfNeeded();
  await page.screenshot({
    path: "test-results/agent-configuration-mobile.png",
  });
  await page.setViewportSize({ width: 1280, height: 900 });

  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  let attempts = 0;
  await page.route(`**${base}/agents`, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    attempts += 1;
    await pending;
    await route.fulfill({
      status: 422,
      json: { detail: "The selected tool is unavailable." },
    });
  });
  await dialog
    .getByRole("button", { name: "Create agent", exact: true })
    .click();
  await expect(
    dialog.getByRole("button", { name: "Saving...", exact: true }),
  ).toBeDisabled();
  await expect(
    dialog.getByLabel("Responsibilities", { exact: true }),
  ).toBeDisabled();
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  await expect(dialog).toBeVisible();
  expect(attempts).toBe(1);
  release();
  await expect(dialog.getByRole("alert")).toHaveText(
    "The selected tool is unavailable.",
  );
  await expect(dialog.getByLabel("Boundaries", { exact: true })).toHaveValue(
    "Ask when a source is missing.",
  );
  await expect(
    dialog.getByRole("checkbox", { name: "Source index:search", exact: true }),
  ).toBeChecked();
  await expect(dialog.getByLabel("Expected behavior")).toHaveValue(
    "Find the source or report the missing evidence.",
  );
  await page.unroute(`**${base}/agents`);
  await dialog
    .getByRole("button", { name: "Create agent", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Saved task surface")).toContainText(
    "Each claim must refer to a source.",
  );
  await expect(page.getByLabel("Saved task surface")).toContainText(
    "Do not invent a source.",
  );
  await page.getByText(/Tool access settings ·/).click();
  await expect(page.getByTestId("selected-count")).toContainText(
    "2 selected / saved",
  );
  const saved = (await (await request.get(`${base}/agents`)).json())[0];
  const agentUrl = page.url();

  await page
    .getByRole("button", { name: "Edit configuration", exact: true })
    .click();
  await expect(
    dialog.getByRole("checkbox", {
      name: "Research library:search",
      exact: true,
    }),
  ).toBeChecked();
  await dialog
    .getByLabel("Boundaries", { exact: true })
    .fill("Discard this change.");
  await dialog
    .getByRole("checkbox", { name: "Research library:search", exact: true })
    .uncheck();
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  await page
    .getByRole("button", { name: "Edit configuration", exact: true })
    .click();
  await expect(dialog.getByLabel("Boundaries", { exact: true })).toHaveValue(
    "Ask when a source is missing.",
  );
  await expect(
    dialog.getByRole("checkbox", {
      name: "Research library:search",
      exact: true,
    }),
  ).toBeChecked();
  await dialog
    .getByLabel("Boundaries", { exact: true })
    .fill("Ask before changing source records.");
  await dialog
    .getByRole("checkbox", { name: "Research library:search", exact: true })
    .uncheck();
  await dialog
    .getByRole("button", { name: "Save changes", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByTestId("selected-count")).toContainText(
    "1 selected / saved",
  );
  await page.reload();
  await expect(page.getByLabel("Saved task surface")).toContainText(
    "Ask before changing source records.",
  );
  await page.getByText(/Tool access settings ·/).click();
  await expect(
    page.getByRole("checkbox", {
      name: "Research library:search",
      exact: true,
    }),
  ).not.toBeChecked();

  await page.goto(`/?task=${task.id}&tab=agents`);
  await page.getByRole("button", { name: "Add agent", exact: true }).click();
  await expect(
    dialog.getByRole("textbox", { name: "Name", exact: true }),
  ).toBeEmpty();
  await expect(
    dialog.getByLabel("Responsibilities", { exact: true }),
  ).toBeEmpty();
  await expect(dialog.getByTestId("selected-count")).toContainText(
    "0 selected",
  );
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  const other = await (
    await request.post(`${base}/agents`, {
      headers: { Origin: "http://localhost:3047" },
      data: {
        name: "Reviewer",
        responsibilities: "Review evidence.",
        tool_ids: [],
      },
    })
  ).json();
  expect(other.tool_ids).toEqual([]);
  await page.goto(agentUrl);
  const agents = await (await request.get(`${base}/agents`)).json();
  expect(
    agents.find((agent: { id: string }) => agent.id === saved.id).tool_ids,
  ).toHaveLength(1);
  expect(
    (await (await request.get("http://127.0.0.1:9147/health")).json()).calls,
  ).toBe(0);
});

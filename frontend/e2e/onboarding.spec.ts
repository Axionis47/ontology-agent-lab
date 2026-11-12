import { expect, test, type Page } from "@playwright/test";

async function createTask(page: Page, name: string) {
  await page
    .getByRole("button", { name: "Create task", exact: true })
    .first()
    .click();
  const form = page.getByRole("form", { name: "Task scope" });
  await form.getByRole("textbox", { name: "Name", exact: true }).fill(name);
  await form
    .getByRole("textbox", { name: "Purpose", exact: true })
    .fill("Make source relationships explicit for reliable research.");
  await form
    .getByRole("textbox", { name: "Responsibilities", exact: true })
    .fill("Find sources and inspect evidence.");
  await form
    .getByRole("textbox", { name: "Success criteria", exact: true })
    .fill("Claims have supporting sources.");
  await form.getByRole("button", { name: "Review scope", exact: true }).click();
  await form.getByRole("button", { name: "Create task", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(`${name}_`);
}

async function addMCP(
  page: Page,
  name: string,
  endpoint: string,
  auth = "Public endpoint",
  token?: string,
) {
  await page.getByRole("tab", { name: /MCPs/ }).click();
  await page.getByRole("button", { name: "+ Add MCP", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("MCP name").fill(name);
  await dialog.getByLabel("Endpoint URL").fill(endpoint);
  if (auth !== "Public endpoint") {
    await dialog.getByRole("combobox").click();
    await page.getByRole("option", { name: auth, exact: true }).click();
  }
  if (token) await dialog.getByLabel("Bearer token").fill(token);
  await dialog
    .getByRole("button", { name: "Connect MCP", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
}

async function addAgent(page: Page, name: string) {
  await page.getByRole("tab", { name: /Agents/ }).click();
  await page.getByRole("button", { name: "Add agent", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("textbox", { name: "Name", exact: true }).fill(name);
  await dialog
    .getByLabel("Responsibilities")
    .fill(`Find and inspect evidence as the ${name}.`);
  await dialog
    .getByLabel("Success criteria", { exact: true })
    .fill("Every claim has supporting evidence.");
  await dialog
    .getByRole("button", { name: "Create agent", exact: true })
    .click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(`${name}_`);
  await page.getByText(/Tool access settings ·/).click();
  await expect(page.getByTestId("selected-count")).toContainText("0 selected");
}

test("complete onboarding preserves explicit access and task boundaries", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await createTask(page, "Reliability research");
  const taskUrl = page.url();
  const taskId = new URL(taskUrl).searchParams.get("task");
  await addMCP(page, "Research library", "http://127.0.0.1:9147/alpha/mcp");
  await expect(
    page.getByRole("article", { name: "MCP Research library", exact: true }),
  ).toContainText("connected");
  await addMCP(page, "Source index", "http://127.0.0.1:9147/beta/mcp");
  await addAgent(page, "Research analyst");
  const firstAgentUrl = page.url();
  await page
    .getByRole("checkbox", { name: "Research library:search", exact: true })
    .check();
  await page
    .getByRole("checkbox", {
      name: "Research library:inspect_document",
      exact: true,
    })
    .focus();
  await page.keyboard.press("Space");
  await page.getByRole("button", { name: "Save tools", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Agent tool access" }).getByRole("status"),
  ).toContainText("Tool selections saved.");
  await page.reload();
  await page.getByText(/Tool access settings ·/).click();
  await expect(
    page.getByRole("checkbox", {
      name: "Research library:search",
      exact: true,
    }),
  ).toBeChecked();
  await expect(
    page.getByRole("checkbox", { name: "Source index:search", exact: true }),
  ).not.toBeChecked();
  await page
    .getByRole("button", { name: "Edit configuration", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("textbox", { name: "Name", exact: true })
    .fill("Source analyst");
  await page
    .getByRole("dialog")
    .getByLabel("Responsibilities")
    .fill("Verify every source before selecting evidence.");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Source analyst_",
  );
  await expect(
    page
      .getByRole("navigation", { name: "Tasks" })
      .getByRole("button", { name: /Source analyst/ }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("Verify every source before selecting evidence.", {
      exact: true,
    }),
  ).toBeVisible();
  await page.goto(taskUrl);
  await addAgent(page, "Evidence reviewer");
  const secondAgentUrl = page.url();
  await page
    .getByRole("checkbox", { name: "Source index:search", exact: true })
    .check();
  await page.getByRole("button", { name: "Save tools", exact: true }).click();
  await expect(page.getByTestId("selected-count")).toContainText(
    "1 selected / saved",
  );
  await page.goto(firstAgentUrl);
  await page.getByText(/Tool access settings ·/).click();
  await expect(page.getByTestId("selected-count")).toContainText(
    "2 selected / saved",
  );
  await request.post("http://127.0.0.1:9147/catalog/changed");
  await page.goto(taskUrl);
  await page.getByRole("tab", { name: /MCPs/ }).click();
  await page
    .getByRole("article", { name: "MCP Research library", exact: true })
    .getByRole("button", { name: "Refresh tools" })
    .click();
  await expect(page.getByText("summarize", { exact: true })).toBeVisible();
  await page.goto(firstAgentUrl);
  await page.getByText(/Tool access settings ·/).click();
  await expect(
    page.getByRole("checkbox", {
      name: "Research library:inspect_document",
      exact: true,
    }),
  ).toBeChecked();
  await expect(page.getByText("Unavailable", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("checkbox", {
      name: "Research library:summarize",
      exact: true,
    }),
  ).not.toBeChecked();
  await page
    .getByRole("textbox", { name: "Search tools" })
    .fill("source index");
  await expect(page.getByRole("checkbox")).toHaveCount(1);
  await page.getByRole("textbox", { name: "Search tools" }).clear();
  await page.screenshot({
    path: "test-results/oak-agent-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
  await page.screenshot({
    path: "test-results/oak-agent-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(taskUrl);
  await addMCP(
    page,
    "Secure archive",
    "http://127.0.0.1:9147/secure/mcp",
    "Bearer token",
    "wrong-token",
  );
  const secure = page.getByRole("article", {
    name: "MCP Secure archive",
    exact: true,
  });
  await expect(secure).toContainText("Could not discover tools");
  await secure.getByRole("button", { name: "Update token" }).click();
  await page
    .getByRole("dialog")
    .getByLabel("Bearer token")
    .fill("fixture-token");
  await page.getByRole("button", { name: "Save and reconnect" }).click();
  await expect(secure).toContainText("connected");
  await expect(secure).not.toContainText("Could not discover tools");
  await addMCP(page, "Unavailable service", "http://127.0.0.1:9147/missing");
  await expect(
    page.getByRole("article", { name: "MCP Unavailable service", exact: true }),
  ).toContainText("Could not discover tools");
  await addMCP(
    page,
    "OAuth library",
    "http://127.0.0.1:9147/oauth/mcp",
    "OAuth",
  );
  const oauth = page.getByRole("article", {
    name: "MCP OAuth library",
    exact: true,
  });
  const popupPromise = page.waitForEvent("popup");
  await oauth.getByRole("link", { name: "Authorize" }).click();
  const popup = await popupPromise;
  await expect(popup.getByText(/Authorization received/)).toBeVisible();
  await popup.close();
  await expect(oauth).toContainText("connected", { timeout: 15_000 });
  const catalog = await (
    await request.get(`/api/tasks/${taskId}/tools`)
  ).json();
  await createTask(page, "Separate task");
  await addAgent(page, "Separate agent");
  const other = new URL(page.url());
  const response = await request.put(
    `/api/tasks/${other.searchParams.get("task")}/agents/${other.searchParams.get("agent")}/tools`,
    {
      headers: { Origin: "http://localhost:3047" },
      data: { tool_ids: [catalog[0].id] },
    },
  );
  expect(response.status()).toBe(422);
  await page
    .getByRole("combobox", { name: "Demo user" })
    .selectOption("demo-sam");
  await expect(
    page.getByRole("heading", { name: "Your tasks." }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("navigation", { name: "Tasks" })
      .getByText("Reliability research"),
  ).toHaveCount(0);
  const hidden = await request.get(`/api/tasks/${taskId}/agents`, {
    headers: { "X-Oak-User": "demo-sam" },
  });
  expect(hidden.status()).toBe(404);
  await page.goto(firstAgentUrl.replace("demo-alex", "demo-sam"));
  await expect(
    page.getByText("This task is not available to the selected demo user.", {
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "Demo user" })
    .selectOption("demo-alex");
  await page.goto(secondAgentUrl);
  await page.getByText(/Tool access settings ·/).click();
  await expect(page.getByTestId("selected-count")).toContainText(
    "1 selected / saved",
  );
  await page
    .getByRole("navigation", { name: "Tasks" })
    .getByRole("button", { name: "Reliability research", exact: true })
    .click();
  await page.getByRole("tab", { name: /Agents/ }).click();
  await expect(
    page.getByRole("main").getByRole("button", { name: /Source analyst/ }),
  ).toContainText("2 tools");
  await page.getByRole("tab", { name: /MCPs/ }).click();
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("article", { name: "MCP Source index", exact: true })
    .getByRole("button", { name: "Remove", exact: true })
    .click();
  await expect(
    page.getByRole("article", { name: "MCP Source index", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("navigation", { name: "Tasks" })
    .getByRole("button", { name: /Evidence reviewer/ })
    .click();
  await page.getByText(/Tool access settings ·/).click();
  await expect(page.getByTestId("selected-count")).toContainText(
    "0 selected / saved",
  );
  expect(
    (await (await request.get("http://127.0.0.1:9147/health")).json()).calls,
  ).toBe(0);
});

test("task form retains failed input and dialogs preserve recovery behavior", async ({
  page,
}) => {
  let finishSave!: () => void;
  const pendingSave = new Promise<void>((resolve) => {
    finishSave = resolve;
  });
  let attempts = 0;
  await page.route("**/api/tasks", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    attempts += 1;
    await pendingSave;
    await route.fulfill({
      status: 422,
      json: { detail: "Check the task values." },
    });
  });
  await page.goto("/?view=create-task");
  const form = page.getByRole("form", { name: "Task scope" });
  await form
    .getByRole("textbox", { name: "Name", exact: true })
    .fill("Form recovery");
  await form
    .getByRole("textbox", { name: "Purpose", exact: true })
    .fill("Verify the saved configuration.");
  await form
    .getByRole("textbox", { name: "Responsibilities", exact: true })
    .fill("Inspect saved records.");
  await form
    .getByRole("textbox", { name: "Success criteria", exact: true })
    .fill("Records match the inputs.");
  await form.getByRole("button", { name: "Review scope", exact: true }).click();
  await form.getByRole("button", { name: "Create task", exact: true }).click();
  await expect(
    form.getByRole("button", { name: "Creating...", exact: true }),
  ).toBeDisabled();
  await expect(
    form.getByRole("button", { name: "Back to form", exact: true }),
  ).toBeDisabled();
  await expect(
    form.getByRole("button", { name: "Discard draft", exact: true }),
  ).toBeDisabled();
  await form.press("Enter");
  expect(attempts).toBe(1);
  finishSave();
  await expect(form.getByRole("alert")).toHaveText("Check the task values.");
  await form.getByRole("button", { name: "Back to form", exact: true }).click();
  await expect(
    form.getByRole("textbox", { name: "Name", exact: true }),
  ).toHaveValue("Form recovery");
  await expect(
    form.getByRole("textbox", { name: "Responsibilities", exact: true }),
  ).toHaveValue("Inspect saved records.");
  await page.unroute("**/api/tasks");
  await form.getByRole("button", { name: "Review scope", exact: true }).click();
  await form.getByRole("button", { name: "Create task", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Form recovery_",
  );

  let finishRename!: () => void;
  const pendingRename = new Promise<void>((resolve) => {
    finishRename = resolve;
  });
  await page.route("**/api/tasks/*", async (route) => {
    if (route.request().method() !== "PATCH") return route.continue();
    await pendingRename;
    await route.continue();
  });
  await page.getByRole("button", { name: "Rename task", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("textbox", { name: "Name", exact: true })
    .fill("Recovered task");
  await dialog.getByRole("button", { name: "Save name", exact: true }).click();
  await expect(
    dialog.getByRole("button", { name: "Saving...", exact: true }),
  ).toBeDisabled();
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  await expect(dialog).toBeVisible();
  finishRename();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Recovered task_",
  );
  await page.getByRole("button", { name: "Rename task", exact: true }).click();
  await expect(
    dialog.getByRole("textbox", { name: "Name", exact: true }),
  ).toHaveValue("Recovered task");
  await dialog.getByRole("button", { name: "Close", exact: true }).click();

  await page.getByRole("tab", { name: /MCPs/ }).click();
  await page.getByRole("button", { name: "+ Add MCP", exact: true }).click();
  await dialog.getByRole("combobox").click();
  await page.getByRole("option", { name: "Bearer token", exact: true }).click();
  await dialog.getByLabel("Bearer token").fill("discarded-token");
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByRole("button", { name: "+ Add MCP", exact: true }).click();
  await expect(dialog.getByRole("combobox")).toContainText("Public endpoint");
  await expect(dialog.getByLabel("Bearer token")).toHaveCount(0);
  await expect(dialog.getByLabel("Endpoint URL")).toBeEmpty();
});

test("private preview and same-origin mutation checks", async ({ request }) => {
  // Native fetch does not inherit Playwright's configured preview credentials.
  expect((await fetch("http://localhost:3047/")).status).toBe(401);
  expect((await fetch("http://localhost:3047/api/tasks")).status).toBe(401);
  expect((await fetch("http://127.0.0.1:8047/api/tasks")).status).toBe(401);
  const csrf = await request.post("/api/tasks", {
    headers: { Origin: "https://untrusted.example" },
    data: { name: "Injected", objective: "Blocked" },
  });
  expect(csrf.status()).toBe(403);
});

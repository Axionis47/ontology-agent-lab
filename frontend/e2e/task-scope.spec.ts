import { expect, test, type Page } from "@playwright/test";

async function fillCore(page: Page, name = "Team meetings") {
  const form = page.getByRole("form", { name: "Task scope" });
  await form.getByRole("textbox", { name: "Name", exact: true }).fill(name);
  await form
    .getByRole("textbox", { name: "Purpose", exact: true })
    .fill("Coordinate team meetings.");
  await form
    .getByRole("textbox", { name: "Responsibilities", exact: true })
    .fill("Create meetings.\nUpdate occurrences and series.");
  await form
    .getByRole("textbox", { name: "Success criteria", exact: true })
    .fill("The calendar matches the requested change.");
  return form;
}

test("full-page scope preserves sections and examples after review and creation", async ({
  page,
  request,
}) => {
  await page.goto("/?view=create-task");
  const form = await fillCore(page);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await form
    .getByRole("textbox", { name: "Context and rules", exact: true })
    .fill("An occurrence belongs to a series.");
  await form
    .getByRole("textbox", { name: "Boundaries", exact: true })
    .fill("Preserve unrelated meetings.");
  await form.getByRole("button", { name: "Add example", exact: true }).click();
  const first = form.getByRole("group", { name: "Example 1", exact: true });
  await first
    .getByRole("textbox", { name: "Situation and request", exact: true })
    .fill("Cancel Friday's occurrence.");
  await first
    .getByRole("textbox", { name: "Expected behavior", exact: true })
    .fill("Cancel only that occurrence.");
  await first
    .getByRole("textbox", { name: "Prohibited behavior", exact: true })
    .fill("Do not cancel the series.");
  await form.getByRole("button", { name: "Add example", exact: true }).click();
  const second = form.getByRole("group", { name: "Example 2", exact: true });
  await second
    .getByRole("textbox", { name: "Situation and request", exact: true })
    .fill("Cancel the entire series.");
  await second
    .getByRole("textbox", { name: "Expected behavior", exact: true })
    .fill("Cancel the series.");
  await form.getByRole("button", { name: "Add example", exact: true }).click();
  await form
    .getByRole("button", { name: "Remove example 3", exact: true })
    .click();
  await page.getByRole("link", { name: "Name", exact: true }).click();
  await page.screenshot({ path: "test-results/oak-task-scope-desktop.png" });

  await form.getByRole("button", { name: "Review scope", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Review task scope.",
  );
  await expect(
    form.getByText("Do not cancel the series.", { exact: true }),
  ).toBeVisible();
  await expect(form.getByRole("textbox")).toHaveCount(0);
  await form.getByRole("button", { name: "Back to form", exact: true }).click();
  await expect(
    first.getByRole("textbox", { name: "Prohibited behavior", exact: true }),
  ).toHaveValue("Do not cancel the series.");
  await form
    .getByRole("textbox", { name: "Name", exact: true })
    .fill("Team meeting coordination");
  await form.getByRole("button", { name: "Review scope", exact: true }).click();
  await form.getByRole("button", { name: "Create task", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Team meeting coordination_",
  );
  await expect(
    page.getByRole("tab", { name: "Scope", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await page.reload();
  const scope = page.getByRole("tabpanel");
  await expect(
    scope.getByText("Preserve unrelated meetings.", { exact: true }),
  ).toBeVisible();
  await expect(scope.getByRole("textbox")).toHaveCount(0);
  await expect(
    scope.getByRole("article", { name: "Example 1", exact: true }),
  ).toContainText("Do not cancel the series.");
  await expect(
    scope.getByRole("article", { name: "Example 2", exact: true }),
  ).toContainText("Cancel the entire series.");
  const taskId = new URL(page.url()).searchParams.get("task");
  const task = await (await request.get(`/api/tasks/${taskId}`)).json();
  expect(task.scope.responsibilities).toBe(
    "Create meetings.\nUpdate occurrences and series.",
  );
  const denied = await request.patch(`/api/tasks/${taskId}`, {
    headers: { Origin: "http://localhost:3047" },
    data: {
      name: task.name,
      objective: task.objective,
      scope: { ...task.scope, examples: [] },
    },
  });
  expect(denied.status()).toBe(409);
  await page.getByRole("button", { name: "Create task", exact: true }).click();
  await expect(
    form.getByRole("textbox", { name: "Name", exact: true }),
  ).toBeEmpty();
});

test("session drafts survive refresh and navigation and remain separate by user", async ({
  page,
}) => {
  await page.goto("/?view=create-task&user=demo-alex");
  const form = await fillCore(page, "Alex draft");
  await form.getByRole("button", { name: "Add example", exact: true }).click();
  await form
    .getByRole("textbox", { name: "Situation and request", exact: true })
    .fill("An unfinished example");
  await page.reload();
  await expect(
    form.getByRole("textbox", { name: "Name", exact: true }),
  ).toHaveValue("Alex draft");
  await expect(
    form.getByRole("textbox", { name: "Situation and request", exact: true }),
  ).toHaveValue("An unfinished example");
  await expect(page.getByRole("status")).toContainText("Draft restored");
  await page
    .getByRole("combobox", { name: "Demo user" })
    .selectOption("demo-sam");
  await page
    .getByRole("button", { name: "Create task", exact: true })
    .first()
    .click();
  await expect(
    form.getByRole("textbox", { name: "Name", exact: true }),
  ).toBeEmpty();
  await fillCore(page, "Sam draft");
  await page
    .getByRole("combobox", { name: "Demo user" })
    .selectOption("demo-alex");
  await page
    .getByRole("button", { name: "Create task", exact: true })
    .first()
    .click();
  await expect(
    form.getByRole("textbox", { name: "Name", exact: true }),
  ).toHaveValue("Alex draft");
  await form
    .getByRole("button", { name: "Discard draft", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Create task", exact: true })
    .first()
    .click();
  await expect(
    form.getByRole("textbox", { name: "Name", exact: true }),
  ).toBeEmpty();
  await page
    .getByRole("combobox", { name: "Demo user" })
    .selectOption("demo-sam");
  await page
    .getByRole("button", { name: "Create task", exact: true })
    .first()
    .click();
  await expect(
    form.getByRole("textbox", { name: "Name", exact: true }),
  ).toHaveValue("Sam draft");
});

test("required fields and examples validate while optional sections can remain empty", async ({
  page,
}) => {
  await page.goto("/?view=create-task");
  const form = page.getByRole("form", { name: "Task scope" });
  await form.getByRole("button", { name: "Review scope", exact: true }).click();
  await expect(
    form.getByRole("textbox", { name: "Name", exact: true }),
  ).toBeFocused();
  await page.keyboard.type("Minimum scope");
  await page.keyboard.press("Tab");
  await expect(
    form.getByRole("textbox", { name: "Purpose", exact: true }),
  ).toBeFocused();
  await fillCore(page, "Minimum scope");
  await form
    .getByRole("textbox", { name: "Responsibilities", exact: true })
    .fill("  \n ");
  await form.getByRole("button", { name: "Review scope", exact: true }).click();
  await expect(form.getByRole("alert")).toContainText("Enter text");
  await form
    .getByRole("textbox", { name: "Responsibilities", exact: true })
    .fill("Find meeting times.");
  await form.getByRole("button", { name: "Add example", exact: true }).click();
  await form
    .getByRole("textbox", { name: "Situation and request", exact: true })
    .fill("Find a time.");
  await form.getByRole("button", { name: "Review scope", exact: true }).click();
  await expect(
    form.getByRole("textbox", { name: "Expected behavior", exact: true }),
  ).toBeFocused();
  await form
    .getByRole("button", { name: "Remove example 1", exact: true })
    .click();
  await form
    .getByRole("textbox", { name: "Boundaries", exact: true })
    .fill("x".repeat(10000));
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
  await page.getByRole("link", { name: "Name", exact: true }).click();
  await page.screenshot({ path: "test-results/oak-task-scope-mobile.png" });
  await form.getByRole("textbox", { name: "Boundaries", exact: true }).clear();
  await form.getByRole("button", { name: "Review scope", exact: true }).click();
  await expect(form.getByText("Unspecified", { exact: true })).toHaveCount(3);
  await form.getByRole("button", { name: "Create task", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Minimum scope_",
  );
});

test("original tasks keep their objective without invented scope details", async ({
  page,
  request,
}) => {
  const response = await request.post("/api/tasks", {
    headers: { Origin: "http://localhost:3047" },
    data: { name: "Original task", objective: "Find original sources." },
  });
  expect(response.status()).toBe(201);
  const task = await response.json();
  await page.goto(`/?task=${task.id}&tab=scope`);
  const scope = page.getByRole("tabpanel");
  await expect(scope).toContainText("Find original sources.");
  await expect(scope.getByText("Unspecified", { exact: true })).toHaveCount(5);
  await expect(
    page.getByRole("button", { name: "Edit task", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Rename task", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("textbox", { name: "Name", exact: true })
    .fill("Renamed original");
  await dialog.getByRole("button", { name: "Save name", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Renamed original_",
  );
  await expect(scope).toContainText("Find original sources.");
});

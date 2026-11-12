import { expect, test, type APIRequestContext } from "@playwright/test";

async function createAgent(request: APIRequestContext) {
  const headers = { Origin: "http://localhost:3047" };
  const task = await (
    await request.post("/api/tasks", {
      headers,
      data: {
        name: "Model access",
        objective: "Keep this task text out of model checks.",
      },
    })
  ).json();
  const agent = await (
    await request.post(`/api/tasks/${task.id}/agents`, {
      headers,
      data: {
        name: "Connection tester",
        responsibilities: "Check sources.",
        tool_ids: [],
      },
    })
  ).json();
  return `/?task=${task.id}&agent=${agent.id}`;
}

async function calls(request: APIRequestContext) {
  return (await (await request.get("http://127.0.0.1:8047/test-model")).json())
    .calls;
}

test("model check persists without automatic calls on navigation or reload", async ({
  page,
  request,
}) => {
  const url = await createAgent(request);
  await request.post("http://127.0.0.1:8047/test-model?mode=success");
  const before = await calls(request);
  await page.goto(url);
  const panel = page.getByRole("region", { name: "Model connection" });
  await expect(
    panel.getByRole("button", { name: "Check connection", exact: true }),
  ).toBeEnabled();
  expect(await calls(request)).toBe(before);
  await page.reload();
  await expect(panel).toContainText("Vertex AI / gemini-3.8-flash");
  expect(await calls(request)).toBe(before);

  await panel
    .getByRole("button", { name: "Check connection", exact: true })
    .click();
  await expect(panel.getByRole("status")).toHaveText("Checking");
  await expect(
    panel.getByRole("button", { name: "Checking...", exact: true }),
  ).toBeDisabled();
  await page.reload();
  await expect(panel.getByRole("status")).toHaveText("Connected");
  await expect(panel).toContainText("50 input tokens / 20 output tokens");
  expect(await calls(request)).toBe(before + 1);
  const saved = await (await request.get("/api/model-runtime")).json();
  await page.goto("/");
  await page.goto(url);
  await expect(panel.getByRole("status")).toHaveText("Connected");
  expect(
    (await (await request.get("/api/model-runtime")).json()).last_check.id,
  ).toBe(saved.last_check.id);
  expect(await calls(request)).toBe(before + 1);
  await panel.screenshot({ path: "test-results/model-connection-desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      panel.evaluate((element) => element.scrollWidth <= element.clientWidth),
    )
    .toBe(true);
  await panel.screenshot({ path: "test-results/model-connection-mobile.png" });
});

test("model failure gives recovery instructions and permits a new check", async ({
  page,
  request,
}) => {
  const url = await createAgent(request);
  await request.post("http://127.0.0.1:8047/test-model?mode=permissions");
  const before = await calls(request);
  await page.goto(url);
  const panel = page.getByRole("region", { name: "Model connection" });
  await panel
    .getByRole("button", { name: "Check connection", exact: true })
    .click();
  await expect(panel.getByRole("status")).toHaveText("Check failed");
  await expect(panel.getByRole("alert")).toContainText("Google denied access");
  await expect(panel.getByRole("alert")).toContainText("model permissions");
  await page.reload();
  await expect(panel.getByRole("status")).toHaveText("Check failed");
  expect(await calls(request)).toBe(before + 1);
  await request.post("http://127.0.0.1:8047/test-model?mode=success");
  await panel
    .getByRole("button", { name: "Check connection", exact: true })
    .click();
  await expect(panel.getByRole("status")).toHaveText("Connected");
  await expect(panel.getByRole("alert")).toHaveCount(0);
  expect(await calls(request)).toBe(before + 2);
});

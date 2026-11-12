import { expect, test, type Locator } from "@playwright/test";
import { domains, savedDiscovery } from "./fixtures/saved-discovery";
import { mockWorkspace } from "./fixtures/saved-workspace";

async function bounded(list: Locator, viewportHeight: number) {
  const sizes = await list.evaluate((node) => ({
    height: node.clientHeight,
    content: node.scrollHeight,
    overflow: getComputedStyle(node).overflowY,
  }));
  expect(sizes.height).toBeLessThanOrEqual(Math.min(420, viewportHeight * 0.5));
  expect(sizes.content).toBeGreaterThan(sizes.height);
  expect(sizes.overflow).toBe("auto");
}

test("520 tools stay bounded and preserve draft grants through search, filters, details, and scrolling", async ({
  page,
}) => {
  const detail = savedDiscovery(domains.empty);
  const fixture = await mockWorkspace(page, detail, 520);
  detail.artifacts.find(
    (artifact) => artifact.kind === "catalog",
  )!.payload.tools = fixture.tools;
  await fixture.open();
  const access = page.getByRole("region", { name: "Agent tool access" });
  await expect(access).not.toBeVisible();
  await page.getByText(/Tool access settings ·/).click();
  const list = access.getByRole("region", { name: "Tool list", exact: true });
  await expect(list.getByRole("checkbox")).toHaveCount(520);
  await bounded(list, 720);
  await access.getByLabel("Search tools").fill("secondary");
  await expect(list.getByRole("checkbox")).toHaveCount(260);
  const duplicate = list.getByRole("checkbox", {
    name: "Records / secondary:duplicate_name",
    exact: true,
  });
  await duplicate.focus();
  await page.keyboard.press("Space");
  await expect(access.getByTestId("selected-count")).toHaveText(
    "2 selected / unsaved",
  );
  await access.getByLabel("Search tools").fill("no-match");
  await expect(list).toContainText("No tools match your search or filter.");
  await access.getByLabel("Search tools").clear();
  await access.getByRole("button", { name: "Selected", exact: true }).click();
  await expect(list.getByRole("checkbox")).toHaveCount(2);
  await expect(list.getByRole("checkbox").first()).toBeChecked();
  await list
    .getByRole("button", {
      name: "Details for Records / primary:duplicate_name",
      exact: true,
    })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "Description for tool 0.",
  );
  await page.keyboard.press("Escape");
  await access.getByRole("button", { name: "All", exact: true }).click();
  await list.focus();
  await page.keyboard.press("End");
  await expect
    .poll(() => list.evaluate((node) => node.scrollTop))
    .toBeGreaterThan(0);
  expect(
    await list.evaluate((node) =>
      node.contains(document.querySelector('input[aria-label="Search tools"]')),
    ),
  ).toBe(false);
  await expect(
    access.getByRole("button", { name: "Save tools", exact: true }),
  ).toBeEnabled();
  expect(fixture.writes).toEqual([]);
  expect(fixture.agent().tool_ids).toEqual(["tool-0"]);
  await access.getByRole("button", { name: "Save tools", exact: true }).click();
  await expect(access.getByTestId("selected-count")).toHaveText(
    "2 selected / saved",
  );
  expect(fixture.agent().tool_ids).toEqual(["tool-0", "tool-1"]);
  await page.setViewportSize({ width: 390, height: 844 });
  await bounded(list, 844);
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await access.getByLabel("Search tools").fill("tool_519");
  await expect(list.getByRole("checkbox")).toHaveCount(1);
  await list.getByRole("checkbox").check();
  await access.getByLabel("Search tools").clear();
  await access.getByRole("button", { name: "Selected", exact: true }).click();
  await expect(list.getByRole("checkbox")).toHaveCount(3);
  await page.screenshot({
    path: "test-results/catalog-mobile.png",
    fullPage: true,
  });
  expect(fixture.writes).toHaveLength(1);
  expect(fixture.unexpected).toEqual([]);
  await page
    .getByRole("tab", { name: "Tools and probes", exact: true })
    .click();
  const savedTools = page.getByRole("region", {
    name: "Saved discovery tools",
  });
  await expect(savedTools.getByRole("button")).toHaveCount(520);
  await bounded(savedTools, 844);
});

test("configuration and task catalogs share bounded scrolling and accessible controls", async ({
  page,
}) => {
  const fixture = await mockWorkspace(page, savedDiscovery(domains.empty), 520);
  await fixture.open();
  await page
    .getByRole("button", { name: "Edit configuration", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  const list = dialog.getByRole("region", { name: "Tool list", exact: true });
  await expect(list.getByRole("checkbox")).toHaveCount(520);
  await bounded(list, 720);
  await dialog.getByLabel("Search tools").fill("tool_517");
  await list.getByRole("checkbox").check();
  await dialog.getByRole("button", { name: "Selected", exact: true }).click();
  await dialog.getByLabel("Search tools").clear();
  await expect(list.getByRole("checkbox")).toHaveCount(2);
  await page.setViewportSize({ width: 390, height: 844 });
  await dialog.getByRole("button", { name: "All", exact: true }).click();
  await bounded(list, 844);
  await list.focus();
  await page.keyboard.press("PageDown");
  await expect
    .poll(() => list.evaluate((node) => node.scrollTop))
    .toBeGreaterThan(0);
  await expect(
    dialog.getByRole("button", { name: "Save changes", exact: true }),
  ).toBeVisible();
  await dialog
    .getByRole("button", { name: "Save changes", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  expect(fixture.agent().tool_ids).toEqual(["tool-0", "tool-517"]);
  await page.goto("/?task=fixture-task&tab=mcps");
  const shared = page.getByRole("region", {
    name: "Shared tool catalog",
    exact: true,
  });
  await expect(
    shared.getByRole("button", { name: "Selected", exact: true }),
  ).toHaveCount(0);
  await expect(shared.getByRole("checkbox")).toHaveCount(0);
  await bounded(
    shared.getByRole("region", { name: "Tool list", exact: true }),
    844,
  );
  await shared.getByLabel("Search tools").fill("duplicate_name");
  await expect(
    shared.getByRole("button", { name: /^Details for/ }),
  ).toHaveCount(2);
  expect(fixture.writes).toHaveLength(1);
  expect(fixture.unexpected).toEqual([]);
});

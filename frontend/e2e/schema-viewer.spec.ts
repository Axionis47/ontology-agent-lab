import { expect, test } from "@playwright/test";
import {
  adaptSchema,
  resolveEvidence,
} from "../src/features/discovery/schema-adapter";
import { domains, savedDiscovery } from "./fixtures/saved-discovery";
import { mockWorkspace } from "./fixtures/saved-workspace";

for (const name of [
  "commerce",
  "projects",
  "services",
  "single",
  "empty",
  "no_properties",
  "missing",
  "long",
  "large",
]) {
  test(`saved ${name} schema uses the same diagram and table records`, async ({
    page,
  }) => {
    const detail = savedDiscovery(domains[name]);
    const source = JSON.stringify(detail);
    const model = adaptSchema(detail.schema_proposal!);
    const fixture = await mockWorkspace(page, detail);
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await fixture.open();
    await page.getByRole("tab", { name: "Schema (S₀)", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Diagram", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    if (model.entities.length) {
      await expect(page.locator(".react-flow__node")).toHaveCount(
        model.entities.length,
        { timeout: 30000 },
      );
      await expect(page.locator(".react-flow__edge")).toHaveCount(
        model.connectedRelations.length,
      );
      for (const relation of model.connectedRelations) {
        await expect(
          page.getByTestId(`rf__edge-${relation.id}`),
        ).toHaveAttribute(
          "aria-label",
          `${relation.name}, ${relation.id}: ${relation.from_entity}.${relation.from_property} to ${relation.to_entity}.${relation.to_property}`,
        );
        await expect(
          page
            .getByTestId(`rf__edge-${relation.id}`)
            .locator(".react-flow__edge-path"),
        ).not.toHaveAttribute("d", "");
      }
      const endpointErrors = await page.evaluate(
        (relations) =>
          relations.flatMap((relation) => {
            const edge = [
              ...document.querySelectorAll<SVGGElement>(".react-flow__edge"),
            ].find((node) => node.dataset.id === relation.id);
            const path = edge?.querySelector<SVGPathElement>(
              ".react-flow__edge-path",
            );
            if (!path) return [Infinity];
            return (["from", "to"] as const).map((side) => {
              const entity =
                side === "from" ? relation.from_entity : relation.to_entity;
              const property =
                side === "from" ? relation.from_property : relation.to_property;
              const handleId = JSON.stringify([
                "property",
                entity,
                property,
                side === "from" ? "out" : "in",
              ]);
              const handle = [
                ...document.querySelectorAll<HTMLElement>(
                  ".react-flow__handle",
                ),
              ].find((node) => node.dataset.handleid === handleId);
              if (!handle) return Infinity;
              const bounds = handle.getBoundingClientRect();
              const point = path.getPointAtLength(
                side === "from" ? 0 : path.getTotalLength(),
              );
              const screen = new DOMPoint(point.x, point.y).matrixTransform(
                path.getScreenCTM()!,
              );
              return Math.hypot(
                screen.x - bounds.x - bounds.width / 2,
                screen.y - bounds.y - bounds.height / 2,
              );
            });
          }),
        model.connectedRelations,
      );
      expect(Math.max(0, ...endpointErrors)).toBeLessThan(2);
      if (name === "commerce" || name === "services")
        await page
          .getByLabel("Schema diagram", { exact: true })
          .screenshot({ path: `test-results/schema-${name}-desktop.png` });
      expect(
        await page
          .getByLabel("Schema diagram", { exact: true })
          .evaluate((node) => node.clientHeight),
      ).toBeLessThanOrEqual(560);
    } else
      await expect(
        page.getByText(
          "No saved entities. Inspect operations below or open Review.",
        ),
      ).toBeVisible();
    if (name === "missing") {
      await expect(
        page.getByText("Entity reference unavailable: absent.", {
          exact: true,
        }),
      ).toBeVisible();
      await expect(
        page.getByText(
          "Property reference unavailable or ambiguous: present.unknown.",
          { exact: true },
        ),
      ).toBeVisible();
    }
    await page.getByRole("button", { name: "Table", exact: true }).click();
    const table = page.getByRole("region", { name: "Schema table" });
    await expect(table.locator("tbody tr")).toHaveCount(
      model.entities.reduce(
        (total, entity) => total + Math.max(1, entity.properties.length),
        0,
      ),
    );
    for (const entity of model.entities)
      await expect(
        table.getByRole("button", {
          name: `${entity.name} ${entity.id}`.replace(/\s+/g, " ").trim(),
          exact: true,
        }),
      ).toHaveCount(1);
    await expect(
      page.getByRole("region", { name: "Operations and prerequisites" }),
    ).toContainText("The user must select the workspace.");
    await page.getByLabel("Search schema").fill("no-saved-record-matches-this");
    await expect(table).toContainText("No matching entities.");
    await page.getByLabel("Search schema").clear();
    await page.setViewportSize({ width: 390, height: 844 });
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBe(true);
    await page.getByRole("button", { name: "Diagram", exact: true }).click();
    if (model.entities.length) {
      await expect(page.locator(".react-flow__node")).toHaveCount(
        model.entities.length,
      );
      expect(
        await page
          .getByLabel("Schema diagram", { exact: true })
          .evaluate((node) => node.clientHeight),
      ).toBeLessThanOrEqual(844 * 0.7);
    }
    if (name === "commerce" || name === "services")
      await page.screenshot({
        path: `test-results/schema-${name}-mobile.png`,
        fullPage: true,
      });
    expect(fixture.writes).toEqual([]);
    expect(fixture.unexpected).toEqual([]);
    expect(errors).toEqual([]);
    expect(JSON.stringify(detail)).toBe(source);
  });
}

test("typed collections and decimals appear in the diagram and table", async ({
  page,
}) => {
  const schema = structuredClone(domains.single);
  schema.entities![0].properties.push(
    { name: "features", type: "array", item_type: "string", unit: null },
    { name: "average", type: "decimal", unit: "USD" },
  );
  const fixture = await mockWorkspace(page, savedDiscovery(schema));
  await fixture.open();
  await page.getByRole("tab", { name: "Schema (S₀)", exact: true }).click();
  await expect(page.locator(".react-flow__node")).toContainText(
    "array<string>",
  );
  await expect(page.locator(".react-flow__node")).toContainText("decimal");
  await page.getByRole("button", { name: "Table", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Schema table" }),
  ).toContainText("array<string>");
  await expect(
    page.getByRole("region", { name: "Schema table" }),
  ).toContainText("decimal");
  expect(fixture.writes).toEqual([]);
});

test("selection uses IDs, retains viewport during polling, and opens the same evidence on desktop and mobile", async ({
  page,
}) => {
  const detail = savedDiscovery(domains.services);
  const fixture = await mockWorkspace(page, detail);
  await fixture.open();
  await page.getByRole("tab", { name: "Schema (S₀)", exact: true }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(3);
  const worker = page.getByTestId('rf__node-["entity","worker"]');
  const gateway = page.getByTestId('rf__node-["entity","gateway"]');
  await expect(worker).toContainText("Service");
  await expect(gateway).toContainText("Service");
  await worker.focus();
  await page.keyboard.press("Enter");
  const inspector = page.getByRole("dialog");
  await expect(inspector).toContainText("Saved ID: worker");
  await expect(worker).toHaveClass(/selected/);
  await expect(gateway).toHaveClass(/schema-neighbor/);
  await expect(page.getByTestId('rf__node-["entity","metrics"]')).toHaveCSS(
    "opacity",
    "0.3",
  );
  await expect(page.getByTestId("rf__edge-callback")).toHaveClass(
    /schema-related/,
  );
  await expect(inspector).toContainText(
    "Source support: declared · Coverage: unknown",
  );
  await expect(inspector).toContainText(
    "Source support: observed · Coverage: sample",
  );
  await expect(inspector.locator("pre")).not.toBeVisible();
  const viewport = page.locator(".react-flow__viewport");
  const transform = await viewport.getAttribute("style");
  const nodeElement = await worker.elementHandle();
  const before = fixture.polls();
  await expect.poll(fixture.polls, { timeout: 10000 }).toBeGreaterThan(before);
  expect(await viewport.getAttribute("style")).toBe(transform);
  expect(await nodeElement!.evaluate((node) => node.isConnected)).toBe(true);
  await expect(inspector).toContainText("Saved ID: worker");
  detail
    .schema_proposal!.entities!.find((entity) => entity.id === "worker")!
    .properties.push({ name: "revision", type: "integer" });
  await page
    .getByRole("button", { name: "Refresh discovery status", exact: true })
    .click();
  await expect(
    worker.getByRole("button", { name: "worker.revision", exact: true }),
  ).toBeVisible();
  await expect(inspector).toContainText("Saved ID: worker");
  await page.keyboard.press("Escape");
  await expect(worker).toBeFocused();
  await worker
    .getByRole("button", { name: "worker.peer", exact: true })
    .click();
  await expect(page.getByTestId("rf__edge-callback")).toHaveClass(
    /schema-related/,
  );
  await expect(page.getByTestId("rf__edge-forwards")).not.toHaveClass(
    /schema-related/,
  );
  await expect(
    inspector.getByRole("heading", { name: "worker.peer", exact: true }),
  ).toBeVisible();
  await inspector
    .getByRole("button", { name: "artifact: /data/value", exact: true })
    .first()
    .click();
  await expect(inspector).toContainText("Observed sample value");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Table", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole("region", { name: "Schema table" })
    .getByRole("button", { name: "Service worker", exact: true })
    .click();
  await expect(inspector).toContainText("Saved ID: worker");
  await expect(inspector).toHaveAttribute("aria-modal", "true");
  await expect
    .poll(() =>
      inspector.evaluate((node) => node.scrollWidth <= node.clientWidth),
    )
    .toBe(true);
  await page.keyboard.press("Escape");
  await page.getByRole("tab", { name: "Evidence map", exact: true }).click();
  await page
    .getByRole("button", { name: "Inspect e:worker", exact: true })
    .click();
  await expect(inspector).toContainText("Saved ID: worker");
  expect(fixture.writes).toEqual([]);
  expect(fixture.unexpected).toEqual([]);
});

test("missing evidence and escaped JSON pointers preserve unknown and null values", async ({
  page,
}) => {
  const detail = savedDiscovery(domains.single);
  const ref = {
    source: "input" as const,
    id: "surface",
    path: "/a~1b/~0key",
  };
  expect(resolveEvidence(detail, ref)).toMatchObject({
    found: true,
    value: null,
  });
  detail.schema_proposal!.bindings![0].source = {
    source: "artifact",
    id: "missing-artifact",
    path: "/data/no-value",
  };
  detail.schema_proposal!.entities![0].requirement_ids.push(
    "missing-requirement",
  );
  const fixture = await mockWorkspace(page, detail);
  await fixture.open();
  await page.getByRole("tab", { name: "Schema (S₀)", exact: true }).click();
  await expect(
    page.getByText("Requirement reference unavailable: missing-requirement.", {
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", {
      name: "Evidence reference unavailable: artifact:missing-artifact/data/no-value.",
      exact: true,
    })
    .click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText(
    "Evidence reference unavailable",
  );
  expect(fixture.writes).toEqual([]);
});

test("a failed diagram download keeps the Table view available", async ({
  page,
}) => {
  const fixture = await mockWorkspace(page, savedDiscovery(domains.commerce));
  await fixture.open();
  await page.route("**/_next/static/chunks/*.js", async (route) => {
    const response = await route.fetch();
    const body = await response.text();
    if (body.includes("elk.algorithm")) return route.abort();
    return route.fulfill({ response, body });
  });
  await page.getByRole("tab", { name: "Schema (S₀)", exact: true }).click();
  await expect(
    page
      .getByRole("region", { name: "Schema (S₀)", exact: true })
      .getByRole("alert"),
  ).toContainText("The diagram is unavailable", { timeout: 30000 });
  await page.getByRole("button", { name: "Table", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Schema table" }).locator("tbody tr"),
  ).toHaveCount(9);
  expect(fixture.writes).toEqual([]);
});

import type { DiscoveryDetail } from "../../src/lib/api";
import type {
  Entity,
  Schema,
} from "../../src/features/discovery/schema-adapter";

const entity = (
  id: string,
  name: string,
  fields: [
    string,
    "string" | "integer" | "number" | "boolean" | "array" | "object",
    string?,
  ][],
): Entity => ({
  id,
  name,
  properties: fields.map(([name, type, unit]) => ({
    name,
    type,
    unit: unit ?? null,
  })),
  identity_keys: [fields[0][0]],
  requirement_ids: ["r-inspect"],
});
const relation = (
  id: string,
  name: string,
  from: string,
  fromProperty: string,
  to: string,
  toProperty: string,
) => ({
  id,
  name,
  from_entity: from,
  from_property: fromProperty,
  to_entity: to,
  to_property: toProperty,
  requirement_ids: ["r-inspect"],
  binding_ids: [`${from}:${fromProperty}`, `${to}:${toProperty}`],
});

export const domains: Record<string, Schema> = {
  commerce: {
    entities: [
      entity("customer", "Customer", [
        ["customer_id", "string"],
        ["profile", "object"],
      ]),
      entity("invoice", "Invoice", [
        ["invoice_id", "string"],
        ["customer_id", "string"],
        ["total", "number", "USD"],
        ["lines", "array"],
      ]),
      entity("payment", "Payment", [
        ["payment_id", "string"],
        ["invoice_id", "string"],
        ["amount", "number", "USD"],
      ]),
    ],
    relations: [
      relation(
        "issued-to",
        "Issued to",
        "invoice",
        "customer_id",
        "customer",
        "customer_id",
      ),
      relation(
        "settles",
        "Settles",
        "payment",
        "invoice_id",
        "invoice",
        "invoice_id",
      ),
    ],
  },
  projects: {
    entities: [
      entity("project", "Project", [
        ["key", "string"],
        ["owner", "string"],
      ]),
      entity("task", "Task", [
        ["key", "string"],
        ["project", "string"],
        ["assignee", "string"],
        ["estimate", "number", "hours"],
      ]),
      entity("person", "Person", [
        ["key", "string"],
        ["skills", "array"],
      ]),
    ],
    relations: [
      relation("member-of", "Member of", "task", "project", "project", "key"),
      relation(
        "assigned-to",
        "Assigned to",
        "task",
        "assignee",
        "person",
        "key",
      ),
      relation("owned-by", "Owned by", "project", "owner", "person", "key"),
    ],
  },
  services: {
    entities: [
      entity("gateway", "Service", [
        ["key", "string"],
        ["peer", "string"],
        ["fallback", "string"],
      ]),
      entity("worker", "Service", [
        ["key", "string"],
        ["peer", "string"],
      ]),
      entity("metrics", "Metrics", [
        ["key", "string"],
        ["latency", "number", "ms"],
      ]),
    ],
    relations: [
      relation("forwards", "Forwards", "gateway", "peer", "worker", "key"),
      relation("retries", "Retries", "gateway", "fallback", "worker", "key"),
      relation("callback", "Callback", "worker", "peer", "gateway", "key"),
      relation("self", "Self reference", "gateway", "key", "gateway", "key"),
    ],
  },
  single: {
    entities: [
      entity("sample", "Sample", [
        ["code", "string"],
        ["enabled", "boolean"],
      ]),
    ],
    relations: [],
  },
  empty: { entities: [], relations: [] },
  no_properties: {
    entities: [
      {
        id: "unresolved",
        name: "Unresolved entity",
        properties: [],
        identity_keys: [],
        requirement_ids: ["r-inspect"],
      },
    ],
    relations: [],
  },
  missing: {
    entities: [entity("present", "Present", [["key", "string"]])],
    relations: [
      relation(
        "missing-entity",
        "Unavailable entity",
        "present",
        "key",
        "absent",
        "key",
      ),
      relation(
        "missing-property",
        "Unavailable property",
        "present",
        "unknown",
        "present",
        "key",
      ),
    ],
  },
  long: {
    entities: [
      entity(
        "long-entity",
        "Entity with a long saved display name ".repeat(6),
        [
          ["property_with_a_long_saved_name_".repeat(8), "object"],
          ["measure", "number", "a long unit declaration ".repeat(8)],
        ],
      ),
    ],
    relations: [],
  },
  large: {
    entities: Array.from({ length: 100 }, (_, i) =>
      entity(`e-${i}`, `Entity ${i}`, [
        ["id", "integer"],
        ["parent", "integer"],
        ["data", "object"],
      ]),
    ),
    relations: Array.from({ length: 99 }, (_, i) =>
      relation(`r-${i}`, `Parent ${i}`, `e-${i + 1}`, "parent", `e-${i}`, "id"),
    ),
  },
};

export function savedDiscovery(source: Schema): DiscoveryDetail {
  const schema = structuredClone(source);
  schema.bindings = schema.entities?.flatMap((entity) =>
    entity.properties.map((property, index) => ({
      id: `${entity.id}:${property.name}`,
      entity_id: entity.id,
      property: property.name,
      tool_id: "saved-tool",
      support: index % 2 ? ("observed" as const) : ("declared" as const),
      coverage: index % 2 ? ("sample" as const) : ("unknown" as const),
      source: {
        source: "artifact" as const,
        id: index % 2 ? "observation" : "catalog",
        path:
          index % 2 ? "/data/value" : "/tools/0/output_schema/properties/value",
      },
    })),
  );
  schema.operations = [
    {
      id: "inspect-records",
      tool_id: "saved-tool",
      effect: "read",
      requirement_ids: ["r-inspect"],
      prerequisites: [
        "The user must select the workspace.",
        "Access must be granted before this operation.",
      ],
      outputs: "Saved records from the selected workspace.",
      confirmation_tool_id: null,
      limitations: ["The saved sample does not establish complete coverage."],
    },
  ];
  schema.gaps = [
    {
      id: "coverage",
      message: "Complete source coverage is unknown.",
      blocking: false,
      evidence: [
        { source: "artifact", id: "observation", path: "/data/value" },
      ],
    },
  ];
  const created_at = "2026-10-01T10:00:00Z";
  return {
    run: {
      id: "saved-run",
      task_id: "fixture-task",
      agent_id: "fixture-agent",
      environment: "Saved fixture",
      status: "completed",
      stage: "checks",
      reason: "gaps",
      message: null,
      revision: 1,
      limits: {
        cost_usd: "1",
        mcp_calls: 12,
        model_calls: 14,
        active_seconds: 600,
        clarification_rounds: 2,
      },
      active_ms: 100,
      clarification_rounds: 0,
      created_at,
      updated_at: created_at,
      model_calls: 0,
      mcp_calls: 0,
      accounted_usd: 0,
      reserved_usd: 0,
      remaining_usd: 1,
      outdated: false,
    },
    inputs: {
      agent: { responsibilities: "Inspect saved records only." },
      "a/b": { "~key": null },
    },
    questions: [],
    events: [],
    calls: [],
    requirements: {
      requirements: [
        {
          id: "r-inspect",
          statement: "Inspect records and preserve source uncertainty.",
          evidence: [
            {
              source: "input",
              id: "surface",
              path: "/agent/responsibilities",
            },
          ],
          tool_ids: ["saved-tool"],
          ambiguity: "Cardinality was not supplied.",
        },
      ],
      gaps: [],
    },
    schema_proposal: schema,
    artifacts: [
      {
        id: "catalog",
        kind: "catalog",
        title: "Saved tool catalog",
        digest: "catalog-1",
        created_at,
        payload: {
          tools: [
            {
              id: "saved-tool",
              name: "inspect",
              description: "Inspect supplied records.",
              output_schema: {
                type: "object",
                properties: { value: { type: "string" } },
              },
            },
          ],
        },
      },
      {
        id: "observation",
        kind: "observation",
        title: "Saved record observation",
        digest: "observation-1",
        created_at,
        payload: {
          tool_id: "saved-tool",
          validation: "valid",
          data: { value: "Observed sample value" },
        },
      },
      {
        id: "schema-artifact",
        kind: "schema",
        title: "Schema proposal",
        digest: "schema-1",
        created_at,
        payload: schema,
      },
    ],
  };
}

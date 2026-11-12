"use client";

import { useId, useState, type ReactNode } from "react";
import { FormDialog } from "@/components/form-dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { scopeSections } from "@/features/tasks/scope/scope-definition";
import { ScopeExamples } from "@/features/tasks/scope/scope-examples";
import { ToolCatalog } from "@/features/tools/tool-catalog";
import type { Agent, AgentInput, Connection, TaskScope, Tool } from "@/lib/api";

function initialScope(agent?: Agent): TaskScope {
  return (
    agent?.scope ?? {
      responsibilities: agent?.responsibilities ?? "",
      context_and_rules: "",
      boundaries: "",
      success_criteria: "",
      examples: [],
    }
  );
}

export function AgentDialog({
  trigger,
  initial,
  connections,
  tools,
  onSave,
}: {
  trigger: ReactNode;
  initial?: Agent;
  connections: Connection[];
  tools: Tool[];
  onSave: (configuration: AgentInput) => Promise<void>;
}) {
  const id = useId();
  const [scope, setScope] = useState(() => initialScope(initial));
  const [toolIds, setToolIds] = useState(initial?.tool_ids ?? []);
  const title = initial ? "Edit agent configuration" : "Create agent";
  return (
    <FormDialog
      trigger={trigger}
      title={title}
      description="Enter the agent's task surface. Select the tools that this agent can access."
      submitLabel={initial ? "Save changes" : title}
      className="max-h-[90dvh] overflow-y-auto sm:max-w-5xl"
      onOpen={() => {
        setScope(initialScope(initial));
        setToolIds(initial?.tool_ids ?? []);
      }}
      onSubmit={(data) =>
        onSave({
          name: String(data.get("name")),
          responsibilities: scope.responsibilities,
          scope,
          tool_ids: toolIds,
        })
      }
    >
      <label className="field">
        Name
        <Input
          name="name"
          defaultValue={initial?.name}
          required
          maxLength={100}
          autoComplete="off"
          placeholder="e.g. Research analyst"
        />
      </label>
      <div className="grid min-w-0 items-start gap-6 lg:grid-cols-2">
        <section aria-label="Task surface" className="min-w-0 space-y-5">
          <div>
            <h2 className="section-title">Task surface</h2>
            <p className="mt-2 text-xs leading-6 text-muted-foreground">
              Enter this agent&apos;s work, rules, limits, and expected results.
            </p>
          </div>
          {scopeSections.map(({ key, label, required, guidance }) => (
            <div key={key} className="space-y-2">
              <label htmlFor={`${id}-${key}`} className="text-xs">
                {label}
              </label>
              <p
                id={`${id}-${key}-help`}
                className="text-xs leading-6 text-muted-foreground"
              >
                {required ? "Required. " : "Optional. "}
                {guidance.replace("this task", "this agent")}
              </p>
              <Textarea
                id={`${id}-${key}`}
                required={required}
                maxLength={10000}
                rows={4}
                value={scope[key] ?? ""}
                aria-describedby={`${id}-${key}-help`}
                onChange={(event) =>
                  setScope({ ...scope, [key]: event.target.value })
                }
              />
            </div>
          ))}
          <ScopeExamples
            idPrefix={id}
            examples={scope.examples ?? []}
            onChange={(examples) => setScope({ ...scope, examples })}
          />
        </section>
        <div className="min-w-0">
          <ToolCatalog
            tools={tools}
            connections={connections}
            selection={{
              toolIds,
              savedToolIds: initial?.tool_ids ?? [],
              onChange: setToolIds,
            }}
          />
        </div>
      </div>
    </FormDialog>
  );
}

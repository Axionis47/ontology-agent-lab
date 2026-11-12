"use client";

import { useState, type ReactNode } from "react";
import { FormDialog } from "@/components/form-dialog";
import { Textarea } from "@/components/ui/textarea";
import { ToolCatalog } from "@/features/tools/tool-catalog";
import type {
  Connection,
  Tool,
  TrainingCase,
  TrainingCaseInput,
} from "@/lib/api";

export function CaseDialog({
  initial,
  trigger,
  tools,
  connections,
  onSave,
}: {
  initial?: TrainingCase;
  trigger: ReactNode;
  tools: Tool[];
  connections: Connection[];
  onSave: (input: TrainingCaseInput) => Promise<void>;
}) {
  const [toolIds, setToolIds] = useState(initial?.tool_ids ?? []);
  const removedTools =
    initial?.tool_ids.filter((id) => !tools.some((tool) => tool.id === id)) ??
    [];
  return (
    <FormDialog
      trigger={trigger}
      title={initial ? "Edit test case" : "Add test case"}
      description="Enter a query, select tools, and describe a successful task result."
      submitLabel="Save test case"
      className="max-h-[90dvh] overflow-y-auto sm:max-w-4xl"
      onOpen={() =>
        setToolIds(
          (initial?.tool_ids ?? []).filter((id) =>
            tools.some((tool) => tool.id === id),
          ),
        )
      }
      onSubmit={async (data) => {
        if (!toolIds.length) throw new Error("Select at least one tool.");
        await onSave({
          query: String(data.get("query")),
          task_success: String(data.get("task_success")),
          tool_ids: toolIds,
        });
      }}
    >
      <label className="field">
        Query
        <Textarea
          name="query"
          defaultValue={initial?.query}
          required
          maxLength={16000}
          rows={3}
        />
      </label>
      <label className="field">
        Task success
        <Textarea
          name="task_success"
          defaultValue={initial?.task_success}
          required
          maxLength={8000}
          rows={3}
          placeholder="Describe what the completed task must achieve."
        />
      </label>
      <ToolCatalog
        tools={tools}
        connections={connections}
        selection={{
          toolIds,
          savedToolIds: initial?.tool_ids ?? [],
          onChange: setToolIds,
        }}
      />
      {!!removedTools.length && (
        <p className="text-xs text-muted-foreground">
          {removedTools.length} tools are no longer granted to this agent. This
          edit removes them from the case.
        </p>
      )}
    </FormDialog>
  );
}

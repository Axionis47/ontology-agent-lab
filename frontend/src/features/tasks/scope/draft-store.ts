import type { ScopeExample, TaskScope } from "@/lib/api";
import { scopeSections } from "./scope-definition";

export type ScopeDraft = {
  name: string;
  objective: string;
  scope: Required<TaskScope>;
};

function emptyDraft(): ScopeDraft {
  return {
    name: "",
    objective: "",
    scope: {
      responsibilities: "",
      context_and_rules: "",
      boundaries: "",
      success_criteria: "",
      examples: [],
    },
  };
}

function draftKey(user: string) {
  return `oak:task-scope-draft:${user}`;
}

export function loadDraft(user: string): {
  draft: ScopeDraft;
  recovered: boolean;
  storageError: boolean;
} {
  try {
    const saved = sessionStorage.getItem(draftKey(user));
    if (saved) {
      const value = JSON.parse(saved);
      if (
        typeof value?.name === "string" &&
        typeof value?.objective === "string" &&
        scopeSections.every(
          ({ key }) => typeof value.scope?.[key] === "string",
        ) &&
        Array.isArray(value.scope.examples) &&
        value.scope.examples.every(
          (example: ScopeExample) =>
            example &&
            typeof example.situation === "string" &&
            typeof example.expected_behavior === "string" &&
            typeof example.prohibited_behavior === "string",
        )
      ) {
        return { draft: value, recovered: true, storageError: false };
      }
    }
    return { draft: emptyDraft(), recovered: false, storageError: false };
  } catch {
    return { draft: emptyDraft(), recovered: false, storageError: true };
  }
}

export function saveDraft(user: string, draft: ScopeDraft) {
  sessionStorage.setItem(draftKey(user), JSON.stringify(draft));
}

export function removeDraft(user: string) {
  sessionStorage.removeItem(draftKey(user));
}

"use client";

import styles from "./task-scope.module.css";

import { useSyncExternalStore } from "react";
import { ArrowLeft, ArrowRight, LockKeyhole } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { TaskInput } from "@/lib/api";
import { scopeSections } from "./scope-definition";
import { ScopeFields } from "./scope-fields";
import { ScopeExamples } from "./scope-examples";
import { ScopeText, TaskScopeView } from "./task-scope-view";
import { useTaskScopeForm } from "./use-task-scope-form";

const subscribe = () => () => {};

export function TaskScopeForm(props: {
  user: string;
  onSave: (input: TaskInput) => Promise<void>;
  onCancel: () => void;
}) {
  const ready = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
  return ready ? (
    <ScopeEditor key={props.user} {...props} />
  ) : (
    <p role="status">Loading task form...</p>
  );
}

function ScopeEditor({
  user,
  onSave,
  onCancel,
}: {
  user: string;
  onSave: (input: TaskInput) => Promise<void>;
  onCancel: () => void;
}) {
  const {
    draft,
    recovered,
    storageError,
    review,
    busy,
    error,
    heading,
    update,
    changeStep,
    clearDraft,
    submit,
  } = useTaskScopeForm(user, onSave);

  return (
    <>
      <Button
        variant="ghost"
        disabled={busy}
        onClick={onCancel}
        className="mb-6"
      >
        <ArrowLeft /> Back to workspace
      </Button>
      <div className="page-heading">
        <div>
          <p className="eyebrow text-primary">
            {review ? "02 / REVIEW" : "01 / DEFINE SCOPE"}
          </p>
          <h1 ref={heading} tabIndex={-1}>
            {review ? "Review task scope" : "Define task scope"}
            <span className="text-primary">.</span>
          </h1>
          <p className="page-description">
            {review
              ? "Check the complete description. The scope becomes read-only when you create the task."
              : "Describe the range of work this task must support. Include the rules and relationships that guide its actions."}
          </p>
        </div>
      </div>
      <p role="status" className="mb-6 text-xs leading-6 text-muted-foreground">
        {storageError
          ? "Draft recovery is unavailable in this browser. Keep this page open until you create the task."
          : recovered
            ? "Draft restored. Changes are saved for this user in this browser tab."
            : "Your draft is saved for this user in this browser tab. Required fields are marked below."}
      </p>
      <form onSubmit={submit} aria-label="Task scope" aria-busy={busy}>
        <div className={styles.layout}>
          <nav aria-label="Scope sections" className={styles.navigation}>
            <p className="eyebrow mb-3">TASK SCOPE</p>
            <a href="#scope-name">Name</a>
            <a href="#scope-purpose">Purpose</a>
            {scopeSections.map(({ key, label }) => (
              <a key={key} href={`#scope-${key}`}>
                {label}
              </a>
            ))}
            <a href="#scope-examples">Example cases</a>
            <p className="mt-6 text-xs leading-6 text-muted-foreground">
              Connect MCPs and assign tools after you create the task.
            </p>
          </nav>
          <div className="min-w-0 space-y-6">
            {review ? (
              <>
                <section id="scope-name" className={styles.section}>
                  <h2 className="section-title">Name</h2>
                  <ScopeText text={draft.name} />
                </section>
                <TaskScopeView
                  objective={draft.objective}
                  scope={draft.scope}
                />
              </>
            ) : (
              <>
                <ScopeFields draft={draft} onChange={update} />
                <ScopeExamples
                  examples={draft.scope.examples}
                  onChange={(examples) =>
                    update({ ...draft, scope: { ...draft.scope, examples } })
                  }
                />
              </>
            )}
          </div>
        </div>
        <div className={styles.actions}>
          {error && (
            <p role="alert" className="error-text w-full">
              {error}
            </p>
          )}
          <p className="flex items-center gap-2 text-xs text-muted-foreground">
            <LockKeyhole className="size-4 shrink-0" />
            Scope is read-only after creation.
          </p>
          <div className="flex flex-wrap gap-3">
            <Button
              type="button"
              variant="ghost"
              disabled={busy}
              onClick={() => {
                clearDraft();
                onCancel();
              }}
            >
              Discard draft
            </Button>
            {review && (
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                onClick={() => changeStep(false)}
              >
                Back to form
              </Button>
            )}
            <Button type="submit" disabled={busy}>
              {busy ? "Creating..." : review ? "Create task" : "Review scope"}
              <ArrowRight />
            </Button>
          </div>
        </div>
      </form>
    </>
  );
}

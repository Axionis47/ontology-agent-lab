"use client";

import { useRef, useState, type FormEvent } from "react";
import type { TaskInput } from "@/lib/api";
import {
  loadDraft,
  saveDraft,
  removeDraft,
  type ScopeDraft,
} from "./draft-store";

export function useTaskScopeForm(
  user: string,
  onSave: (input: TaskInput) => Promise<void>,
) {
  const [initial] = useState(() => loadDraft(user));
  const [draft, setDraft] = useState(initial.draft);
  const [storageError, setStorageError] = useState(initial.storageError);
  const [review, setReview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const saving = useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);

  function update(next: ScopeDraft) {
    setDraft(next);
    setError("");
    try {
      saveDraft(user, next);
      setStorageError(false);
    } catch {
      setStorageError(true);
    }
  }

  function changeStep(next: boolean) {
    setReview(next);
    setError("");
    heading.current?.focus();
    window.scrollTo({ top: 0 });
  }

  function clearDraft() {
    try {
      removeDraft(user);
    } catch {
      setStorageError(true);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving.current) return;
    if (!review) {
      const fields = Array.from(event.currentTarget.elements).filter(
        (element): element is HTMLInputElement | HTMLTextAreaElement =>
          element instanceof HTMLInputElement ||
          element instanceof HTMLTextAreaElement,
      );
      const invalid = fields.find(
        (field) => field.required && !field.value.trim(),
      );
      if (invalid) {
        setError("Enter text in each required field.");
        invalid.focus();
        return;
      }
      update({
        ...draft,
        name: draft.name.trim(),
        objective: draft.objective.trim(),
      });
      changeStep(true);
      return;
    }
    saving.current = true;
    setBusy(true);
    setError("");
    try {
      await onSave(draft);
      clearDraft();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      saving.current = false;
      setBusy(false);
    }
  }

  return {
    draft,
    recovered: initial.recovered,
    storageError,
    review,
    busy,
    error,
    heading,
    update,
    changeStep,
    clearDraft,
    submit,
  };
}

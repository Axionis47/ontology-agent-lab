"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { FlaskConical, Play, Square } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormDialog } from "@/components/form-dialog";
import { Checkbox } from "@/components/ui/checkbox";
import {
  api,
  type Agent,
  type Connection,
  type Tool,
  type TrainingDetail,
  type TrainingLimits,
} from "@/lib/api";
import { CaseDialog } from "./case-dialog";
import { RunLimits, trainingDefaults } from "./run-limits";
import { TrainingResults } from "./training-results";
import { useTrainingData } from "./use-training-data";

export function TrainingPanel({
  user,
  taskId,
  agent,
  tools,
  connections,
  runId,
  onRunChange,
  onInference,
}: {
  user: string;
  taskId: string;
  agent: Agent;
  tools: Tool[];
  connections: Connection[];
  runId: string | null;
  onRunChange: (id: string) => void;
  onInference: () => void;
}) {
  const base = `/tasks/${taskId}/agents/${agent.id}/training`;
  const { overview, detail, loadError, reload, loadingOlder, loadOlder } =
    useTrainingData(user, base, runId);
  const [limits, setLimits] = useState<TrainingLimits>(trainingDefaults);
  const [environment, setEnvironment] = useState("");
  const [stableEnvironment, setStableEnvironment] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [casePage, setCasePage] = useState(0);
  const [runPage, setRunPage] = useState(0);
  const pending = useRef<{ key: string; id: string } | null>(null);
  const submitting = useRef(false);
  const disposed = useRef(false);
  useEffect(() => {
    disposed.current = false;
    return () => {
      disposed.current = true;
    };
  }, []);
  const granted = tools.filter((tool) => agent.tool_ids?.includes(tool.id));
  const active = overview?.runs.find((run) =>
    ["running", "stopping"].includes(run.status),
  );
  const cases = overview?.cases ?? [];
  const runs = overview?.runs ?? [];
  const accepted = overview?.accepted_candidate;
  const inferenceReady = overview?.inference_ready === true;

  async function launch(
    path: "runs" | "inference",
    payload: Record<string, unknown>,
  ) {
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    const key = JSON.stringify({ path, payload });
    if (!pending.current || pending.current.key !== key)
      pending.current = { key, id: crypto.randomUUID() };
    try {
      const saved = await api<TrainingDetail>(user, `${base}/${path}`, "POST", {
        ...payload,
        request_id: pending.current.id,
      });
      if (disposed.current) return;
      pending.current = null;
      onRunChange(saved.run.id);
      reload();
    } catch (error) {
      setError((error as Error).message);
      throw error;
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await launch("runs", {
      limits,
      environment_ref: stableEnvironment
        ? "stable"
        : environment.trim() || null,
    }).catch(() => {});
  }

  async function stop() {
    if (!active || submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      await api(user, `${base}/runs/${active.id}/stop`, "POST");
      reload();
    } catch (error) {
      setError((error as Error).message);
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  return (
    <section
      aria-label="Training"
      className="min-w-0 space-y-6 border p-4 sm:p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="mb-2 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Training preparation · Step 02
          </p>
          <h2 className="section-title flex items-center gap-2">
            <FlaskConical className="size-4" />
            Construction and training
          </h2>
          <p className="mt-2 text-xs text-muted-foreground">
            Test task success, inspect the evidence, and train a shared ontology
            harness.
          </p>
        </div>
        <Badge variant="outline">
          {inferenceReady
            ? "Accepted version available"
            : accepted
              ? "Accepted version needs validation"
              : "No accepted version"}
        </Badge>
      </div>
      {(error || loadError) && (
        <p role="alert" className="error-panel">
          {error || loadError}
          <Button variant="ghost" size="sm" onClick={reload}>
            Refresh status
          </Button>
        </p>
      )}
      {!overview && <p role="status">Loading training...</p>}
      {overview?.inference_message && (
        <p
          aria-label="Inference availability"
          className="text-xs text-muted-foreground"
        >
          {overview.inference_message}
        </p>
      )}
      {overview && (
        <>
          <section aria-label="Test cases" className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-sm font-medium">
                Test cases{" "}
                <span className="text-muted-foreground">({cases.length})</span>
              </h3>
              <CaseDialog
                trigger={<Button variant="outline">Add test case</Button>}
                tools={granted}
                connections={connections}
                onSave={async (input) => {
                  await api(user, `${base}/cases`, "POST", input);
                  reload();
                }}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Oak evaluates each complete task from its success description and
              observed evidence. Saved runs keep their original cases.
            </p>
            {!cases.length && (
              <p className="border border-dashed p-5 text-sm">
                Add a test case to begin.
              </p>
            )}
            {cases.slice(casePage * 10, casePage * 10 + 10).map((item) => (
              <article
                key={item.id}
                className="space-y-3 border p-4"
                aria-label={`Test case: ${item.query}`}
              >
                <p className="whitespace-pre-wrap break-words text-sm font-medium">
                  {item.query}
                </p>
                <p className="whitespace-pre-wrap break-words text-xs">
                  <span className="text-muted-foreground">Task success: </span>
                  {item.task_success}
                </p>
                <p className="break-words text-xs text-muted-foreground">
                  Tools:{" "}
                  {item.tool_ids
                    .map(
                      (id) =>
                        tools.find((tool) => tool.id === id)?.name ??
                        "Unavailable tool",
                    )
                    .join(", ")}
                </p>
                <div className="flex gap-2">
                  <CaseDialog
                    initial={item}
                    trigger={
                      <Button size="sm" variant="ghost">
                        Edit test case
                      </Button>
                    }
                    tools={granted}
                    connections={connections}
                    onSave={async (input) => {
                      await api(user, `${base}/cases/${item.id}`, "PUT", input);
                      reload();
                    }}
                  />
                  <FormDialog
                    trigger={
                      <Button size="sm" variant="ghost">
                        Delete test case
                      </Button>
                    }
                    title="Delete test case"
                    description="Remove this case from future runs. Saved runs keep their original input."
                    submitLabel="Delete test case"
                    onSubmit={async () => {
                      await api(user, `${base}/cases/${item.id}`, "DELETE");
                      setCasePage(0);
                      reload();
                    }}
                  >
                    <p className="break-words text-sm">{item.query}</p>
                  </FormDialog>
                </div>
              </article>
            ))}
            <Pages
              page={casePage}
              count={cases.length}
              onChange={setCasePage}
              label="test cases"
            />
          </section>
          <form
            onSubmit={start}
            className="space-y-4 border-t pt-5"
            aria-label="Start training"
          >
            <h3 className="text-sm font-medium">Run training</h3>
            <p className="text-xs text-muted-foreground">
              Each case runs with a basic agent first. Oak then constructs and
              tests the ontology harness, including cases that already passed.
            </p>
            <p className="text-xs">{overview.message}</p>
            <fieldset
              disabled={busy || Boolean(active)}
              className="min-w-0 space-y-4"
            >
              <label className="field">
                Prepared environment reference
                <Input
                  disabled={stableEnvironment}
                  value={environment}
                  onChange={(event) => setEnvironment(event.target.value)}
                  maxLength={200}
                  placeholder="Reference for the supplied test environment"
                />
              </label>
              <label className="flex items-center gap-3 text-xs">
                <Checkbox
                  checked={stableEnvironment}
                  onCheckedChange={(checked) =>
                    setStableEnvironment(checked === true)
                  }
                />
                The environment stays comparable between episodes
              </label>
              <p className="text-xs text-muted-foreground">
                Repeated episodes need a prepared, comparable initial state.
                Selected tools can read or change that environment.
              </p>
              <RunLimits value={limits} onChange={setLimits} />
              <Button
                type="submit"
                disabled={
                  !overview.ready ||
                  !cases.length ||
                  !(Number(limits.cost_usd) > 0)
                }
              >
                <Play className="size-3" />
                Start training
              </Button>
            </fieldset>
          </form>
          {active && (
            <div
              className="flex flex-wrap items-center justify-between gap-3 border p-4 text-xs"
              aria-label="Active run"
            >
              <div>
                <strong>
                  {active.mode === "inference" ? "Inference" : "Training"}{" "}
                  {active.status}
                </strong>
                <p className="mt-2">
                  {active.stage} · {active.message}
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onRunChange(active.id)}
                >
                  View active run
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy || active.status === "stopping"}
                  onClick={stop}
                >
                  <Square className="size-3" />
                  {active.status === "stopping" ? "Stopping..." : "Stop run"}
                </Button>
              </div>
            </div>
          )}
          <section aria-label="Saved runs" className="space-y-3 border-t pt-5">
            <h3 className="text-sm font-medium">
              Saved runs ({runs.length}
              {overview.has_more ? "+" : ""})
            </h3>
            {!runs.length && (
              <p className="text-xs text-muted-foreground">No runs yet.</p>
            )}
            <div className="grid gap-2 sm:grid-cols-2">
              {runs.slice(runPage * 10, runPage * 10 + 10).map((run) => (
                <button
                  key={run.id}
                  type="button"
                  aria-pressed={runId === run.id}
                  onClick={() => onRunChange(run.id)}
                  className={`min-w-0 border p-3 text-left text-xs focus-visible:outline-2 focus-visible:outline-primary ${runId === run.id ? "border-primary bg-primary/5" : ""}`}
                >
                  <span className="font-medium">
                    {run.mode === "inference" ? "Inference" : "Training"} ·{" "}
                    {run.status}
                  </span>
                  <time className="mt-1 block text-muted-foreground">
                    {new Date(run.created_at).toLocaleString()}
                  </time>
                  <span className="mt-1 block break-all text-[10px] text-muted-foreground">
                    {run.id}
                  </span>
                </button>
              ))}
            </div>
            <Pages
              page={runPage}
              count={runs.length}
              onChange={setRunPage}
              label="runs"
            />
            {overview.has_more && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={loadingOlder}
                onClick={() => void loadOlder()}
              >
                {loadingOlder ? "Loading older runs..." : "Load older runs"}
              </Button>
            )}
          </section>
          {runId && !detail && !loadError && (
            <p role="status">Loading selected run...</p>
          )}
          {detail && <TrainingResults key={detail.run.id} detail={detail} />}
          {accepted && (
            <section
              aria-label="Accepted version"
              className="space-y-3 border-t pt-5"
            >
              <h3 className="text-sm font-medium">Try accepted version</h3>
              <p className="break-all text-xs text-muted-foreground">
                Candidate {accepted.id} · {accepted.digest}
              </p>
              <p className="text-xs text-muted-foreground">
                Run a new query with the accepted functions. This does not train
                or change the accepted version.
              </p>
              <Button variant="outline" onClick={onInference}>
                Try a new query
              </Button>
            </section>
          )}
        </>
      )}
    </section>
  );
}

function Pages({
  page,
  count,
  onChange,
  label,
}: {
  page: number;
  count: number;
  onChange: (page: number) => void;
  label: string;
}) {
  if (count <= 10) return null;
  return (
    <nav
      aria-label={`${label} pages`}
      className="flex items-center gap-3 text-xs"
    >
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={page === 0}
        onClick={() => onChange(page - 1)}
      >
        Previous {label}
      </Button>
      <span>
        Page {page + 1} of {Math.ceil(count / 10)}
      </span>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={(page + 1) * 10 >= count}
        onClick={() => onChange(page + 1)}
      >
        Next {label}
      </Button>
    </nav>
  );
}

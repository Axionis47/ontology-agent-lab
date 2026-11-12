"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ToolCatalog } from "@/features/tools/tool-catalog";
import {
  api,
  type Agent,
  type Connection,
  type Tool,
  type TrainingDetail,
} from "@/lib/api";
import { RunLimits, trainingDefaults } from "@/features/training/run-limits";
import { useTrainingData } from "@/features/training/use-training-data";
import { InferenceRun } from "./inference-run";

type Candidate = TrainingDetail["candidates"][number];

export function InferencePanel({
  user,
  taskId,
  agent,
  tools,
  connections,
  runId,
  onRunChange,
}: {
  user: string;
  taskId: string;
  agent: Agent;
  tools: Tool[];
  connections: Connection[];
  runId: string | null;
  onRunChange: (id: string) => void;
}) {
  const base = `/tasks/${taskId}/agents/${agent.id}/training`;
  const { overview, detail, loadError, reload, loadOlder, loadingOlder } =
    useTrainingData(user, base, runId);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState("");
  const active = overview?.runs.find((run) =>
    ["running", "stopping"].includes(run.status),
  );
  const accepted = overview?.accepted_candidate;
  const catalog = tools.filter(
    (tool) =>
      tool.available &&
      agent.tool_ids?.includes(tool.id) &&
      overview?.inference_tool_ids?.includes(tool.id),
  );
  const inferenceDetail = detail?.run.mode === "inference" ? detail : null;
  const runs = (overview?.runs ?? []).filter((run) => run.mode === "inference");
  if (inferenceDetail && !runs.some((run) => run.id === inferenceDetail.run.id))
    runs.push(inferenceDetail.run);
  const pinned = inferenceDetail?.candidates.find(
    (candidate) => candidate.id === inferenceDetail.run.accepted_candidate_id,
  );
  const displayed = runId ? pinned : accepted;

  async function stop() {
    if (!active || active.mode !== "inference" || stopping) return;
    setStopping(true);
    setError("");
    try {
      await api(user, `${base}/runs/${active.id}/stop`, "POST");
      reload();
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setStopping(false);
    }
  }

  return (
    <section
      aria-label="Inference"
      className="min-w-0 space-y-5 border p-4 sm:p-5"
    >
      <div>
        <h2 className="text-lg font-medium">Inference</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Run a new task with the accepted kernel. Follow its calls and observed
          evidence.
        </p>
      </div>
      {(loadError || error) && (
        <p role="alert" className="error-panel">
          {loadError || error}
        </p>
      )}
      {!overview && !loadError && <p role="status">Loading inference...</p>}
      {overview && !overview.inference_ready && (
        <p
          aria-label="Inference availability"
          className="text-sm text-muted-foreground"
        >
          {overview.inference_message ||
            "Accept a kernel in Training before running inference."}
        </p>
      )}
      {accepted ? (
        <InferenceForm
          key={accepted.id}
          candidate={accepted}
          tools={catalog}
          connections={connections}
          ready={overview?.inference_ready === true && !active}
          user={user}
          base={base}
          onStarted={(id) => {
            onRunChange(id);
            reload();
          }}
        />
      ) : (
        overview && <p className="text-xs">No accepted kernel is available.</p>
      )}
      {active && (
        <div className="flex flex-wrap items-center gap-3 border p-3 text-xs">
          <p>
            {active.mode === "inference" ? "Inference" : "Training"}{" "}
            {active.status}. {active.message}
          </p>
          {active.mode === "inference" && (
            <>
              {active.id !== runId && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onRunChange(active.id)}
                >
                  View active run
                </Button>
              )}
              <Button
                size="sm"
                variant="outline"
                disabled={stopping || active.status === "stopping"}
                onClick={stop}
              >
                {stopping || active.status === "stopping"
                  ? "Stopping..."
                  : "Stop run"}
              </Button>
            </>
          )}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <label className="min-w-0 space-y-1 text-xs">
          Saved inference runs
          <select
            className="block max-w-full border bg-background p-2"
            value={runs.some((run) => run.id === runId) ? runId! : ""}
            onChange={(event) => onRunChange(event.target.value)}
          >
            <option value="">New query</option>
            {runs.map((run) => (
              <option key={run.id} value={run.id}>
                {new Date(run.created_at).toLocaleString()} · {run.status} ·{" "}
                {run.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </label>
        {overview?.has_more && (
          <Button
            size="sm"
            variant="ghost"
            disabled={loadingOlder}
            onClick={() => void loadOlder()}
          >
            {loadingOlder ? "Loading..." : "Load older runs"}
          </Button>
        )}
      </div>
      {runId && !detail && !loadError && (
        <p role="status">Loading selected run...</p>
      )}
      {detail && !inferenceDetail && (
        <p>This link refers to a training run. Open it from Training.</p>
      )}
      {inferenceDetail && (
        <div className="space-y-1 text-xs">
          <p role="status" aria-label="Inference status">
            {inferenceDetail.run.status}
          </p>
          <p>{inferenceDetail.run.message}</p>
          <p className="text-muted-foreground">
            Model calls: {inferenceDetail.run.model_calls ?? 0} · MCP calls:{" "}
            {inferenceDetail.run.mcp_calls ?? 0} · Accounted cost: $
            {(inferenceDetail.run.accounted_usd ?? 0).toFixed(5)}
          </p>
        </div>
      )}
      {inferenceDetail && !pinned && (
        <p role="alert">The kernel pinned to this run is unavailable.</p>
      )}
      {displayed && (
        <InferenceRun
          key={`${runId ?? "preview"}:${displayed.id}`}
          detail={inferenceDetail}
          candidate={displayed}
          tools={tools}
        />
      )}
    </section>
  );
}

function InferenceForm({
  candidate,
  tools,
  connections,
  ready,
  user,
  base,
  onStarted,
}: {
  candidate: Candidate;
  tools: Tool[];
  connections: Connection[];
  ready: boolean;
  user: string;
  base: string;
  onStarted: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(tools.map((tool) => tool.id));
  const [limits, setLimits] = useState(trainingDefaults);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef<{ key: string; id: string } | null>(null);
  const submitting = useRef(false);
  const disposed = useRef(false);
  useEffect(() => {
    disposed.current = false;
    return () => {
      disposed.current = true;
    };
  }, []);
  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current || !ready) return;
    if (selected.some((id) => !tools.some((tool) => tool.id === id))) {
      setError("Select tools enabled by the accepted kernel.");
      return;
    }
    const payload = {
      query,
      tool_ids: selected,
      limits,
      accepted_candidate_id: candidate.id,
    };
    const key = JSON.stringify(payload);
    if (pending.current?.key !== key)
      pending.current = { key, id: crypto.randomUUID() };
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      const detail = await api<TrainingDetail>(
        user,
        `${base}/inference`,
        "POST",
        { ...payload, request_id: pending.current.id },
      );
      if (disposed.current) return;
      pending.current = null;
      onStarted(detail.run.id);
    } catch (error) {
      if (!disposed.current) setError((error as Error).message);
    } finally {
      submitting.current = false;
      if (!disposed.current) setBusy(false);
    }
  }
  return (
    <form onSubmit={start} className="space-y-3">
      <p className="break-all text-xs text-muted-foreground">
        Kernel for new queries: {candidate.id}
      </p>
      {error && (
        <p role="alert" className="error-panel">
          {error}
        </p>
      )}
      <fieldset disabled={!ready || busy} className="min-w-0 space-y-3">
        <label className="field">
          Query
          <Textarea
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            required
            maxLength={16000}
            rows={3}
          />
        </label>
        <details className="border p-3 text-xs">
          <summary className="cursor-pointer">
            MCP tools · {selected.length} selected
          </summary>
          <div className="mt-3">
            <ToolCatalog
              tools={tools}
              connections={connections}
              selection={{
                toolIds: selected,
                savedToolIds: tools.map((tool) => tool.id),
                onChange: setSelected,
              }}
            />
          </div>
        </details>
        <details className="border p-3 text-xs">
          <summary className="cursor-pointer">
            Run limits
            {Number(limits.cost_usd) > 0
              ? ` · $${limits.cost_usd} maximum`
              : " · Set a cost limit before running"}
          </summary>
          <div className="mt-3">
            <RunLimits value={limits} onChange={setLimits} inference />
          </div>
        </details>
        <Button
          type="submit"
          disabled={
            !ready ||
            busy ||
            !query.trim() ||
            !selected.length ||
            !(Number(limits.cost_usd) > 0)
          }
        >
          {busy ? "Starting inference..." : "Run inference"}
        </Button>
      </fieldset>
    </form>
  );
}

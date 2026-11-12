"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Check,
  CircleHelp,
  LoaderCircle,
  Pause,
  Play,
  RefreshCw,
  Search,
  Square,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  api,
  type Agent,
  type DiscoveryDetail,
  type DiscoveryLimits,
  type DiscoveryOverview,
  type EvidenceRef,
  type Tool,
} from "@/lib/api";
import type { Selection } from "./schema-adapter";
import { SchemaViewer } from "./schema-viewer";
import { DiscoveryReview } from "./discovery-review";
import { DiscoveryModeling } from "./discovery-modeling";
import { DiscoveryInspector, EvidenceLinks } from "./discovery-inspector";

const TraceMap = dynamic(() => import("./trace-map"), {
  ssr: false,
  loading: () => <p role="status">Loading evidence map...</p>,
});
const stages = ["inputs", "tools", "exploration", "checks"];
const labels: Record<string, string> = {
  inputs: "Inputs",
  tools: "Tools",
  exploration: "Explore and revise",
  checks: "Checks",
};
const limitFields = [
  ["cost_usd", "Maximum model cost (USD)", "0.01"],
  ["mcp_calls", "Maximum MCP calls", "1"],
  ["model_calls", "Maximum model calls", "1"],
  ["active_seconds", "Maximum active runtime (seconds)", "1"],
  ["clarification_rounds", "Maximum clarification rounds", "1"],
] as const;
const defaults: DiscoveryLimits = {
  cost_usd: "",
  mcp_calls: 12,
  model_calls: 14,
  active_seconds: 600,
  clarification_rounds: 2,
};
const money = (value: number) => `$${value.toFixed(5)}`;
const pretty = (value: unknown) => JSON.stringify(value, null, 2);

export function DiscoveryPanel({
  user,
  taskId,
  agent,
  tools,
}: {
  user: string;
  taskId: string;
  agent: Agent;
  tools: Tool[];
}) {
  const base = `/tasks/${taskId}/agents/${agent.id}/discovery`;
  const [overview, setOverview] = useState<DiscoveryOverview | null>(null);
  const [detail, setDetail] = useState<DiscoveryDetail | null>(null);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [environment, setEnvironment] = useState("");
  const [limits, setLimits] = useState<DiscoveryLimits>(defaults);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tab, setTab] = useState("overview");
  const [search, setSearch] = useState("");
  const [inspection, setInspection] = useState<Selection | null>(null);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [showActivity, setShowActivity] = useState(false);
  const initialized = useRef<string | null>(null);
  const pendingRequest = useRef<{ key: string; id: string } | null>(null);
  const grantedTools = tools.filter((tool) =>
    agent.tool_ids?.includes(tool.id),
  );
  const run = detail?.run;
  const executing = run?.status === "running" || run?.status === "pausing";
  const paused = run?.status === "paused";
  const terminal = run?.status === "completed" || run?.status === "stopped";
  const pendingQuestions =
    detail?.questions.filter((q) => q.answer === null) ?? [];

  const reload = useCallback(async () => {
    const next = await api<DiscoveryOverview>(
      user,
      `${base}?offset=${historyOffset}`,
    );
    setOverview(next);
    const id = selectedRun || (!creating ? next.runs[0]?.id : null);
    if (id) {
      const saved = await api<DiscoveryDetail>(user, `${base}/runs/${id}`);
      setDetail(saved);
      if (initialized.current !== id) {
        initialized.current = id;
        setEnvironment(saved.run.environment);
        setLimits(saved.run.limits);
        setAnswers({});
        setInspection(null);
      }
    } else setDetail(null);
  }, [user, base, selectedRun, creating, historyOffset]);

  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        await reload();
        if (!disposed) setLoadError(null);
      } catch (e) {
        if (!disposed) setLoadError((e as Error).message);
      }
      if (!disposed) timer = setTimeout(refresh, executing ? 1000 : 5000);
    }
    void refresh();
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [reload, executing]);

  async function action(name: "start" | "resume" | "pause" | "stop") {
    setBusy(true);
    setError(null);
    try {
      const payload =
        name === "start"
          ? { environment, limits }
          : name === "resume"
            ? { expected_revision: run?.revision, answers, limits }
            : undefined;
      const key = pretty({ name, run: run?.id, payload });
      if (!pendingRequest.current || pendingRequest.current.key !== key)
        pendingRequest.current = { key, id: crypto.randomUUID() };
      const body = payload
        ? { ...payload, request_id: pendingRequest.current.id }
        : undefined;
      const path =
        name === "start" ? `${base}/runs` : `${base}/runs/${run?.id}/${name}`;
      const saved = await api<DiscoveryDetail>(user, path, "POST", body);
      pendingRequest.current = null;
      setDetail(saved);
      setSelectedRun(saved.run.id);
      setCreating(false);
      setLimits(saved.run.limits);
      setAnswers({});
      initialized.current = saved.run.id;
      setOverview(await api<DiscoveryOverview>(user, base));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function openRef(ref: EvidenceRef) {
    setInspection({ kind: "evidence", ref });
  }

  function inspect(title: string, value: unknown, id = title) {
    setInspection({ kind: "record", id, title, value });
  }
  function matches(value: unknown) {
    return pretty(value).toLowerCase().includes(search.toLowerCase());
  }
  const validation = detail?.artifacts
    .filter((a) => a.kind === "validation")
    .at(-1);
  const catalog = detail?.artifacts.filter((a) => a.kind === "catalog").at(-1);
  const artifactTools = catalog?.payload.tools;
  const schema = detail?.schema_proposal;
  const recentEvents = detail?.events.filter(matches).slice().reverse() ?? [];

  return (
    <section
      aria-label="Discovery"
      className="min-w-0 space-y-5 border p-4 sm:p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="mb-2 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Training preparation · Step 01
          </p>
          <h2 className="section-title flex items-center gap-2">
            <Search className="size-4" />
            Discovery
          </h2>
          <p className="mt-2 text-xs text-muted-foreground">
            Understand the task, inspect its tools, and build an evidence-linked
            proposal for the next step.
          </p>
        </div>
        <Badge role="status" variant="outline">
          {creating || !run
            ? "Not started"
            : run.status === "completed"
              ? run.reason === "gaps"
                ? "Completed with gaps"
                : "Discovery complete"
              : run.status === "paused"
                ? "Paused for review"
                : run.status === "pausing"
                  ? "Pausing"
                  : run.status === "running"
                    ? "Running"
                    : "Stopped"}
        </Badge>
      </div>

      {(error || loadError) && (
        <p role="alert" className="error-panel">
          {error || loadError}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setError(null);
              void reload().catch((e) => setError(e.message));
            }}
          >
            Refresh status
          </Button>
        </p>
      )}
      {!overview && <p className="text-xs">Loading discovery...</p>}
      {overview && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            {overview.runs.length > 0 && (
              <details className="min-w-0 flex-1 text-xs">
                <summary className="w-fit py-2 text-muted-foreground">
                  Run history ({overview.runs.length}
                  {overview.has_more ? "+" : ""})
                </summary>
                <label className="flex min-w-0 flex-1 items-center gap-2 text-xs">
                  <span className="sr-only">Run history</span>
                  <select
                    aria-label="Run history"
                    className="min-w-0 max-w-full border bg-background p-2"
                    value={creating ? "" : selectedRun || run?.id || ""}
                    onChange={(e) => {
                      setCreating(false);
                      setSelectedRun(e.target.value);
                      setError(null);
                    }}
                  >
                    <option value="" disabled>
                      Select a run
                    </option>
                    {overview.runs.map((r) => (
                      <option key={r.id} value={r.id}>
                        {new Date(r.created_at).toLocaleString()} · {r.status}
                      </option>
                    ))}
                  </select>
                </label>
              </details>
            )}
            {historyOffset > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  setHistoryOffset(Math.max(0, historyOffset - 20))
                }
              >
                Newer runs
              </Button>
            )}
            {overview.has_more && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setHistoryOffset(historyOffset + 20)}
              >
                Older runs
              </Button>
            )}
            {terminal && !creating && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setCreating(true);
                  setSelectedRun(null);
                  setDetail(null);
                  setLimits(defaults);
                  initialized.current = null;
                }}
              >
                Start new run
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              aria-label="Refresh discovery status"
              onClick={() => void reload().catch((e) => setError(e.message))}
            >
              <RefreshCw className="size-3" />
            </Button>
          </div>

          {(!run || creating) && (
            <div className="space-y-3 text-xs">
              <p>
                <strong>Saved task surface:</strong>{" "}
                {agent.scope?.responsibilities || agent.responsibilities}
              </p>
              <p>
                <strong>Granted tools:</strong> {grantedTools.length} selected
              </p>
              <label className="block space-y-2">
                <span>Supplied test environment</span>
                <Input
                  value={environment}
                  onChange={(e) => setEnvironment(e.target.value)}
                  placeholder="For example, team test workspace"
                  maxLength={200}
                />
              </label>
              <p className="text-muted-foreground">
                Start permits read and write probes through these grants within
                the saved task boundaries. Oak does not create or verify
                isolation.
              </p>
            </div>
          )}

          {(!run || creating || paused) && (
            <fieldset
              disabled={busy || (Boolean(run) && !paused && !creating)}
              className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
            >
              <legend className="mb-3 text-xs font-medium">
                Run limits{paused ? " · increase limits, then resume" : ""}
              </legend>
              {limitFields.map(([key, label, step]) => (
                <label key={key} className="space-y-2 text-xs">
                  <span>{label}</span>
                  <Input
                    type="number"
                    aria-label={label}
                    min={
                      paused && run
                        ? Number(run.limits[key])
                        : key === "clarification_rounds"
                          ? 0
                          : key === "cost_usd"
                            ? 0.000001
                            : 1
                    }
                    max={Number(overview.ceilings[key])}
                    step={step}
                    value={limits[key] ?? ""}
                    onChange={(e) =>
                      setLimits((previous) => ({
                        ...previous,
                        [key]:
                          key === "cost_usd"
                            ? e.target.value
                            : Number(e.target.value),
                      }))
                    }
                  />
                  <span className="block text-muted-foreground">
                    Backend ceiling: {overview.ceilings[key]}
                  </span>
                </label>
              ))}
            </fieldset>
          )}

          {run && !creating && (
            <>
              <div
                className="grid gap-2 border-y py-3 text-xs sm:grid-cols-2 lg:grid-cols-3"
                aria-label="Discovery counters"
              >
                <p>
                  Accounted: {money(run.accounted_usd)} / $
                  {Number(run.limits.cost_usd).toFixed(2)}
                </p>
                <p>Reserved: {money(run.reserved_usd)}</p>
                <p>Remaining: {money(run.remaining_usd)}</p>
                <p>
                  MCP calls: {run.mcp_calls} / {run.limits.mcp_calls}
                </p>
                <p>
                  Model calls: {run.model_calls} / {run.limits.model_calls}
                </p>
                <p>
                  Active time: {Math.floor(run.active_ms / 1000)} /{" "}
                  {run.limits.active_seconds} seconds
                </p>
                <p>
                  Clarification rounds: {run.clarification_rounds} /{" "}
                  {run.limits.clarification_rounds}
                </p>
              </div>
              <ol
                aria-label="Discovery stages"
                className="flex flex-wrap gap-x-4 gap-y-2 text-xs"
              >
                {stages.map((stage, index) => (
                  <li
                    key={stage}
                    className={`flex items-center gap-2 border-b-2 pb-2 ${run.stage === stage ? "border-primary text-primary" : "border-transparent text-muted-foreground"}`}
                    aria-current={run.stage === stage ? "step" : undefined}
                  >
                    {index < stages.indexOf(run.stage) ||
                    run.status === "completed" ? (
                      <Check className="size-3" />
                    ) : executing && run.stage === stage ? (
                      <LoaderCircle className="size-3 animate-spin" />
                    ) : (
                      <span className="size-3 rounded-full border" />
                    )}
                    {labels[stage]}
                  </li>
                ))}
              </ol>
              {run.message && (
                <p className="border-l-2 border-primary pl-3 text-sm">
                  {run.message}
                </p>
              )}
              {run.outdated && (
                <p role="alert" className="error-panel">
                  This run belongs to an earlier configuration. Its evidence
                  remains inspectable. Start a new run after ending any
                  unfinished run.
                </p>
              )}
            </>
          )}

          {paused && pendingQuestions.length > 0 && (
            <div
              className="space-y-4 border p-4"
              aria-label="Discovery questions"
            >
              <h3 className="flex items-center gap-2 text-sm">
                <CircleHelp className="size-4" />
                Questions for you
              </h3>
              {pendingQuestions.map((q) => (
                <div key={q.id} className="space-y-2">
                  <label
                    htmlFor={`answer-${q.id}`}
                    className="text-sm font-medium"
                  >
                    {q.question.text}
                  </label>
                  <p className="text-xs text-muted-foreground">
                    {q.question.why_needed}
                  </p>
                  {q.question.unresolved_detail && (
                    <p className="text-xs">
                      Still unresolved: {q.question.unresolved_detail}
                    </p>
                  )}
                  <EvidenceLinks refs={q.question.evidence} onOpen={openRef} />
                  {(q.question.options ?? []).length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {(q.question.options ?? []).map((option) => (
                        <Button
                          key={option}
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            setAnswers((a) => ({ ...a, [q.id]: option }))
                          }
                        >
                          {option}
                        </Button>
                      ))}
                    </div>
                  )}
                  <Textarea
                    id={`answer-${q.id}`}
                    value={answers[q.id] || ""}
                    onChange={(e) =>
                      setAnswers((a) => ({ ...a, [q.id]: e.target.value }))
                    }
                    maxLength={10000}
                  />
                </div>
              ))}
              <p className="text-xs text-muted-foreground">
                Answers clarify intent. They do not prove a tool capability or a
                write effect. Typing does not resume discovery.
              </p>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            {(!run || creating) && (
              <Button
                disabled={
                  busy ||
                  !overview.ready ||
                  !environment.trim() ||
                  !(Number(limits.cost_usd) > 0)
                }
                onClick={() => void action("start")}
              >
                <Play />
                Start discovery
              </Button>
            )}
            {run?.status === "running" && (
              <Button
                disabled={busy}
                variant="outline"
                onClick={() => void action("pause")}
              >
                <Pause />
                Pause
              </Button>
            )}
            {paused && (
              <Button
                disabled={
                  busy ||
                  run?.outdated ||
                  pendingQuestions.some((q) => !answers[q.id]?.trim())
                }
                onClick={() => void action("resume")}
              >
                <Play />
                {pendingQuestions.length
                  ? "Answer and resume"
                  : "Resume discovery"}
              </Button>
            )}
            {run && !terminal && !creating && (
              <Button
                disabled={busy || run.reason === "stop_requested"}
                variant="outline"
                onClick={() => void action("stop")}
              >
                <Square />
                Stop
              </Button>
            )}
            {busy && (
              <LoaderCircle
                aria-label="Saving discovery action"
                className="size-4 animate-spin self-center"
              />
            )}
          </div>
          {!overview.ready && (!run || creating) && (
            <p className="text-xs text-muted-foreground">
              {overview.blocked_reason}
            </p>
          )}
          {(executing || paused) && (
            <p className="text-xs text-muted-foreground">
              Pause prevents the next call. A dispatched call can still finish.
              Stop does not undo external writes. Resume retains all counters.
            </p>
          )}
        </>
      )}

      {detail && !creating && (
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="h-auto! w-full flex-wrap justify-start gap-1">
            {[
              ["overview", "Overview"],
              ["tools", "Tools and probes"],
              ["requirements", "Requirements (R₀)"],
              ["schema", "Schema (S₀)"],
              ["trace", "Evidence map"],
              ["review", "Review"],
            ].map(([value, label]) => (
              <TabsTrigger
                key={value}
                value={value}
                className="h-8 flex-none px-2"
              >
                {label}
              </TabsTrigger>
            ))}
          </TabsList>
          {!["schema", "trace", "review"].includes(tab) && (
            <div className="my-4">
              <Input
                aria-label="Filter discovery records"
                placeholder="Filter discovery records"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          )}
          <TabsContent value="overview" className="space-y-4">
            <div
              className="grid gap-3 sm:grid-cols-3"
              aria-label="Discovery findings"
            >
              {[
                {
                  title: "Tool evidence",
                  value: detail.calls.filter((call) => call.kind === "mcp")
                    .length,
                  description: "Saved probe attempts and responses",
                  tab: "tools",
                },
                {
                  title: "Requirements (R₀)",
                  value: detail.requirements?.requirements.length ?? 0,
                  description: "What the agent must support",
                  tab: "requirements",
                },
                {
                  title: "Schema (S₀)",
                  value: schema?.entities?.length ?? 0,
                  description: "Proposed entities and source mappings",
                  tab: "schema",
                },
              ].map((finding) => (
                <button
                  key={finding.tab}
                  className="border bg-muted/20 p-4 text-left transition-colors hover:border-primary/50 focus-visible:outline-2 focus-visible:outline-primary"
                  onClick={() => setTab(finding.tab)}
                >
                  <span className="text-xs text-muted-foreground">
                    {finding.title}
                  </span>
                  <span className="my-2 block text-3xl tabular-nums text-primary">
                    {finding.value}
                  </span>
                  <span className="text-xs leading-relaxed text-muted-foreground">
                    {finding.description}
                  </span>
                </button>
              ))}
            </div>
            <div className="space-y-3 border p-4 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h3 className="font-medium">Inputs for this discovery</h3>
                <button
                  className="text-primary underline underline-offset-4"
                  onClick={() =>
                    inspect(
                      "Saved task, boundaries, and tool grants",
                      detail.inputs,
                    )
                  }
                >
                  Inspect saved task and grants
                </button>
              </div>
              <p className="break-words leading-relaxed text-muted-foreground">
                Environment: {detail.run.environment}
              </p>
              <p className="leading-relaxed text-muted-foreground">
                Discovery produces requirements and a schema proposal.
                Construction, training, and evaluation follow in later steps.
              </p>
            </div>
            <details className="border p-3 text-xs">
              <summary className="cursor-pointer">
                Saved evidence and proposal history ({detail.artifacts.length})
              </summary>
              <div className="mt-3 max-h-64 space-y-2 overflow-auto">
                {detail.artifacts
                  .filter(matches)
                  .slice()
                  .reverse()
                  .map((artifact) => (
                    <button
                      key={artifact.id}
                      className="block w-full border-b py-2 text-left text-primary"
                      onClick={() => inspect(artifact.title, artifact)}
                    >
                      {artifact.title} ·{" "}
                      {new Date(artifact.created_at).toLocaleTimeString()}
                    </button>
                  ))}
              </div>
            </details>
            {validation && (
              <button
                className="w-full border p-3 text-left text-sm"
                onClick={() => inspect(validation.title, validation.payload)}
              >
                Package checks:{" "}
                {validation.payload.ready_for_construction
                  ? "references and coverage checks passed"
                  : "gaps remain"}
                <span className="mt-1 block text-xs text-muted-foreground">
                  Proposals remain untrained. Inspect checks and unresolved
                  gaps.
                </span>
              </button>
            )}
            <div
              className="grid gap-3 sm:grid-cols-2"
              aria-label="Discovery review summary"
            >
              <button
                className="border p-3 text-left text-xs"
                onClick={() => setTab("review")}
              >
                <strong className="block">Questions for you</strong>
                <span className="mt-1 block text-muted-foreground">
                  {pendingQuestions.length} awaiting an answer ·{" "}
                  {detail.questions.length - pendingQuestions.length} answered
                </span>
              </button>
              <button
                className="border p-3 text-left text-xs"
                onClick={() => setTab("review")}
              >
                <strong className="block">Evidence gaps</strong>
                <span className="mt-1 block text-muted-foreground">
                  {(schema?.gaps?.length ?? 0) +
                    (detail.requirements?.gaps?.length ?? 0)}{" "}
                  recorded · inspect missing evidence and capabilities
                </span>
              </button>
            </div>
            <div className="flex items-center justify-between gap-3 pt-2">
              <h3 className="text-sm">Recent activity</h3>
              {recentEvents.length > 5 && (
                <Button
                  variant="ghost"
                  size="sm"
                  aria-expanded={showActivity}
                  onClick={() => setShowActivity((value) => !value)}
                >
                  {showActivity
                    ? "Show recent activity"
                    : `View all activity (${recentEvents.length})`}
                </Button>
              )}
            </div>
            <ol
              aria-label="Discovery activity"
              className={`space-y-2 ${showActivity ? "max-h-80 overflow-y-auto" : ""}`}
            >
              {recentEvents
                .slice(0, showActivity ? undefined : 5)
                .map((event) => (
                  <li
                    key={event.sequence}
                    className="flex gap-3 border-b py-2 text-xs"
                  >
                    <time className="shrink-0 text-muted-foreground">
                      {new Date(event.created_at).toLocaleTimeString()}
                    </time>
                    <span>{event.message}</span>
                  </li>
                ))}
            </ol>
          </TabsContent>
          <TabsContent value="tools" className="space-y-4">
            {detail.artifacts
              .filter(
                (a) =>
                  ["capabilities", "confirmation"].includes(a.kind) &&
                  matches(a),
              )
              .map((artifact) => (
                <button
                  key={artifact.id}
                  className="block w-full border p-3 text-left text-xs"
                  onClick={() => inspect(artifact.title, artifact.payload)}
                >
                  {artifact.title}
                  {artifact.kind === "confirmation"
                    ? ` · ${artifact.payload.matched ? "compared fields match" : "comparison differs"}`
                    : " · declarations and observations"}
                </button>
              ))}
            <button
              className="text-xs text-primary underline"
              disabled={!catalog}
              onClick={() => catalog && inspect(catalog.title, catalog.payload)}
            >
              Inspect native catalog, schemas, and annotations
            </button>
            <div
              role="region"
              aria-label="Saved discovery tools"
              tabIndex={0}
              className="max-h-[min(420px,50dvh)] space-y-2 overflow-y-auto overscroll-contain focus-visible:outline-2 focus-visible:outline-primary"
            >
              {Array.isArray(artifactTools) &&
                artifactTools.filter(matches).map((tool, i) => {
                  const t = tool as Record<string, unknown>;
                  return (
                    <button
                      key={i}
                      className="block w-full border p-3 text-left text-xs"
                      onClick={() =>
                        setInspection({ kind: "tool", id: String(t.id) })
                      }
                    >
                      <strong>{String(t.name)}</strong>
                      <span className="ml-2 text-muted-foreground">
                        Declared contract
                      </span>
                      <p className="mt-2 line-clamp-2 break-words">
                        {String(t.description)}
                      </p>
                      <p className="mt-2">
                        Output schema:{" "}
                        {t.output_schema ? "available" : "not supplied"}
                      </p>
                    </button>
                  );
                })}
            </div>
            {detail.calls.filter(matches).map((call) => (
              <article key={call.id} className="space-y-2 border p-3 text-xs">
                <div className="flex flex-wrap justify-between gap-2">
                  <strong>{call.purpose}</strong>
                  <Badge variant="outline">
                    {call.kind} · {call.status}
                  </Badge>
                </div>
                <p>
                  {call.effect && `Proposed effect: ${call.effect} · `}
                  {call.duration_ms ?? 0} ms
                  {call.error_code && ` · ${call.error_code}`}
                </p>
                <div className="flex flex-wrap gap-3">
                  <button
                    className="text-primary underline"
                    onClick={() => inspect("Call request", call)}
                  >
                    Inspect request and accounting
                  </button>
                  {call.response_artifact_id && (
                    <button
                      className="text-primary underline"
                      onClick={() =>
                        openRef({
                          source: "artifact",
                          id: call.response_artifact_id!,
                          path: "",
                        })
                      }
                    >
                      Inspect response
                    </button>
                  )}
                </div>
              </article>
            ))}
            {detail.calls.length === 0 && (
              <p className="text-xs text-muted-foreground">
                No calls have been dispatched.
              </p>
            )}
          </TabsContent>
          <TabsContent value="requirements" className="space-y-3">
            {detail.requirements?.requirements
              .filter(matches)
              .map((requirement) => (
                <article key={requirement.id} className="border p-3 text-sm">
                  <button
                    className="text-left"
                    onClick={() =>
                      setInspection({ kind: "requirement", id: requirement.id })
                    }
                  >
                    <span className="mr-2 text-primary">{requirement.id}</span>
                    {requirement.statement}
                  </button>
                  {requirement.ambiguity && (
                    <p className="mt-2 text-xs">
                      Unresolved: {requirement.ambiguity}
                    </p>
                  )}
                  <EvidenceLinks refs={requirement.evidence} onOpen={openRef} />
                </article>
              ))}
            {!!detail.requirements?.gaps?.length && (
              <button
                className="inspection-link text-xs"
                onClick={() => setTab("review")}
              >
                Review evidence gaps
              </button>
            )}
            {!detail.requirements && (
              <p className="text-xs text-muted-foreground">
                Requirement proposals appear during exploration and change with
                new evidence.
              </p>
            )}
          </TabsContent>
          <TabsContent value="schema" className="min-w-0">
            <SchemaViewer
              detail={detail}
              selection={inspection}
              onSelect={setInspection}
              onReview={() => setTab("review")}
            />
            <DiscoveryModeling detail={detail} onInspect={setInspection} />
          </TabsContent>
          <TabsContent value="review">
            <DiscoveryReview
              detail={detail}
              onInspect={setInspection}
              onAnswer={() => {
                document
                  .getElementById(`answer-${pendingQuestions[0]?.id}`)
                  ?.focus();
              }}
            />
          </TabsContent>
          <TabsContent value="trace">
            {tab === "trace" && (
              <TraceMap
                detail={detail}
                selection={inspection}
                onInspect={setInspection}
                onReview={() => setTab("review")}
                onSchema={() => setTab("schema")}
              />
            )}
          </TabsContent>
        </Tabs>
      )}

      {detail && (
        <DiscoveryInspector
          key={detail.run.id}
          detail={detail}
          selection={inspection}
          onSelect={setInspection}
          onClose={() => setInspection(null)}
        />
      )}
    </section>
  );
}

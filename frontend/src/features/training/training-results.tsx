"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { TrainingDetail, TrainingEpisode } from "@/lib/api";
import { HarnessLedger } from "./harness-ledger";
import { EpisodeDetail } from "./episode-detail";
import { SavedData, object, text } from "./saved-data";

export function TrainingResults({ detail }: { detail: TrainingDetail }) {
  const { run, episodes, candidates, events } = detail;
  const [round, setRound] = useState<number | null>(null);
  const [episodeId, setEpisodeId] = useState<string | null>(null);
  const [candidateId, setCandidateId] = useState<string | null>(null);
  const [casePage, setCasePage] = useState(0);
  const [activityOpen, setActivityOpen] = useState(false);
  const rounds = [
    ...new Set(
      episodes
        .filter((episode) => episode.stage === "harness")
        .map((episode) => episode.round_index),
    ),
  ].sort((a, b) => a - b);
  const selectedRound = round ?? rounds[0];
  const caseIds = [...new Set(episodes.map((episode) => episode.case_id))];
  const selectedEpisode = episodes.find((episode) => episode.id === episodeId);
  const candidate = candidates.find((item) => item.id === candidateId);
  const priorCandidate = candidate?.patch
    ? candidates.find((item) => item.digest === candidate.patch?.base_digest)
    : undefined;
  return (
    <section
      aria-label="Run results"
      className="min-w-0 space-y-5 border-t pt-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-medium">
          {run.mode === "inference" ? "Inference result" : "Training results"}
        </h3>
        <Badge variant="outline" role="status">
          {run.status.replaceAll("_", " ")}
        </Badge>
      </div>
      <p className="text-xs">
        {run.stage} · {run.message}
      </p>
      <p className="text-xs text-muted-foreground">
        Model calls: {run.model_calls ?? 0} / {run.limits.model_calls} · MCP
        calls: {run.mcp_calls ?? 0} / {run.limits.mcp_calls} · Accounted cost: $
        {(run.accounted_usd ?? 0).toFixed(5)}
      </p>
      <p className="break-all text-[11px] text-muted-foreground">
        Run {run.id}
        {run.discovery_run_id && <> · Discovery {run.discovery_run_id}</>}
      </p>
      <SavedData
        title="Saved run inputs and limits"
        value={{
          input_digest: run.input_digest,
          cases: run.cases,
          limits: run.limits,
          environment_ref: run.environment_ref,
          evaluator_version: run.evaluator_version,
        }}
      />
      {!!rounds.length && (
        <label className="flex flex-wrap items-center gap-3 text-xs">
          Harness round
          <select
            className="max-w-full border bg-background p-2"
            value={selectedRound}
            onChange={(event) => setRound(Number(event.target.value))}
          >
            {rounds.map((value) => (
              <option key={value} value={value}>
                Round {value}
              </option>
            ))}
          </select>
        </label>
      )}
      {!episodes.length && (
        <p className="text-xs text-muted-foreground">
          No episode result has been recorded yet.
        </p>
      )}
      {caseIds.slice(casePage * 10, casePage * 10 + 10).map((caseId) => {
        const caseEpisodes = episodes.filter(
          (episode) => episode.case_id === caseId,
        );
        const snapshot = caseEpisodes[0].case_snapshot;
        const baseline = caseEpisodes.find(
          (episode) => episode.stage === "baseline",
        );
        const harness = caseEpisodes.find(
          (episode) =>
            episode.stage === "harness" &&
            episode.round_index === selectedRound,
        );
        const inference = caseEpisodes.find(
          (episode) => episode.stage === "inference",
        );
        return (
          <article
            key={caseId}
            className="min-w-0 space-y-3 border p-4"
            aria-label={`Case result: ${text(snapshot.query, caseId)}`}
          >
            <p className="whitespace-pre-wrap break-words text-sm font-medium">
              {text(snapshot.query, caseId)}
            </p>
            {Boolean(snapshot.task_success) && (
              <p className="whitespace-pre-wrap break-words text-xs text-muted-foreground">
                Task success: {text(snapshot.task_success)}
              </p>
            )}
            <div className={inference ? "" : "grid gap-3 sm:grid-cols-2"}>
              {inference ? (
                <Outcome
                  label="Inference"
                  episode={inference}
                  onInspect={setEpisodeId}
                />
              ) : (
                <>
                  <Outcome
                    label="Basic agent baseline"
                    episode={baseline}
                    onInspect={setEpisodeId}
                  />
                  <Outcome
                    label={
                      selectedRound === undefined
                        ? "Ontology harness"
                        : `Ontology harness · round ${selectedRound}`
                    }
                    episode={harness}
                    onInspect={setEpisodeId}
                  />
                </>
              )}
            </div>
          </article>
        );
      })}
      {caseIds.length > 10 && (
        <div className="flex gap-3">
          <Button
            size="sm"
            variant="ghost"
            disabled={casePage === 0}
            onClick={() => setCasePage(casePage - 1)}
          >
            Previous results
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={(casePage + 1) * 10 >= caseIds.length}
            onClick={() => setCasePage(casePage + 1)}
          >
            Next results
          </Button>
        </div>
      )}
      {selectedEpisode && (
        <EpisodeDetail
          key={`${run.id}:${selectedEpisode.round_index}:${selectedEpisode.id}`}
          episode={selectedEpisode}
          events={events.filter(
            (event) => event.episode_id === selectedEpisode.id,
          )}
          onClose={() => setEpisodeId(null)}
        />
      )}
      <section aria-label="Candidate versions" className="space-y-3">
        <h4 className="text-sm font-medium">Candidate versions and repairs</h4>
        {!candidates.length && (
          <p className="text-xs text-muted-foreground">
            Construction has not recorded a candidate.
          </p>
        )}
        <div className="flex max-h-64 flex-col gap-2 overflow-y-auto">
          {candidates.map((item, index) => (
            <button
              type="button"
              key={item.id}
              aria-pressed={candidateId === item.id}
              className={`min-w-0 border p-3 text-left text-xs focus-visible:outline-2 focus-visible:outline-primary ${candidateId === item.id ? "border-primary" : ""}`}
              onClick={() => setCandidateId(item.id)}
            >
              <span>
                Candidate {index + 1} · {item.status} ·{" "}
                {item.patch ? "Targeted repair" : "Initial construction"}
              </span>
              <span className="mt-2 block break-all text-muted-foreground">
                {item.id}
              </span>
            </button>
          ))}
        </div>
        {candidate && (
          <section
            key={candidate.id}
            className="space-y-3"
            aria-label="Candidate inspection"
          >
            <p className="break-all text-xs">
              Candidate {candidate.id} · {candidate.digest}
            </p>
            <SavedData
              title="Acceptance decision and checks"
              value={candidate.decision}
              open
            />
            {candidate.patch && (
              <SavedData
                title="Diagnosed failure, evidence, and targeted patch"
                value={candidate.patch}
                open
              />
            )}
            {candidate.patch && (
              <SavedData
                title="Exact before and after changes"
                value={{
                  previous_candidate_id: priorCandidate?.id ?? null,
                  changes: Array.isArray(candidate.patch.changes)
                    ? candidate.patch.changes.map((value) => {
                        const change = object(value);
                        const collection = text(change.collection);
                        const before =
                          priorCandidate?.payload[collection] ??
                          object(priorCandidate?.payload.schema)[collection];
                        const after =
                          candidate.payload[collection] ??
                          object(candidate.payload.schema)[collection];
                        return {
                          collection,
                          id: change.id,
                          operation: change.op,
                          before: Array.isArray(before)
                            ? (before.find(
                                (item) => object(item).id === change.id,
                              ) ?? null)
                            : null,
                          after: Array.isArray(after)
                            ? (after.find(
                                (item) => object(item).id === change.id,
                              ) ?? null)
                            : null,
                        };
                      })
                    : [],
                  prior_version_available: Boolean(priorCandidate),
                }}
                open
              />
            )}
            {[
              "requirements",
              "schema",
              "formal_axioms",
              "request_fields",
              "operation_bindings",
              "requirement_coverage",
              "mappings",
              "constraints",
              "functions",
            ]
              .filter((key) => candidate.payload[key] !== undefined)
              .map((key) => (
                <SavedData
                  key={key}
                  title={key[0].toUpperCase() + key.slice(1)}
                  value={candidate.payload[key]}
                />
              ))}
            <SavedData
              title="Exact saved candidate"
              value={candidate.payload}
            />
          </section>
        )}
      </section>
      <HarnessLedger
        detail={detail}
        candidate={candidate}
        onInspectEvidence={() => setActivityOpen(true)}
      />
      <details
        className="border p-3 text-xs"
        open={activityOpen}
        onToggle={(event) => {
          if (event.target === event.currentTarget)
            setActivityOpen(event.currentTarget.open);
        }}
      >
        <summary className="cursor-pointer">
          Run activity ({events.length})
        </summary>
        <ol className="mt-3 max-h-80 space-y-2 overflow-y-auto">
          {events.map((event) => (
            <li
              key={event.id}
              id={`record-${event.id}`}
              className="border-b py-2"
            >
              <span className="text-muted-foreground">
                {event.sequence} ·{" "}
                {new Date(event.created_at).toLocaleTimeString()}
              </span>
              <p className="mt-1 break-words">{event.message}</p>
              <SavedData title={`${event.kind} record`} value={event.data} />
            </li>
          ))}
        </ol>
      </details>
    </section>
  );
}

function Outcome({
  label,
  episode,
  onInspect,
}: {
  label: string;
  episode?: TrainingEpisode;
  onInspect: (id: string) => void;
}) {
  const evaluation = object(episode?.evaluation);
  const status = text(evaluation.status);
  const inference = episode?.stage === "inference";
  return (
    <div className="min-w-0 space-y-2 border bg-muted/10 p-3 text-xs">
      <h4 className="font-medium">{label}</h4>
      <Badge variant="outline">
        {inference
          ? text(episode.result.status, episode.status)
          : status || (episode ? "Not evaluated" : "Not run")}
      </Badge>
      {episode && (
        <>
          <p className="text-muted-foreground">
            Execution: {text(episode.result.status, episode.status)}
          </p>
          <p className="whitespace-pre-wrap break-words">
            {inference
              ? text(episode.result.final_output)
              : text(
                  evaluation.reason,
                  text(
                    episode.result.reason,
                    "No evaluator decision is recorded.",
                  ),
                )}
          </p>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onInspect(episode.id)}
          >
            Inspect{" "}
            {label.startsWith("Basic")
              ? "baseline"
              : label.startsWith("Ontology")
                ? "harness"
                : "inference"}{" "}
            trace
          </Button>
        </>
      )}
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  Circle,
  LoaderCircle,
  TriangleAlert,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, type ModelRuntime } from "@/lib/api";

const labels: Record<ModelRuntime["status"], string> = {
  not_configured: "Not configured",
  not_checked: "Not checked",
  checking: "Checking",
  connected: "Connected",
  check_failed: "Check failed",
};

export function ModelConnectionPanel({ user }: { user: string }) {
  const [runtime, setRuntime] = useState<ModelRuntime | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const requestId = useRef<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function load() {
      try {
        const result = await api<ModelRuntime>(user, "/model-runtime");
        if (!active) return;
        setRuntime(result);
        setError("");
        if (result.status === "checking") timer = setTimeout(load, 1000);
      } catch (e) {
        if (active)
          setError(
            e instanceof Error ? e.message : "Could not load model status.",
          );
      }
    }
    void load();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [user, refresh]);

  async function check() {
    if (submitting || !runtime?.can_check) return;
    setSubmitting(true);
    setError("");
    requestId.current ??= crypto.randomUUID();
    try {
      const result = await api<ModelRuntime>(
        user,
        "/model-runtime/check",
        "POST",
        {
          request_id: requestId.current,
        },
      );
      requestId.current = null;
      if (mounted.current) {
        setRuntime(result);
        setRefresh((value) => value + 1);
      }
    } catch (e) {
      if (mounted.current)
        setError(e instanceof Error ? e.message : "Could not start the check.");
    } finally {
      if (mounted.current) setSubmitting(false);
    }
  }

  const checking = submitting || runtime?.status === "checking";
  const Icon = checking
    ? LoaderCircle
    : runtime?.status === "connected"
      ? CheckCircle2
      : runtime?.status === "check_failed"
        ? TriangleAlert
        : Circle;
  const last = runtime?.last_check;

  return (
    <section aria-label="Model connection" className="border p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="section-title">Model connection</h2>
          <p className="mt-2 text-xs text-muted-foreground">
            Shared backend connection
          </p>
        </div>
        <Badge
          variant="outline"
          role="status"
          aria-live="polite"
          className="gap-2"
        >
          <Icon
            className={`size-3.5 ${checking ? "animate-spin motion-reduce:animate-none" : ""}`}
          />
          {checking
            ? "Checking"
            : runtime
              ? labels[runtime.status]
              : "Loading status"}
        </Badge>
      </div>
      {runtime && (
        <>
          <p className="mt-4 break-words text-sm">
            {runtime.provider} / {runtime.model}
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            This checks whether the backend can obtain validated model output.
          </p>
          {runtime.outdated && (
            <p className="mt-4 text-xs">
              The previous check used a different configuration. Check this
              configuration.
            </p>
          )}
          {last && (
            <div className="mt-4 space-y-2 text-xs text-muted-foreground">
              <p>
                {runtime.outdated
                  ? "Previous configuration checked"
                  : "Last check"}
                :{" "}
                <time dateTime={last.started_at}>
                  {new Date(last.started_at).toLocaleString()}
                </time>
                {last.duration_ms !== null &&
                  ` / ${(last.duration_ms / 1000).toFixed(1)} seconds`}
              </p>
              {last.usage && (
                <p>
                  {last.usage.input_tokens} input tokens /{" "}
                  {last.usage.output_tokens} output tokens (includes reasoning)
                </p>
              )}
              {last.status !== "checking" && !last.usage_known && (
                <p>Usage is unknown. The cost reservation remains in use.</p>
              )}
            </div>
          )}
          {runtime.status === "check_failed" && last?.message && (
            <div role="alert" className="error-panel mt-4">
              <p>{last.message}</p>
              <p className="mt-2 text-xs">{last.recovery}</p>
            </div>
          )}
          {runtime.blocked_reason && runtime.status !== "checking" && (
            <p className="mt-4 text-xs text-muted-foreground">
              {runtime.blocked_reason}
            </p>
          )}
          <div className="mt-5 flex flex-wrap items-center gap-4">
            <Button
              onClick={check}
              disabled={!runtime.can_check || checking || Boolean(error)}
            >
              {checking ? "Checking..." : "Check connection"}
            </Button>
            <p className="text-xs text-muted-foreground">
              ${runtime.remaining_usd.toFixed(5)} remains of the shared $
              {runtime.budget_usd.toFixed(2)} check allowance.
            </p>
          </div>
        </>
      )}
      {error && (
        <div role="alert" className="error-panel mt-4">
          <p>{error}</p>
          <Button
            variant="outline"
            className="mt-3"
            onClick={() => setRefresh((value) => value + 1)}
          >
            Refresh status
          </Button>
        </div>
      )}
    </section>
  );
}

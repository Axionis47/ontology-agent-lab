"use client";

import { useEffect, useRef, useState } from "react";
import { api, type TrainingDetail, type TrainingOverview } from "@/lib/api";

export function useTrainingData(
  user: string,
  base: string,
  runId: string | null,
) {
  const [overview, setOverview] = useState<TrainingOverview | null>(null);
  const [savedDetail, setDetail] = useState<TrainingDetail | null>(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [older, setOlder] = useState<TrainingOverview | null>(null);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const lifetime = useRef<AbortController | null>(null);
  const runs = [
    ...(overview?.runs ?? []),
    ...(older?.runs ?? []).filter(
      (run) => !overview?.runs.some((item) => item.id === run.id),
    ),
  ];
  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const [next, detail] = await Promise.all([
          api<TrainingOverview>(
            user,
            base,
            "GET",
            undefined,
            controller.signal,
          ),
          runId
            ? api<TrainingDetail>(
                user,
                `${base}/runs/${runId}`,
                "GET",
                undefined,
                controller.signal,
              )
            : Promise.resolve(null),
        ]);
        if (controller.signal.aborted) return;
        setOverview((current) => ({
          ...next,
          runs: [
            ...next.runs,
            ...(current?.runs ?? []).filter(
              (run) => !next.runs.some((item) => item.id === run.id),
            ),
          ],
        }));
        setDetail(detail);
        setError("");
        const active = next.runs.some((run) =>
          ["running", "stopping"].includes(run.status),
        );
        timer = setTimeout(refresh, active ? 1000 : 5000);
      } catch (error) {
        if (controller.signal.aborted) return;
        setError((error as Error).message);
        timer = setTimeout(refresh, 5000);
      }
    }
    void refresh();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [user, base, runId, revision]);
  return {
    overview: overview
      ? { ...overview, runs, has_more: older?.has_more ?? overview.has_more }
      : null,
    detail: savedDetail?.run.id === runId ? savedDetail : null,
    loadError: error,
    reload: () => setRevision((value) => value + 1),
    loadingOlder,
    loadOlder: async () => {
      const controller = lifetime.current;
      if (!controller || controller.signal.aborted || loadingOlder) return;
      setLoadingOlder(true);
      try {
        const next = await api<TrainingOverview>(
          user,
          `${base}?offset=${runs.length}`,
          "GET",
          undefined,
          controller.signal,
        );
        if (!controller.signal.aborted)
          setOlder({ ...next, runs: [...(older?.runs ?? []), ...next.runs] });
      } catch (error) {
        if (!controller.signal.aborted) setError((error as Error).message);
      } finally {
        setLoadingOlder(false);
      }
    },
  };
}

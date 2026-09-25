"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { browserApi } from "@/lib/api";

type Phase = "queued" | "running" | "done" | "failed" | "timeout";

interface SourceState {
  error?: string;
  stored?: number;
  status?: string;
}

interface Text {
  queued: string;
  running: string;
  done: string;
  failed: string;
  timeout: string;
  sourceDone: string;
  sourceFailed: string;
}

/**
 * Follows a background index job over Server-Sent Events and refreshes the
 * server-rendered results whenever a source finishes (docs/05-api.md).
 */
export function LiveSearch({
  jobId,
  initialStatus,
  text,
  sourceNames,
}: {
  jobId: string;
  initialStatus: string;
  text: Text;
  sourceNames: Record<string, string>;
}) {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>(initialStatus === "running" ? "running" : "queued");
  const [sources, setSources] = useState<Record<string, SourceState>>({});

  useEffect(() => {
    const stream = new EventSource(browserApi.jobStream(jobId));
    let finishedSources = 0;

    stream.addEventListener("progress", (event) => {
      const state = JSON.parse((event as MessageEvent).data);
      setPhase(state.status === "queued" ? "queued" : "running");
      setSources(state.sources ?? {});
      const finished = Object.values(state.sources ?? {}).filter(
        (s) => (s as SourceState).status !== "running",
      ).length;
      if (finished > finishedSources) {
        finishedSources = finished;
        router.refresh();
      }
    });
    for (const end of ["done", "failed", "timeout"] as const) {
      stream.addEventListener(end, () => {
        setPhase(end);
        stream.close();
        router.refresh();
      });
    }
    stream.onerror = () => {
      // The browser retries automatically; stop once the job has ended.
      if (stream.readyState === EventSource.CLOSED) setPhase("timeout");
    };
    return () => stream.close();
  }, [jobId, router]);

  const busy = phase === "queued" || phase === "running";
  const tone = phase === "failed" || phase === "timeout" ? "border-danger/40" : "border-primary/40";

  return (
    <div role="status" aria-live="polite" className={`space-y-2 rounded-xl border ${tone} bg-primary-soft p-4 text-sm`}>
      <p className="flex items-center gap-2 font-medium">
        {busy && <span className="size-2 animate-pulse rounded-full bg-primary" aria-hidden />}
        {text[phase]}
      </p>
      {Object.keys(sources).length > 0 && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-muted">
          {Object.entries(sources).map(([id, s]) => {
            if (s.status === "running") return null;
            const name = sourceNames[id] ?? id;
            const template = s.error ? text.sourceFailed : text.sourceDone;
            return <li key={id}>{template.replace("{source}", name)}</li>;
          })}
        </ul>
      )}
    </div>
  );
}

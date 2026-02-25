"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import type { Job } from "@/types";

interface JobProgressProps {
  jobId: string;
  /** Called once the job reaches completed or failed */
  onFinished?: (job: Job) => void;
}

const STAGE_LABELS: Record<string, string> = {
  queued: "Waiting in queue",
  strategy: "Analysing product",
  batch_submitted: "Submitting image batch",
  generating: "Generating images",
  completed: "Done",
  failed: "Failed",
};

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
      <div
        className="h-full rounded-full bg-primary transition-all duration-700 ease-out"
        style={{ width: `${Math.min(100, value)}%` }}
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={100}
      />
    </div>
  );
}

export function JobProgress({ jobId, onFinished }: JobProgressProps) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchJob = useCallback(async () => {
    try {
      const j = await api.jobs.get(jobId);
      setJob(j);
      if (j.status === "completed" || j.status === "failed") {
        onFinished?.(j);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch job status");
    }
  }, [jobId, onFinished]);

  useEffect(() => {
    fetchJob();
  }, [fetchJob]);

  useEffect(() => {
    if (!job) return;
    if (job.status === "completed" || job.status === "failed") return;

    // Poll every 5s while job is active
    const interval = setInterval(fetchJob, 5000);
    return () => clearInterval(interval);
  }, [job, fetchJob]);

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3">
        <p className="text-sm text-destructive">{error}</p>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
        Fetching status…
      </div>
    );
  }

  const isActive = ["queued", "strategy", "batch_submitted", "generating"].includes(
    job.status
  );
  const stageLabel =
    STAGE_LABELS[job.status] ?? (job.stage_name || job.status);

  return (
    <div className="space-y-3 rounded-xl border border-border/60 bg-card p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <StatusBadge status={job.status} />
          <span className="text-sm font-medium text-foreground">{stageLabel}</span>
        </div>
        <span className="text-sm tabular-nums text-muted-foreground">
          {job.progress}%
        </span>
      </div>

      <ProgressBar value={job.progress} />

      {isActive && (
        <p className="text-xs text-muted-foreground">
          Generation is running in the background.{" "}
          <span className="font-medium">You can close this tab</span> — we&apos;ll
          email you when it&apos;s done.
        </p>
      )}

      {job.status === "failed" && job.error_message && (
        <p className="text-xs text-destructive">{job.error_message}</p>
      )}

      {job.status === "completed" && job.image_urls && job.image_urls.length > 0 && (
        <p className="text-xs text-emerald-600 dark:text-emerald-400">
          {job.image_urls.length} image{job.image_urls.length !== 1 ? "s" : ""} generated
        </p>
      )}
    </div>
  );
}

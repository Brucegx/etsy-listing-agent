"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { NavBar } from "@/components/nav-bar";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, API_BASE } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Job, JobListResponse } from "@/types";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
      <div
        className="h-full rounded-full bg-primary transition-all duration-500"
        style={{ width: `${Math.min(100, value)}%` }}
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={100}
      />
    </div>
  );
}

// ── Job row ───────────────────────────────────────────────────────────────────

interface JobRowProps {
  job: Job;
  onRefresh: () => void;
}

function JobRow({ job }: JobRowProps) {
  const firstImage = job.image_urls?.[0];

  return (
    <div className="flex items-center gap-4 rounded-xl border border-border/60 bg-card p-4 shadow-sm transition-shadow hover:shadow-md">
      {/* Thumbnail */}
      <div className="relative h-14 w-14 shrink-0 overflow-hidden rounded-lg border border-border/40 bg-muted">
        {firstImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={`${API_BASE}${firstImage}`}
            alt={`Thumbnail for ${job.product_id}`}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-lg text-muted-foreground">
            {job.status === "completed" ? "✓" : "·"}
          </div>
        )}
      </div>

      {/* Main info */}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="max-w-xs truncate font-medium text-foreground">
            {job.product_id}
          </span>
          <StatusBadge status={job.status} />
        </div>

        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
          {job.category && <span className="capitalize">{job.category}</span>}
          <span>{formatDate(job.created_at)}</span>
          {job.cost_usd > 0 && <span>${job.cost_usd.toFixed(3)}</span>}
        </div>

        {/* Progress bar for in-flight jobs */}
        {["strategy", "batch_submitted", "generating"].includes(job.status) && (
          <div className="mt-2 space-y-1">
            <ProgressBar value={job.progress} />
            <p className="text-xs text-muted-foreground">
              {job.stage_name} — {job.progress}%
            </p>
          </div>
        )}

        {/* Error message */}
        {job.status === "failed" && job.error_message && (
          <p className="mt-1 truncate text-xs text-destructive">{job.error_message}</p>
        )}
      </div>

      {/* Actions */}
      {job.status === "completed" && job.image_urls && job.image_urls.length > 0 && (
        <div className="shrink-0">
          <a
            href={`${API_BASE}${job.image_urls[0]}`}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Download images for ${job.product_id}`}
          >
            <Button variant="outline" size="sm">
              Download
            </Button>
          </a>
        </div>
      )}
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border/60 bg-muted/20 px-6 py-16 text-center">
      <span className="mb-3 text-4xl" role="img" aria-label="">
        📷
      </span>
      <h3 className="font-semibold text-foreground">No jobs yet</h3>
      <p className="mt-1 max-w-xs text-sm text-muted-foreground">
        Generate your first listing from the home page or your Google Drive dashboard.
      </p>
      <Button variant="outline" size="sm" className="mt-4" asChild>
        <a href="/">Start generating</a>
      </Button>
    </div>
  );
}

// ── Skeleton rows ─────────────────────────────────────────────────────────────

function SkeletonRow() {
  return (
    <div className="flex items-center gap-4 rounded-xl border border-border/60 bg-card p-4">
      <Skeleton className="h-14 w-14 rounded-lg" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-3 w-28" />
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function JobsPage() {
  const { isAuthenticated, loading: authLoading } = useAuth();
  const router = useRouter();

  const [data, setData] = useState<JobListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const fetchJobs = useCallback(
    async (p: number) => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.jobs.list(p, 20);
        setData(res);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load jobs");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  // Redirect unauthenticated users
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/");
    }
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchJobs(page);
    }
  }, [isAuthenticated, page, fetchJobs]);

  // Auto-refresh in-flight jobs every 8 seconds
  useEffect(() => {
    if (!data) return;
    const hasActive = data.jobs.some((j) =>
      ["queued", "strategy", "batch_submitted", "generating"].includes(j.status)
    );
    if (!hasActive) return;
    const interval = setInterval(() => fetchJobs(page), 8000);
    return () => clearInterval(interval);
  }, [data, page, fetchJobs]);

  const handleRefresh = () => fetchJobs(page);

  return (
    <div className="min-h-screen bg-background">
      <NavBar />

      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Jobs</h1>
            {data && (
              <p className="mt-0.5 text-sm text-muted-foreground">
                {data.total} job{data.total !== 1 ? "s" : ""}
              </p>
            )}
          </div>
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={loading}>
            {loading ? "Refreshing…" : "Refresh"}
          </Button>
        </div>

        {/* Content */}
        {error && (
          <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 p-4">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        {loading && !data ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <SkeletonRow key={i} />
            ))}
          </div>
        ) : data?.jobs.length === 0 ? (
          <EmptyState />
        ) : (
          <>
            <div className="space-y-3">
              {data?.jobs.map((job) => (
                <JobRow key={job.job_id} job={job} onRefresh={handleRefresh} />
              ))}
            </div>

            {/* Pagination */}
            {data && data.total_pages > 1 && (
              <div className="mt-6 flex items-center justify-between text-sm text-muted-foreground">
                <span>
                  Page {data.page} of {data.total_pages}
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                    disabled={page === data.total_pages}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

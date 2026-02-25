"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { NavBar } from "@/components/nav-bar";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { API_BASE } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────

interface JobEntry {
  id?: number;
  job_id?: string;
  product_id: string;
  category?: string;
  status: string;
  progress?: number;
  stage_name?: string;
  image_urls?: string[] | null;
  error_message?: string | null;
  cost_usd?: number;
  created_at: string;
}

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

// ── Status badge with test-friendly color classes ─────────────────────────────

const STATUS_CLASSES: Record<string, string> = {
  queued:
    "bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900/40 dark:text-yellow-400 dark:border-yellow-800",
  strategy:
    "bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900/40 dark:text-yellow-400 dark:border-yellow-800",
  batch_submitted:
    "bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900/40 dark:text-yellow-400 dark:border-yellow-800",
  generating:
    "bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900/40 dark:text-yellow-400 dark:border-yellow-800",
  completed:
    "bg-green-100 text-green-700 border-green-200 dark:bg-green-900/40 dark:text-green-400 dark:border-green-800",
  failed:
    "bg-rose-100 text-rose-700 border-rose-200 dark:bg-rose-900/40 dark:text-rose-400 dark:border-rose-800",
};

function InlineStatusBadge({
  status,
  testId,
}: {
  status: string;
  testId: string;
}) {
  const classes =
    STATUS_CLASSES[status] ??
    "bg-muted text-muted-foreground border-border";
  return (
    <span
      data-testid={testId}
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${classes}`}
    >
      {status}
    </span>
  );
}

// ── Job row ───────────────────────────────────────────────────────────────────

interface JobRowProps {
  job: JobEntry;
  onRefresh: () => void;
}

function JobRow({ job }: JobRowProps) {
  const jobKey = job.id ?? job.job_id ?? job.product_id;
  const firstImage = job.image_urls?.[0];

  return (
    <div
      data-testid={`job-item-${jobKey}`}
      className="flex items-center gap-4 rounded-xl border border-border/60 bg-card p-4 shadow-sm transition-shadow hover:shadow-md"
    >
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
          <InlineStatusBadge
            status={job.status}
            testId={`job-status-${jobKey}`}
          />
        </div>

        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
          {job.category && <span className="capitalize">{job.category}</span>}
          <span>{formatDate(job.created_at)}</span>
          {job.cost_usd != null && job.cost_usd > 0 && (
            <span>${job.cost_usd.toFixed(3)}</span>
          )}
        </div>

        {/* Progress bar for in-flight jobs */}
        {["strategy", "batch_submitted", "generating"].includes(job.status) &&
          job.progress != null && (
            <div className="mt-2 space-y-1">
              <ProgressBar value={job.progress} />
              <p className="text-xs text-muted-foreground">
                {job.stage_name} — {job.progress}%
              </p>
            </div>
          )}

        {/* Error message */}
        {job.status === "failed" && job.error_message && (
          <p className="mt-1 truncate text-xs text-destructive">
            {job.error_message}
          </p>
        )}
      </div>

      {/* Actions */}
      {job.status === "completed" &&
        job.image_urls &&
        job.image_urls.length > 0 && (
          <div className="shrink-0">
            <a
              href={`${BACKEND_URL}${job.image_urls[0]}`}
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

function EmptyState({ onUpload }: { onUpload: () => void }) {
  return (
    <div
      data-testid="jobs-empty"
      className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border/60 bg-muted/20 px-6 py-16 text-center"
    >
      <span className="mb-3 text-4xl" role="img" aria-label="">
        📷
      </span>
      <h3 className="font-semibold text-foreground">No jobs yet</h3>
      <p className="mt-1 max-w-xs text-sm text-muted-foreground">
        Generate your first listing from the home page or your Google Drive
        dashboard.
      </p>
      <Button
        variant="outline"
        size="sm"
        className="mt-4"
        onClick={onUpload}
      >
        Upload Product
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

  const [jobs, setJobs] = useState<JobEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  const fetchJobs = useCallback(
    async (p: number) => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(
          `${BACKEND_URL}/api/jobs?page=${p}&page_size=20`,
          { credentials: "include" }
        );
        if (!res.ok) {
          throw new Error("Failed to fetch jobs");
        }
        const data = await res.json();
        // Handle both plain array (mock) and paginated response (real backend)
        if (Array.isArray(data)) {
          setJobs(data);
          setTotal(data.length);
          setTotalPages(1);
        } else {
          setJobs(data.jobs ?? []);
          setTotal(data.total ?? 0);
          setTotalPages(data.total_pages ?? 1);
        }
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to fetch jobs"
        );
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
    const hasActive = jobs.some((j) =>
      ["queued", "strategy", "batch_submitted", "generating"].includes(j.status)
    );
    if (!hasActive) return;
    const interval = setInterval(() => fetchJobs(page), 8000);
    return () => clearInterval(interval);
  }, [jobs, page, fetchJobs]);

  const handleRefresh = () => fetchJobs(page);
  const handleUpload = () => router.push("/");

  return (
    <div className="min-h-screen bg-background">
      <NavBar />

      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Jobs</h1>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Track the status of your product listing generation jobs
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => router.push("/dashboard")}
            >
              Dashboard
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={loading}
            >
              {loading ? "Refreshing…" : "Refresh"}
            </Button>
          </div>
        </div>

        {/* Count */}
        {!loading && !error && total > 0 && (
          <p className="mb-4 text-sm text-muted-foreground">
            {total} job{total !== 1 ? "s" : ""}
          </p>
        )}

        {/* Error */}
        {error && (
          <div
            data-testid="jobs-error"
            className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 p-4"
          >
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        {/* Content */}
        {loading && jobs.length === 0 ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <SkeletonRow key={i} />
            ))}
          </div>
        ) : !error && jobs.length === 0 ? (
          <EmptyState onUpload={handleUpload} />
        ) : (
          <>
            <ul data-testid="jobs-list" className="space-y-3">
              {jobs.map((job) => (
                <li key={job.id ?? job.job_id ?? job.product_id}>
                  <JobRow job={job} onRefresh={handleRefresh} />
                </li>
              ))}
            </ul>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="mt-6 flex items-center justify-between text-sm text-muted-foreground">
                <span>
                  Page {page} of {totalPages}
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
                    onClick={() =>
                      setPage((p) => Math.min(totalPages, p + 1))
                    }
                    disabled={page === totalPages}
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

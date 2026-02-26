"use client";

import { useAuth } from "@/lib/auth";
import { useRouter, useParams } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { NavBar } from "@/components/nav-bar";
import { api, API_BASE } from "@/lib/api";
import type { Job } from "@/types";

/* ---------- status badge (reused from jobs list) ---------- */

const STATUS_CONFIG: Record<string, { label: string; color: string; dot: string }> = {
  queued: {
    label: "Queued",
    color: "text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-950/40 border-yellow-200 dark:border-yellow-800",
    dot: "bg-yellow-400",
  },
  strategy: {
    label: "Analyzing",
    color: "text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800",
    dot: "bg-blue-400 animate-pulse",
  },
  batch_submitted: {
    label: "Generating",
    color: "text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800",
    dot: "bg-blue-400 animate-pulse",
  },
  generating: {
    label: "Generating",
    color: "text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800",
    dot: "bg-blue-400 animate-pulse",
  },
  completed: {
    label: "Completed",
    color: "text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-950/40 border-green-200 dark:border-green-800",
    dot: "bg-green-400",
  },
  failed: {
    label: "Failed",
    color: "text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-800",
    dot: "bg-red-400",
  },
};

const FALLBACK_STATUS = {
  label: "Processing",
  color: "text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-950/40 border-gray-200 dark:border-gray-800",
  dot: "bg-gray-400 animate-pulse",
};

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? FALLBACK_STATUS;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${cfg.color}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

/* ---------- copy button ---------- */

function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: ignore clipboard errors silently
    }
  }, [text]);

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={handleCopy}
      className="h-7 px-2 text-xs shrink-0"
    >
      {copied ? (
        <>
          <svg className="h-3.5 w-3.5 mr-1 text-green-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
          Copied!
        </>
      ) : (
        <>
          <svg className="h-3.5 w-3.5 mr-1" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0 0 13.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 0 1-.75.75H9.75a.75.75 0 0 1-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 0 1-2.25 2.25H6.75A2.25 2.25 0 0 1 4.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 0 1 1.927-.184" />
          </svg>
          {label}
        </>
      )}
    </Button>
  );
}

/* ---------- friendly error (from jobs list) ---------- */

function friendlyError(raw: string | Record<string, unknown> | null | undefined): string {
  if (!raw) return "An unknown error occurred.";

  const msg = typeof raw === "string" ? raw : JSON.stringify(raw);
  const lower = msg.toLowerCase();

  if (lower.includes("image exceeds") || lower.includes("file size") || lower.includes("too large")) {
    return "One or more images were too large. Please use images under 5 MB.";
  }
  if (lower.includes("rate limit") || lower.includes("too many requests") || lower.includes("429")) {
    return "The AI service is temporarily busy. Please wait a moment and try again.";
  }
  if (lower.includes("timeout") || lower.includes("timed out")) {
    return "The generation timed out. Try again -- large batches may take longer.";
  }
  if (lower.includes("unauthorized") || lower.includes("401") || lower.includes("403")) {
    return "Your session expired. Please sign in again.";
  }

  if (msg.includes("Traceback") || msg.includes("Error:")) {
    const firstLine = msg
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean)
      .find((l) => l.includes("Error:") || l.includes("Exception:"));
    return firstLine
      ? `Generation failed: ${firstLine.replace(/^.*Error:\s*/, "")}`
      : "Generation failed due to an internal error. Check server logs.";
  }

  return msg.length > 300 ? msg.slice(0, 300) + "..." : msg;
}

/* ---------- date formatting ---------- */

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

/* ---------- main page component ---------- */

export default function JobDetailPage() {
  const { loading, isAuthenticated } = useAuth();
  const router = useRouter();
  const params = useParams();
  const jobId = params.jobId as string;

  const [job, setJob] = useState<Job | null>(null);
  const [jobLoading, setJobLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push("/");
    }
  }, [loading, isAuthenticated, router]);

  const fetchJob = useCallback(async () => {
    if (!jobId) return;
    setJobLoading(true);
    setFetchError(null);
    try {
      const data = await api.jobs.get(jobId);
      setJob(data);
    } catch (err) {
      setFetchError(err instanceof Error ? err.message : "Failed to load job.");
    } finally {
      setJobLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    if (isAuthenticated) fetchJob();
  }, [isAuthenticated, fetchJob]);

  const handleDelete = async () => {
    if (!job) return;
    setDeleting(true);
    try {
      const res = await fetch(`${API_BASE}/api/jobs/${job.job_id}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (res.ok || res.status === 204) {
        router.push("/jobs");
      } else {
        setFetchError(res.status === 409 ? "Cannot delete a running job." : "Failed to delete job.");
      }
    } catch {
      setFetchError("Network error — could not delete job.");
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const listing: Record<string, any> | null = job?.result && "listing" in job.result
    ? (job.result.listing as Record<string, any>)
    : null;

  const tags = listing?.tags
    ? String(listing.tags).split(",").map((t: string) => t.trim()).filter(Boolean)
    : [];

  const attributes: Record<string, unknown> = listing?.attributes ?? {};
  const titleVariations: string[] = Array.isArray(listing?.title_variations) ? listing.title_variations : [];
  const longTailKeywords: string[] = Array.isArray(listing?.long_tail_keywords) ? listing.long_tail_keywords : [];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <NavBar />

      <main className="mx-auto max-w-4xl px-4 py-8 space-y-6">
        {/* Back link */}
        <Link
          href="/jobs"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
          </svg>
          Back to Jobs
        </Link>

        {/* Error banner */}
        {fetchError && (
          <div className="rounded-lg border border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/40 p-4 flex items-start gap-3">
            <svg className="h-5 w-5 text-red-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
            </svg>
            <p className="text-sm text-red-700 dark:text-red-400">{fetchError}</p>
          </div>
        )}

        {/* Loading skeleton */}
        {jobLoading && (
          <Card>
            <CardContent className="pt-6 space-y-4">
              <Skeleton className="h-6 w-1/3" />
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-32 w-full" />
            </CardContent>
          </Card>
        )}

        {/* Job detail */}
        {!jobLoading && job && (
          <>
            {/* Header card */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <CardTitle className="text-lg">{job.product_id}</CardTitle>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      {job.category && (
                        <span className="rounded bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 font-mono text-xs">
                          {job.category}
                        </span>
                      )}
                      <span>{formatDate(job.created_at)}</span>
                      {job.cost_usd > 0 && <span>&middot; ${job.cost_usd.toFixed(3)}</span>}
                    </div>
                  </div>
                  <StatusBadge status={job.status} />
                </div>
              </CardHeader>
            </Card>

            {/* In-progress: progress bar */}
            {job.progress > 0 && job.progress < 100 && job.status !== "failed" && job.status !== "completed" && (
              <Card>
                <CardContent className="pt-6 space-y-2">
                  <div className="flex justify-between text-sm text-muted-foreground">
                    <span>{job.stage_name}</span>
                    <span>{job.progress}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-gray-200 dark:bg-gray-700">
                    <div
                      className="h-2 rounded-full bg-blue-500 transition-all"
                      style={{ width: `${job.progress}%` }}
                    />
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Failed: error message */}
            {job.status === "failed" && (
              <Card className="border-red-200 dark:border-red-800">
                <CardContent className="pt-6 space-y-2">
                  <h3 className="text-sm font-medium text-red-700 dark:text-red-400">Error</h3>
                  <p className="text-sm text-red-600 dark:text-red-400">
                    {friendlyError(job.error_message)}
                  </p>
                  {job.error_message && typeof job.error_message === "string" && job.error_message.length > 100 && (
                    <details className="mt-2">
                      <summary className="text-xs text-red-500 cursor-pointer hover:underline">
                        Show raw error
                      </summary>
                      <pre className="mt-2 whitespace-pre-wrap break-all text-xs text-red-600 dark:text-red-400 font-mono max-h-48 overflow-y-auto bg-red-50 dark:bg-red-950/30 rounded p-2">
                        {job.error_message}
                      </pre>
                    </details>
                  )}
                  <div className="pt-2">
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={handleDelete}
                      disabled={deleting}
                    >
                      {deleting ? "Deleting..." : "Delete this job"}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Completed: listing details */}
            {job.status === "completed" && listing && (
              <>
                {/* Title */}
                {listing.title && (
                  <Card>
                    <CardHeader className="pb-2">
                      <div className="flex items-start justify-between gap-3">
                        <CardTitle className="text-base">Listing Title</CardTitle>
                        <CopyButton text={listing.title} label="Copy" />
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-gray-900 dark:text-gray-100 leading-relaxed">
                        {listing.title}
                      </p>
                    </CardContent>
                  </Card>
                )}

                {/* Tags */}
                {tags.length > 0 && (
                  <Card>
                    <CardHeader className="pb-2">
                      <div className="flex items-start justify-between gap-3">
                        <CardTitle className="text-base">Tags</CardTitle>
                        <CopyButton text={tags.join(", ")} label="Copy all tags" />
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-wrap gap-1.5">
                        {tags.map((tag, i) => (
                          <span
                            key={i}
                            className="inline-block rounded-full bg-gray-200 dark:bg-gray-700 px-2.5 py-1 text-xs text-gray-700 dark:text-gray-300"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Description */}
                {listing.description && (
                  <Card>
                    <CardHeader className="pb-2">
                      <div className="flex items-start justify-between gap-3">
                        <CardTitle className="text-base">Description</CardTitle>
                        <CopyButton text={listing.description} label="Copy" />
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-gray-900 dark:text-gray-100 leading-relaxed whitespace-pre-wrap">
                        {listing.description}
                      </p>
                    </CardContent>
                  </Card>
                )}

                {/* Attributes */}
                {Object.keys(attributes).length > 0 && (
                  <Card>
                    <CardHeader className="pb-2">
                      <div className="flex items-start justify-between gap-3">
                        <CardTitle className="text-base">Listing Attributes</CardTitle>
                        <CopyButton
                          text={Object.entries(attributes)
                            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`)
                            .join("\n")}
                          label="Copy all"
                        />
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 gap-x-6 gap-y-2">
                        {Object.entries(attributes).map(([key, value]) => (
                          <div key={key} className="flex items-baseline gap-2">
                            <span className="text-xs text-muted-foreground capitalize whitespace-nowrap">
                              {key.replace(/_/g, " ")}:
                            </span>
                            <span className="text-sm text-gray-900 dark:text-gray-100">
                              {Array.isArray(value) ? value.join(", ") : String(value)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Title Variations */}
                {titleVariations.length > 0 && (
                  <Card>
                    <CardHeader className="pb-2">
                      <div className="flex items-start justify-between gap-3">
                        <CardTitle className="text-base">Title Variations</CardTitle>
                        <CopyButton text={titleVariations.join("\n")} label="Copy all" />
                      </div>
                    </CardHeader>
                    <CardContent>
                      <ul className="space-y-1.5">
                        {titleVariations.map((t, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <span className="text-xs text-muted-foreground mt-0.5">{i + 1}.</span>
                            <span className="text-sm text-gray-900 dark:text-gray-100">{t}</span>
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                )}

                {/* Long-tail Keywords */}
                {longTailKeywords.length > 0 && (
                  <Card>
                    <CardHeader className="pb-2">
                      <div className="flex items-start justify-between gap-3">
                        <CardTitle className="text-base">Long-tail Keywords</CardTitle>
                        <CopyButton text={longTailKeywords.join(", ")} label="Copy all" />
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-wrap gap-1.5">
                        {longTailKeywords.map((kw, i) => (
                          <span
                            key={i}
                            className="inline-block rounded-full bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 px-2.5 py-1 text-xs text-blue-700 dark:text-blue-300"
                          >
                            {kw}
                          </span>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </>
            )}

            {/* Completed: images */}
            {job.status === "completed" && job.image_urls && job.image_urls.length > 0 && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">
                    Generated Images ({job.image_urls.length})
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {job.image_urls.map((url, idx) => (
                      <a
                        key={idx}
                        href={`${API_BASE}${url}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="group relative aspect-square rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700 hover:border-blue-400 transition-colors"
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={`${API_BASE}${url}`}
                          alt={`Generated image ${idx + 1}`}
                          className="h-full w-full object-cover"
                          loading="lazy"
                        />
                        <span className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-xs text-center py-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          {url.split("/").pop()?.replace(/^upload_\w+_/, "").replace(/\.png$/, "") ?? `Image ${idx + 1}`}
                        </span>
                      </a>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </>
        )}
      </main>
    </div>
  );
}

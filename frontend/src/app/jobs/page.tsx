"use client";

import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { NavBar } from "@/components/nav-bar";
import { API_BASE } from "@/lib/api";
/** Shape returned by GET /api/jobs → jobs[] */
interface ApiJob {
  job_id: string;
  product_id: string;
  category: string;
  status: string;
  progress: number;
  stage_name: string;
  image_urls: string[] | null;
  result: Record<string, unknown> | null;
  error_message: string | null;
  cost_usd: number;
  created_at: string;
  updated_at: string;
}

/**
 * Translates raw error strings into user-friendly messages.
 */
function friendlyError(raw: string | Record<string, unknown> | null | undefined): string {
  if (!raw) return "An unknown error occurred.";

  const msg = typeof raw === "string" ? raw : JSON.stringify(raw);
  const lower = msg.toLowerCase();

  if (lower.includes("image exceeds") || lower.includes("file size") || lower.includes("too large")) {
    return "One or more images were too large. Please use images under 5 MB.";
  }
  if (lower.includes("no excel") || lower.includes("spreadsheet") || lower.includes("xlsx")) {
    return "No product spreadsheet found in the Drive folder. Add an Excel or Google Sheets file with product details.";
  }
  if (lower.includes("rate limit") || lower.includes("too many requests") || lower.includes("429")) {
    return "The AI service is temporarily busy. Please wait a moment and try again.";
  }
  if (lower.includes("timeout") || lower.includes("timed out")) {
    return "The generation timed out. Try again — large batches may take longer.";
  }
  if (lower.includes("unauthorized") || lower.includes("401") || lower.includes("403")) {
    return "Your session expired. Please sign in again.";
  }
  if (lower.includes("no product") || lower.includes("product not found")) {
    return "Product not found in the spreadsheet. Check that the product ID matches the spreadsheet rows.";
  }
  if (lower.includes("invalid image") || lower.includes("unsupported format") || lower.includes("mime")) {
    return "One or more files are not valid images. Use JPG, PNG, or WebP files.";
  }
  if (lower.includes("network") || lower.includes("connection") || lower.includes("econnrefused")) {
    return "Network error — the server could not be reached. Check your connection and try again.";
  }

  // Strip raw Python tracebacks — just show first meaningful line
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

  return msg.length > 200 ? msg.slice(0, 200) + "…" : msg;
}

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

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function ListingSummary({ listing }: { listing: Record<string, string> }) {
  return (
    <div className="rounded-md border border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50 px-3 py-2.5 space-y-2">
      {listing.title && (
        <p className="text-sm font-medium text-gray-900 dark:text-gray-100 leading-snug">
          {listing.title}
        </p>
      )}
      {listing.tags && (
        <div className="flex flex-wrap gap-1">
          {listing.tags.split(",").map((tag, i) => (
            <span
              key={i}
              className="inline-block rounded bg-gray-200 dark:bg-gray-700 px-1.5 py-0.5 text-[10px] text-gray-600 dark:text-gray-300"
            >
              {tag.trim()}
            </span>
          ))}
        </div>
      )}
      {listing.description && (
        <p className="text-xs text-muted-foreground line-clamp-3 leading-relaxed">
          {listing.description.slice(0, 300)}
          {listing.description.length > 300 ? "..." : ""}
        </p>
      )}
    </div>
  );
}

export default function JobsPage() {
  const { loading, isAuthenticated } = useAuth();
  const router = useRouter();
  const [jobs, setJobs] = useState<ApiJob[]>([]);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [expandedErrors, setExpandedErrors] = useState<Set<string>>(new Set());
  const [expandedImages, setExpandedImages] = useState<Set<string>>(new Set());
  const [deletingJobs, setDeletingJobs] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push("/");
    }
  }, [loading, isAuthenticated, router]);

  const fetchJobs = useCallback(async () => {
    setJobsLoading(true);
    setFetchError(null);
    try {
      const res = await fetch(`${API_BASE}/api/jobs`, {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setJobs(data.jobs ?? []);
      } else if (res.status === 404) {
        setJobs([]);
      } else {
        setFetchError("Failed to load jobs. Please try again.");
      }
    } catch {
      setFetchError("Network error — could not reach the server.");
    } finally {
      setJobsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) fetchJobs();
  }, [isAuthenticated, fetchJobs]);

  const toggleError = (id: string) => {
    setExpandedErrors((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleImages = (id: string) => {
    setExpandedImages((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const deleteJob = async (jobId: string) => {
    setDeletingJobs((prev) => new Set(prev).add(jobId));
    try {
      const res = await fetch(`${API_BASE}/api/jobs/${jobId}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (res.ok || res.status === 204) {
        setJobs((prev) => prev.filter((j) => j.job_id !== jobId));
      } else {
        setFetchError(res.status === 409 ? "Cannot delete a running job." : "Failed to delete job.");
      }
    } catch {
      setFetchError("Network error — could not delete job.");
    } finally {
      setDeletingJobs((prev) => {
        const next = new Set(prev);
        next.delete(jobId);
        return next;
      });
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <NavBar />

      <main className="mx-auto max-w-4xl px-4 py-8 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">
              Generation Jobs
            </h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              Track the status of your listing generation runs.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {!jobsLoading && jobs.length > 0 && (
              <span className="text-sm text-muted-foreground">
                {jobs.length} job{jobs.length !== 1 ? "s" : ""}
              </span>
            )}
            <Button size="sm" variant="outline" onClick={fetchJobs} disabled={jobsLoading}>
              <svg
                className={`h-3.5 w-3.5 mr-1.5 ${jobsLoading ? "animate-spin" : ""}`}
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99"
                />
              </svg>
              Refresh
            </Button>
          </div>
        </div>

        {fetchError && (
          <div className="rounded-lg border border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/40 p-4 flex items-start gap-3">
            <svg
              className="h-5 w-5 text-red-500 shrink-0 mt-0.5"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z"
              />
            </svg>
            <p className="text-sm text-red-700 dark:text-red-400">{fetchError}</p>
          </div>
        )}

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">All Jobs</CardTitle>
          </CardHeader>
          <CardContent>
            {jobsLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : jobs.length === 0 ? (
              <div className="py-12 text-center space-y-2">
                <svg
                  className="mx-auto h-10 w-10 text-gray-300 dark:text-gray-700"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1}
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0ZM3.75 12h.007v.008H3.75V12Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm-.375 5.25h.007v.008H3.75v-.008Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z"
                  />
                </svg>
                <p className="text-sm text-muted-foreground">No jobs yet.</p>
                <p className="text-xs text-muted-foreground">
                  Jobs appear here after you run a generation from the Drive
                  dashboard.
                </p>
              </div>
            ) : (
              <ul className="space-y-3">
                {jobs.map((job) => {
                  const errorMsg = job.status === "failed" ? friendlyError(job.error_message) : null;
                  const isExpanded = expandedErrors.has(job.job_id);

                  return (
                    <li
                      key={job.job_id}
                      className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 hover:border-gray-300 dark:hover:border-gray-600 transition-colors"
                    >
                      {/* Clickable header area — Link wraps only safe (no nested <a>) content */}
                      <Link href={`/jobs/${job.job_id}`} className="block px-4 py-3 space-y-2">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex-1 min-w-0 space-y-0.5">
                            <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                              {job.product_id}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {job.category && (
                                <span className="mr-2 rounded bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 font-mono">
                                  {job.category}
                                </span>
                              )}
                              {formatDate(job.created_at)}
                              {job.cost_usd > 0 && (
                                <span className="ml-2">&middot; ${job.cost_usd.toFixed(3)}</span>
                              )}
                            </p>
                          </div>
                          <StatusBadge status={job.status} />
                        </div>

                        {/* Listing info for completed jobs */}
                        {job.status === "completed" && job.result && "listing" in job.result && (
                          <ListingSummary listing={job.result.listing as Record<string, string>} />
                        )}

                        {/* Progress bar for in-flight jobs */}
                        {job.progress > 0 && job.progress < 100 && job.status !== "failed" && job.status !== "completed" && (
                          <div className="space-y-1">
                            <div className="flex justify-between text-xs text-muted-foreground">
                              <span>{job.stage_name}</span>
                              <span>{job.progress}%</span>
                            </div>
                            <div className="h-1.5 rounded-full bg-gray-200 dark:bg-gray-700">
                              <div
                                className="h-1.5 rounded-full bg-blue-500 transition-all"
                                style={{ width: `${job.progress}%` }}
                              />
                            </div>
                          </div>
                        )}
                      </Link>

                      {/* Image thumbnails — outside Link to avoid nested <a> */}
                      {job.status === "completed" && job.image_urls && job.image_urls.length > 0 && (
                        <div className="px-4 pb-3 space-y-2">
                          <button
                            className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
                            onClick={() => toggleImages(job.job_id)}
                          >
                            <svg
                              className={`h-3 w-3 transition-transform ${expandedImages.has(job.job_id) ? "rotate-90" : ""}`}
                              fill="none"
                              stroke="currentColor"
                              strokeWidth={2}
                              viewBox="0 0 24 24"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                            </svg>
                            {job.image_urls.length} generated image{job.image_urls.length !== 1 ? "s" : ""}
                          </button>
                          {expandedImages.has(job.job_id) && (
                            <div className="grid grid-cols-5 gap-2">
                              {job.image_urls.map((url, idx) => (
                                <a
                                  key={idx}
                                  href={`${API_BASE}${url}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="group relative aspect-square rounded-md overflow-hidden border border-gray-200 dark:border-gray-700 hover:border-blue-400 transition-colors"
                                >
                                  <img
                                    src={`${API_BASE}${url}`}
                                    alt={`Generated image ${idx + 1}`}
                                    className="h-full w-full object-cover"
                                    loading="lazy"
                                  />
                                  <span className="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-[10px] text-center py-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                                    {url.split("/").pop()?.replace(/^upload_\w+_/, "").replace(/\.png$/, "") ?? `Image ${idx + 1}`}
                                  </span>
                                </a>
                              ))}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Error message — outside Link to avoid nested <a> issues */}
                      {job.status === "failed" && errorMsg && (
                        <div className="px-4 pb-3">
                          <div className="rounded-md bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 px-3 py-2 space-y-1">
                            <p className="text-xs text-red-700 dark:text-red-400">
                              {errorMsg}
                            </p>
                            <div className="flex items-center gap-3">
                              {job.error_message && (
                                <button
                                  className="text-xs text-red-500 dark:text-red-500 underline hover:no-underline"
                                  onClick={() => toggleError(job.job_id)}
                                >
                                  {isExpanded ? "Hide raw error" : "Show raw error"}
                                </button>
                              )}
                              <button
                                className="text-xs text-red-500 hover:text-red-700 dark:hover:text-red-300 underline hover:no-underline"
                                disabled={deletingJobs.has(job.job_id)}
                                onClick={() => deleteJob(job.job_id)}
                              >
                                {deletingJobs.has(job.job_id) ? "Deleting..." : "Delete"}
                              </button>
                            </div>
                            {isExpanded && job.error_message && (
                              <pre className="mt-2 whitespace-pre-wrap break-all text-xs text-red-600 dark:text-red-400 font-mono max-h-32 overflow-y-auto">
                                {typeof job.error_message === "string"
                                  ? job.error_message
                                  : JSON.stringify(job.error_message, null, 2)}
                              </pre>
                            )}
                          </div>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}

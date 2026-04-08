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
import type { Job } from "@/types";

function JobTypeBadge({ jobType }: { jobType?: string }) {
  if (jobType === "image_only") {
    return (
      <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide bg-[#D4A853]/15 text-[#D4A853]">
        <svg className="h-2.5 w-2.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909" />
          <rect x="3" y="3" width="18" height="18" rx="2" />
        </svg>
        Image Studio
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide bg-orange-500/15 text-orange-400">
      <svg className="h-2.5 w-2.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25z" />
      </svg>
      Full Listing
    </span>
  );
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
    color: "text-gray-600 bg-gray-100 border-gray-200",
    dot: "bg-gray-400",
  },
  strategy: {
    label: "Analyzing",
    color: "text-[#D4A853] bg-[#D4A853]/10 border-[#D4A853]/20",
    dot: "bg-[#D4A853] animate-pulse",
  },
  batch_submitted: {
    label: "Generating",
    color: "text-[#D4A853] bg-[#D4A853]/10 border-[#D4A853]/20",
    dot: "bg-[#D4A853] animate-pulse",
  },
  generating: {
    label: "Generating",
    color: "text-[#D4A853] bg-[#D4A853]/10 border-[#D4A853]/20",
    dot: "bg-[#D4A853] animate-pulse",
  },
  completed: {
    label: "Completed",
    color: "text-green-700 bg-green-50 border-green-200",
    dot: "bg-green-500",
  },
  failed: {
    label: "Failed",
    color: "text-red-700 bg-red-50 border-red-200",
    dot: "bg-red-500",
  },
};

const FALLBACK_STATUS = {
  label: "Processing",
  color: "text-[#D4A853] bg-[#D4A853]/10 border-[#D4A853]/20",
  dot: "bg-[#D4A853] animate-pulse",
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
    <div className="rounded-md border border-[#E8E8E3] bg-[#F5F5F0] px-3 py-2.5 space-y-2">
      {listing.title && (
        <p className="text-sm font-medium text-[#1A1A1A] leading-snug">
          {listing.title}
        </p>
      )}
      {listing.tags && (
        <div className="flex flex-wrap gap-1">
          {listing.tags.split(",").map((tag, i) => (
            <span
              key={i}
              className="inline-block rounded bg-[#E8E8E3] px-1.5 py-0.5 text-[10px] text-[#737373]"
            >
              {tag.trim()}
            </span>
          ))}
        </div>
      )}
      {listing.description && (
        <p className="text-xs text-[#737373] line-clamp-3 leading-relaxed">
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
  const [jobs, setJobs] = useState<Job[]>([]);
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
      <div className="flex h-screen items-center justify-center bg-[#FAFAF9]">
        <p className="text-sm text-[#737373]">Loading...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <NavBar />

      <main className="mx-auto max-w-4xl px-4 py-8 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-[#1A1A1A]">
              Generation Jobs
            </h2>
            <p className="text-sm text-[#737373] mt-0.5">
              Track the status of your listing generation runs.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {!jobsLoading && jobs.length > 0 && (
              <span className="text-sm text-[#737373]">
                {jobs.length} job{jobs.length !== 1 ? "s" : ""}
              </span>
            )}
            <Button
              size="sm"
              variant="outline"
              onClick={fetchJobs}
              disabled={jobsLoading}
              className="border-[#E8E8E3] bg-transparent hover:bg-[#F5F5F0] text-[#737373] hover:text-[#1A1A1A]"
            >
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
          <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4 flex items-start gap-3">
            <svg
              className="h-5 w-5 text-red-400 shrink-0 mt-0.5"
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
            <p className="text-sm text-red-400">{fetchError}</p>
          </div>
        )}

        <Card className="bg-white border-[#E8E8E3] shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base text-[#1A1A1A]">All Jobs</CardTitle>
          </CardHeader>
          <CardContent>
            {jobsLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-16 w-full bg-[#F5F5F0]" />
                ))}
              </div>
            ) : jobs.length === 0 ? (
              <div className="py-12 text-center space-y-2">
                <svg
                  className="mx-auto h-10 w-10 text-[#D4D4CF]"
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
                <p className="text-sm text-[#737373]">No jobs yet.</p>
                <p className="text-xs text-[#737373]">
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
                      className="rounded-lg border border-[#E8E8E3] bg-[#F5F5F0] hover:border-[#D4D4CF] hover:shadow-sm transition-all"
                    >
                      {/* Clickable header area — Link wraps only safe (no nested <a>) content */}
                      <Link href={`/jobs/${job.job_id}`} className="block px-4 py-3 space-y-2">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex-1 min-w-0 space-y-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <p className="text-sm font-medium text-[#1A1A1A] truncate">
                                {job.product_id}
                              </p>
                              <JobTypeBadge jobType={job.job_type} />
                            </div>
                            <p className="text-xs text-[#888]">
                              {job.category && (
                                <span className="mr-2 rounded bg-[#E8E8E3] px-1.5 py-0.5 font-mono text-[#737373]">
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

                        {/* Listing info for completed full_listing jobs only */}
                        {job.status === "completed" && job.result && "listing" in job.result && job.job_type !== "image_only" && (
                          <ListingSummary listing={job.result.listing as Record<string, string>} />
                        )}

                        {/* Image-only: show compact image count */}
                        {job.status === "completed" && job.job_type === "image_only" && job.image_urls && job.image_urls.length > 0 && (
                          <div className="flex items-center gap-1.5 text-xs text-[#D4A853]">
                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909" />
                              <rect x="3" y="3" width="18" height="18" rx="2" />
                            </svg>
                            {job.image_urls.length} image{job.image_urls.length !== 1 ? "s" : ""} generated
                          </div>
                        )}

                        {/* Progress bar for in-flight jobs */}
                        {job.progress > 0 && job.progress < 100 && job.status !== "failed" && job.status !== "completed" && (
                          <div className="space-y-1">
                            <div className="flex justify-between text-xs text-[#888]">
                              <span>{job.stage_name}</span>
                              <span>{job.progress}%</span>
                            </div>
                            <div className="h-1.5 rounded-full bg-[#F5F5F0]">
                              <div
                                className="h-1.5 rounded-full bg-[#D4A853] transition-all"
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
                            className="text-xs text-[#D4A853] hover:text-[#E4B863] transition-colors flex items-center gap-1"
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
                                  className="group relative aspect-square rounded-md overflow-hidden border border-[#E8E8E3] hover:border-[#D4A853]/50 transition-colors"
                                >
                                  <img
                                    src={`${API_BASE}${url}`}
                                    alt={`Generated image ${idx + 1}`}
                                    className="h-full w-full object-cover"
                                    loading="lazy"
                                  />
                                  <span className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-[10px] text-center py-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
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
                          <div className="rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2 space-y-1">
                            <p className="text-xs text-red-400">
                              {errorMsg}
                            </p>
                            <div className="flex items-center gap-3">
                              {job.error_message && (
                                <button
                                  className="text-xs text-red-400/70 underline hover:no-underline"
                                  onClick={() => toggleError(job.job_id)}
                                >
                                  {isExpanded ? "Hide raw error" : "Show raw error"}
                                </button>
                              )}
                              <button
                                className="text-xs text-red-400/70 hover:text-red-400 underline hover:no-underline"
                                disabled={deletingJobs.has(job.job_id)}
                                onClick={() => deleteJob(job.job_id)}
                              >
                                {deletingJobs.has(job.job_id) ? "Deleting..." : "Delete"}
                              </button>
                            </div>
                            {isExpanded && job.error_message && (
                              <pre className="mt-2 whitespace-pre-wrap break-all text-xs text-red-400 font-mono max-h-32 overflow-y-auto">
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

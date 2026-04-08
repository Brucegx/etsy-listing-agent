"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ImageUploader } from "@/components/image-uploader";
import { ListingDisplay } from "@/components/listing-display";
import { ImageGrid } from "@/components/image-grid";
import { WorkflowPipeline } from "@/components/workflow-pipeline";
import { NavBar } from "@/components/nav-bar";
import { ImageStudioForm } from "@/components/image-studio-form";
import { useSSE } from "@/lib/use-sse";
import { useAuth } from "@/lib/auth";
import { API_BASE } from "@/lib/api";
import type { GenerateResults, ImageResult, ImageStrategy, SSEEvent, ImageConfig } from "@/types";

/** How long (ms) the "Job submitted" button stays disabled after a successful submit */
const POST_SUBMIT_LOCK_MS = 5000;

interface SubmitBanner {
  type: "success" | "error";
  message: string;
}

// --- Unauthenticated landing page ---

function DemoPreview({ file }: { file: File }) {
  const [previewUrl, setPreviewUrl] = useState<string>("");

  useEffect(() => {
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  return (
    <div className="rounded-xl overflow-hidden border border-[#E8E8E3] bg-white shadow-sm">
      <div className="relative aspect-square max-h-64 bg-[#F5F5F0] flex items-center justify-center overflow-hidden">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={previewUrl}
          alt="Your product"
          className="max-h-full max-w-full object-contain"
        />
        {/* Blur overlay with "preview only" notice */}
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/40 backdrop-blur-sm">
          <svg
            className="h-8 w-8 text-white mb-2"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z"
            />
          </svg>
          <p className="text-white text-sm font-medium text-center px-4">
            Sign in to generate AI listings &amp; product photos
          </p>
        </div>
      </div>
      <div className="p-4 space-y-2">
        <div className="h-4 rounded bg-[#E8E8E3] w-3/4 animate-pulse" />
        <div className="h-3 rounded bg-[#F5F5F0] w-full animate-pulse" />
        <div className="h-3 rounded bg-[#F5F5F0] w-5/6 animate-pulse" />
      </div>
    </div>
  );
}

function LandingPage() {
  const [demoFile, setDemoFile] = useState<File | null>(null);

  return (
    <div className="min-h-screen bg-[#FAFAF9]">
      {/* Header */}
      <header className="border-b border-[#E8E8E3] bg-white/80 backdrop-blur-xl sticky top-0 z-10">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-2">
            <span
              className="text-lg font-bold tracking-tight"
              style={{ color: "#D4A853", textShadow: "0 0 20px rgba(212,168,83,0.3)" }}
            >
              Luma
            </span>
            <span className="text-sm font-medium text-[#1A1A1A]">Studio</span>
          </div>
          <a
            href={`${API_BASE}/api/auth/login`}
            className="inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold transition-opacity hover:opacity-90"
            style={{ background: "#D4A853", color: "#FFFFFF" }}
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Sign in with Google
          </a>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-16 space-y-20">
        {/* Hero */}
        <section className="text-center space-y-6 hero-gradient py-8">
          <div className="inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-medium" style={{ background: "rgba(212,168,83,0.12)", color: "#D4A853", border: "1px solid rgba(212,168,83,0.2)" }}>
            <span>AI-powered product photography</span>
          </div>
          <h2 className="text-4xl sm:text-5xl font-bold text-[#1A1A1A] leading-tight">
            Transform raw photos into{" "}
            <span style={{ color: "#D4A853" }}>studio-quality images</span>
          </h2>
          <p className="text-lg text-[#737373] max-w-2xl mx-auto">
            Upload your product photos and let AI generate professional studio imagery
            — white backgrounds, lifestyle scenes, macro detail shots, and more.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <a
              href={`${API_BASE}/api/auth/login`}
              className="inline-flex items-center gap-2 rounded-lg px-8 py-3 text-base font-semibold shadow-md transition-opacity hover:opacity-90"
              style={{ background: "#D4A853", color: "#FFFFFF" }}
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  fill="#FFFFFF"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#FFFFFF"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FFFFFF"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="#FFFFFF"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Get started free
            </a>
            <span className="text-sm text-[#A3A3A3]">
              No credit card required
            </span>
          </div>
        </section>

        {/* Features */}
        <section className="grid sm:grid-cols-3 gap-6">
          {[
            {
              icon: (
                <svg className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
                </svg>
              ),
              title: "AI Scene Composition",
              desc: "AI plans the perfect shot — white backgrounds, lifestyle scenes, macro details, and packaging.",
            },
            {
              icon: (
                <svg className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6.827 6.175A2.31 2.31 0 0 1 5.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 0 0-1.134-.175 2.31 2.31 0 0 1-1.64-1.055l-.822-1.316a2.192 2.192 0 0 0-1.736-1.039 48.774 48.774 0 0 0-5.232 0 2.192 2.192 0 0 0-1.736 1.039l-.821 1.316Z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 12.75a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0ZM18.75 10.5h.008v.008h-.008V10.5Z" />
                </svg>
              ),
              title: "Studio-Quality Output",
              desc: "Gemini generates professional product imagery across multiple creative directions in one click.",
            },
            {
              icon: (
                <svg className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                </svg>
              ),
              title: "Instant Results",
              desc: "Submit a job, get an email when complete. No waiting — check your results in the Jobs dashboard.",
            },
          ].map(({ icon, title, desc }) => (
            <Card key={title} className="border-[#E8E8E3] bg-white shadow-sm">
              <CardContent className="pt-6 space-y-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-lg" style={{ background: "rgba(212,168,83,0.10)", color: "#D4A853" }}>
                  {icon}
                </span>
                <h3 className="font-semibold text-[#1A1A1A]">
                  {title}
                </h3>
                <p className="text-sm text-[#737373]">{desc}</p>
              </CardContent>
            </Card>
          ))}
        </section>

        {/* Demo area */}
        <section className="space-y-6">
          <div className="text-center space-y-2">
            <h3 className="text-2xl font-bold text-[#1A1A1A]">
              Try it — upload a photo to preview
            </h3>
            <p className="text-[#737373] text-sm">
              Sign in to run the full AI generation pipeline.
            </p>
          </div>
          <div className="grid sm:grid-cols-2 gap-8 items-start max-w-3xl mx-auto">
            {/* Upload area */}
            <div className="space-y-3">
              <DemoUploadZone onFile={setDemoFile} hasFile={!!demoFile} />
              {demoFile && (
                <a
                  href={`${API_BASE}/api/auth/login`}
                  className="flex w-full items-center justify-center gap-2 rounded-lg px-6 py-3 text-sm font-semibold transition-opacity hover:opacity-90"
                  style={{ background: "#D4A853", color: "#FFFFFF" }}
                >
                  Sign in to generate images
                  <svg
                    className="h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3"
                    />
                  </svg>
                </a>
              )}
            </div>
            {/* Preview area */}
            <div>
              {demoFile ? (
                <DemoPreview file={demoFile} />
              ) : (
                <div className="rounded-xl border-2 border-dashed border-[#E8E8E3] bg-[#F5F5F0] aspect-square max-h-64 flex flex-col items-center justify-center gap-3 text-[#A3A3A3]">
                  <svg
                    className="h-12 w-12"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1}
                    viewBox="0 0 24 24"
                  >
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <circle cx="8.5" cy="8.5" r="1.5" />
                    <path d="m21 15-5-5L5 21" />
                  </svg>
                  <p className="text-sm">Preview appears here</p>
                </div>
              )}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-[#E8E8E3] py-8 text-center text-sm text-[#A3A3A3]">
        Luma Studio &mdash; AI-powered product photography
      </footer>
    </div>
  );
}

function DemoUploadZone({
  onFile,
  hasFile,
}: {
  onFile: (f: File) => void;
  hasFile: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFiles = useCallback(
    (list: FileList | null) => {
      if (!list || list.length === 0) return;
      onFile(list[0]);
    },
    [onFile]
  );

  return (
    <button
      type="button"
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={(e) => {
        e.preventDefault();
        setDragOver(false);
      }}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFiles(e.dataTransfer.files);
      }}
      aria-label="Upload one product photo for demo preview"
      className={`w-full rounded-xl border-2 border-dashed p-8 flex flex-col items-center gap-3 transition-colors focus:outline-none focus:ring-2 focus:ring-[#D4A853] ${
        dragOver
          ? "border-[#D4A853] bg-[rgba(212,168,83,0.06)]"
          : hasFile
            ? "border-green-400 bg-green-50"
            : "border-[#E8E8E3] bg-[#F5F5F0] hover:border-[#D4D4CF]"
      }`}
    >
      {hasFile ? (
        <>
          <svg
            className="h-8 w-8 text-green-500"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
            />
          </svg>
          <p className="text-sm text-green-600 font-medium">
            Photo uploaded — sign in to generate
          </p>
        </>
      ) : (
        <>
          <svg
            className="h-8 w-8 text-[#A3A3A3]"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5"
            />
          </svg>
          <p className="text-sm font-medium text-[#737373]">
            Drop a product photo here
          </p>
          <p className="text-xs text-[#A3A3A3]">
            1 image preview only — sign in for full generation
          </p>
        </>
      )}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
        aria-hidden="true"
        tabIndex={-1}
      />
    </button>
  );
}

// ─── Image Studio submit handler (standalone, no SSE) ──────────────────────

async function submitImageStudioJob(
  files: File[],
  productInfo: string,
  config: ImageConfig
): Promise<{ job_id: string }> {
  const formData = new FormData();
  for (const file of files) formData.append("images", file);
  if (config.category) formData.append("category", config.category);
  formData.append("count", String(config.count));
  formData.append("aspect_ratio", config.aspect_ratio);
  formData.append("additional_prompt", config.additional_prompt);
  if (productInfo) formData.append("product_info", productInfo);
  formData.append("model", config.model);
  formData.append("resolution", config.resolution);

  const res = await fetch(`${API_BASE}/api/jobs/image-studio`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = Array.isArray(err.detail)
      ? err.detail.map((e: { msg?: string; loc?: string[] }) => `${e.loc?.join(".")}: ${e.msg}`).join("; ")
      : err.detail || "Failed to submit Image Studio job";
    if (res.status === 402) {
      throw Object.assign(new Error(detail), { status: 402 });
    }
    throw new Error(detail);
  }

  return res.json();
}

// ─── Authenticated home hub ─────────────────────────────────────────────────

function AuthenticatedHome() {
  const { user } = useAuth();

  // Hub mode state
  const [activeMode, setActiveMode] = useState<"hub" | "full_listing" | "image_studio">("hub");

  // Full Listing state
  const [files, setFiles] = useState<File[]>([]);
  const [material, setMaterial] = useState("");
  const [size, setSize] = useState("");
  const [results, setResults] = useState<GenerateResults | null>(null);
  const [generatedImages, setGeneratedImages] = useState<ImageResult[]>([]);
  const [imageProgress, setImageProgress] = useState({ total: 10, completed: 0 });
  const [promptProgress, setPromptProgress] = useState({ total: 10, completed: 0 });
  const [strategy, setStrategy] = useState<ImageStrategy | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Image Studio state
  const [studioSubmitting, setStudioSubmitting] = useState(false);
  const [studioLocked, setStudioLocked] = useState(false);
  const studioTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cleanup studioTimerRef on unmount to prevent state updates on unmounted components
  useEffect(() => {
    return () => {
      if (studioTimerRef.current) clearTimeout(studioTimerRef.current);
    };
  }, []);

  // Recent jobs for hub view
  interface RecentJob {
    job_id: string;
    product_id: string;
    job_type?: string;
    status: string;
    created_at: string;
  }
  const [recentJobs, setRecentJobs] = useState<RecentJob[]>([]);

  useEffect(() => {
    fetch(`${API_BASE}/api/jobs`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.jobs) setRecentJobs(data.jobs.slice(0, 5));
      })
      .catch(() => {});
  }, []);

  // P0 submit feedback state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitBanner, setSubmitBanner] = useState<SubmitBanner | null>(null);
  const [postSubmitLocked, setPostSubmitLocked] = useState(false);
  const postSubmitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleEvent = useCallback((event: SSEEvent) => {
    if (event.event === "strategy_complete") {
      setStrategy(event.data.strategy);
    }
    if (event.event === "progress" && event.data.node === "prompt_node") {
      setPromptProgress((prev) => ({ ...prev, completed: prev.completed + 1 }));
    }
    if (event.event === "image_complete") {
      setGeneratedImages((prev) => [...prev, event.data]);
      setImageProgress((prev) => ({ ...prev, completed: prev.completed + 1 }));
    }
    if (event.event === "image_done") {
      setImageProgress({ total: event.data.total, completed: event.data.total - event.data.failed });
    }
  }, []);

  const handleComplete = useCallback((data: unknown) => {
    const d = data as { results?: GenerateResults };
    if (d.results) {
      setResults(d.results);
      if (d.results.strategy) setStrategy(d.results.strategy);
    }
  }, []);

  const { events, isRunning, start, stop } = useSSE({
    onEvent: handleEvent,
    onComplete: handleComplete,
    onError: (msg) => {
      setError(msg);
      setSubmitBanner({ type: "error", message: msg });
    },
  });

  const canGenerate =
    files.length > 0 &&
    material.trim() !== "" &&
    size.trim() !== "" &&
    !isSubmitting &&
    !postSubmitLocked;

  const handleGenerate = useCallback(async () => {
    if (isSubmitting || postSubmitLocked) return;

    setResults(null);
    setGeneratedImages([]);
    setImageProgress({ total: 10, completed: 0 });
    setPromptProgress({ total: 10, completed: 0 });
    setStrategy(null);
    setError(null);
    setSubmitBanner(null);
    setIsSubmitting(true);

    try {
      const formData = new FormData();
      for (const file of files) formData.append("images", file);
      formData.append("material", material.trim());
      formData.append("size", size.trim());

      start("/api/generate/upload", formData);

      setSubmitBanner({
        type: "success",
        message: "Job created! Track progress in Jobs →",
      });

      setPostSubmitLocked(true);
      if (postSubmitTimerRef.current) clearTimeout(postSubmitTimerRef.current);
      postSubmitTimerRef.current = setTimeout(() => {
        setPostSubmitLocked(false);
      }, POST_SUBMIT_LOCK_MS);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to submit job";
      setSubmitBanner({ type: "error", message: msg });
    } finally {
      setIsSubmitting(false);
    }
  }, [files, material, size, start, isSubmitting, postSubmitLocked]);

  const handleImageStudioSubmit = useCallback(
    async (studioFiles: File[], productInfo: string, config: ImageConfig) => {
      if (studioSubmitting || studioLocked) return;
      setStudioSubmitting(true);
      setSubmitBanner(null);
      try {
        await submitImageStudioJob(studioFiles, productInfo, config);
        setSubmitBanner({
          type: "success",
          message: "Image Studio job created! Track progress in Jobs →",
        });
        setStudioLocked(true);
        if (studioTimerRef.current) clearTimeout(studioTimerRef.current);
        studioTimerRef.current = setTimeout(() => setStudioLocked(false), POST_SUBMIT_LOCK_MS);
      } catch (err) {
        const isInsufficientCredits =
          err instanceof Error && (err as Error & { status?: number }).status === 402;
        const msg = isInsufficientCredits
          ? "Insufficient credits — please contact support to top up your balance."
          : err instanceof Error
          ? err.message
          : "Failed to submit Image Studio job";
        setSubmitBanner({ type: "error", message: msg });
      } finally {
        setStudioSubmitting(false);
      }
    },
    [studioSubmitting, studioLocked]
  );

  const hasResults = results?.listing || generatedImages.length > 0 || strategy;

  const generateButtonLabel = isSubmitting
    ? "Submitting…"
    : postSubmitLocked
    ? "Job Submitted"
    : "Generate listing";

  const inputClass =
    "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50";

  // Hub view — choose workflow
  if (activeMode === "hub" && !isRunning && !hasResults) {
    return (
      <div className="min-h-screen bg-[#FAFAF9]">
        <NavBar />

        <main className="mx-auto max-w-4xl px-4 py-12 space-y-10">
          <div className="text-center space-y-2">
            <h2 className="text-2xl font-bold text-[#1A1A1A]">
              What would you like to create?
            </h2>
            <p className="text-[#737373] text-sm">
              Choose a workflow to get started
            </p>
          </div>

          <div className="grid sm:grid-cols-3 gap-5">
            {/* Full Listing — Coming Soon */}
            <div
              className="relative text-left rounded-xl border border-[#E8E8E3] bg-white p-6 opacity-40 cursor-not-allowed shadow-sm"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-[#F5F5F0] text-[#A3A3A3] mb-4">
                <svg className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25z" />
                </svg>
              </div>
              <h3 className="font-semibold text-[#A3A3A3]">
                Full Listing
              </h3>
              <p className="mt-1 text-sm text-[#A3A3A3]">
                SEO title, tags, description + 10 AI product photos.
              </p>
              <span className="mt-3 inline-flex items-center gap-1 text-xs font-medium bg-[#F5F5F0] text-[#A3A3A3] px-2 py-0.5 rounded-full">
                Coming Soon
              </span>
            </div>

            {/* Image Studio */}
            <button
              type="button"
              onClick={() => { setActiveMode("image_studio"); setSubmitBanner(null); }}
              className="text-left rounded-xl border border-[#E8E8E3] bg-white p-6 hover:border-[#D4A853]/50 hover:shadow-md transition-all group focus:outline-none focus:ring-2 focus:ring-[#D4A853] shadow-sm"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-lg mb-4 transition-colors" style={{ background: "rgba(212,168,83,0.12)", color: "#D4A853" }}>
                <svg className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M13.5 12a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                </svg>
              </div>
              <h3 className="font-semibold text-[#1A1A1A] group-hover:text-[#D4A853] transition-colors">
                Image Studio
              </h3>
              <p className="mt-1 text-sm text-[#737373]">
                Generate custom product photos — white bg, scene, model or detail.
              </p>
              <span className="mt-3 inline-flex items-center gap-1 text-sm font-medium" style={{ color: "#D4A853" }}>
                Open studio
                <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                </svg>
              </span>
            </button>

            {/* Batch Processing — Coming Soon */}
            <div
              className="relative text-left rounded-xl border border-[#E8E8E3] bg-white p-6 opacity-40 cursor-not-allowed shadow-sm"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-[#F5F5F0] text-[#A3A3A3] mb-4">
                <svg className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
                </svg>
              </div>
              <h3 className="font-semibold text-[#A3A3A3]">
                Batch Processing
              </h3>
              <p className="mt-1 text-sm text-[#A3A3A3]">
                Process multiple products at once with an Excel catalog.
              </p>
              <span className="mt-3 inline-flex items-center gap-1 text-xs font-medium bg-[#F5F5F0] text-[#A3A3A3] px-2 py-0.5 rounded-full">
                Coming Soon
              </span>
            </div>
          </div>

          {/* Recent jobs */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-medium text-[#A3A3A3] uppercase tracking-widest">
                Recent jobs
              </h3>
              {recentJobs.length > 0 && (
                <Link href="/jobs" className="text-xs text-[#D4A853] hover:underline">View all</Link>
              )}
            </div>
            {recentJobs.length === 0 ? (
              <div className="rounded-lg border border-dashed border-[#E8E8E3] py-8 text-center">
                <p className="text-sm text-[#A3A3A3]">
                  Your recent generation jobs will appear here.
                </p>
              </div>
            ) : (
              <ul className="space-y-2">
                {recentJobs.map((job) => (
                  <li key={job.job_id}>
                    <Link
                      href={`/jobs/${job.job_id}`}
                      className="flex items-center justify-between rounded-lg border border-[#E8E8E3] bg-white px-4 py-3 hover:border-[#D4D4CF] hover:shadow-sm transition-all"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-sm font-medium text-[#1A1A1A] truncate">
                          {job.product_id}
                        </span>
                        {job.job_type === "image_only" && (
                          <span className="shrink-0 text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded" style={{ background: "rgba(212,168,83,0.12)", color: "#D4A853" }}>
                            Studio
                          </span>
                        )}
                      </div>
                      <span className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${
                        job.status === "completed"
                          ? "bg-green-50 text-green-700"
                          : job.status === "failed"
                          ? "bg-red-50 text-red-700"
                          : "bg-gray-100 text-gray-600"
                      }`}>
                        {job.status}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </main>
      </div>
    );
  }

  // Image Studio form view
  if (activeMode === "image_studio") {
    return (
      <div className="min-h-screen bg-[#FAFAF9]">
        <NavBar />

        <main className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
          {/* Header + back */}
          <div className="flex items-center gap-3 mb-6">
            <button
              type="button"
              onClick={() => { setActiveMode("hub"); setSubmitBanner(null); }}
              className="inline-flex items-center gap-1.5 text-sm text-[#737373] hover:text-[#1A1A1A] transition-colors"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
              </svg>
              Back
            </button>
            <div className="h-4 w-px bg-[#E8E8E3]" />
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-md" style={{ background: "rgba(212,168,83,0.10)", color: "#D4A853" }}>
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909" />
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                </svg>
              </span>
              <h2 className="text-lg font-bold text-[#1A1A1A]">Image Studio</h2>
              <span className="text-xs font-medium px-1.5 py-0.5 rounded" style={{ background: "rgba(212,168,83,0.10)", color: "#D4A853" }}>
                Beta
              </span>
            </div>
          </div>

          {/* Submit feedback banner */}
          {submitBanner && (
            <div
              role="status"
              aria-live="polite"
              className={`mb-4 flex items-center justify-between rounded-lg border px-4 py-3 text-sm ${
                submitBanner.type === "success"
                  ? "border-green-200 bg-green-50 text-green-700"
                  : "border-red-200 bg-red-50 text-red-700"
              }`}
            >
              <span>{submitBanner.message}</span>
              {submitBanner.type === "success" && (
                <Link
                  href="/jobs"
                  className="ml-4 shrink-0 font-medium underline underline-offset-2 hover:no-underline"
                >
                  Go to Jobs
                </Link>
              )}
              <button
                type="button"
                onClick={() => setSubmitBanner(null)}
                className="ml-4 shrink-0 text-current opacity-60 hover:opacity-100"
                aria-label="Dismiss"
              >
                ✕
              </button>
            </div>
          )}

          <ImageStudioForm
            onSubmit={handleImageStudioSubmit}
            isSubmitting={studioSubmitting}
            isLocked={studioLocked}
            creditBalance={user?.credit_balance}
            isAdmin={user?.is_admin}
          />
        </main>
      </div>
    );
  }

  // Full Listing form + results view
  return (
    <div className="min-h-screen bg-[#FAFAF9]">
      <NavBar />

      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        {/* Header + back */}
        <div className="flex items-center gap-3 mb-6">
          <button
            type="button"
            onClick={() => { setActiveMode("hub"); setSubmitBanner(null); }}
            className="inline-flex items-center gap-1.5 text-sm text-[#737373] hover:text-[#1A1A1A] transition-colors"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
            </svg>
            Back
          </button>
          <div className="h-4 w-px bg-[#E8E8E3]" />
          <h2 className="text-lg font-bold text-[#1A1A1A]">Full Listing</h2>
        </div>

        <Card className="shadow-sm">
          <CardContent className="space-y-5 pt-6">
            <ImageUploader files={files} onChange={setFiles} disabled={isRunning} />

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label htmlFor="material" className="block text-sm font-medium">
                  Material
                </label>
                <input
                  id="material"
                  type="text"
                  value={material}
                  onChange={(e) => setMaterial(e.target.value)}
                  placeholder="e.g. 925 silver, copper"
                  disabled={isRunning}
                  className={inputClass}
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="size" className="block text-sm font-medium">
                  Size
                </label>
                <input
                  id="size"
                  type="text"
                  value={size}
                  onChange={(e) => setSize(e.target.value)}
                  placeholder="e.g. 2cm × 1.5cm"
                  disabled={isRunning}
                  className={inputClass}
                />
              </div>
            </div>

            <div className="flex items-center gap-3">
              {isRunning ? (
                <Button variant="destructive" onClick={stop}>
                  Stop
                </Button>
              ) : (
                <Button
                  onClick={handleGenerate}
                  disabled={!canGenerate}
                  size="lg"
                  aria-busy={isSubmitting}
                >
                  {isSubmitting && (
                    <svg
                      className="mr-2 h-4 w-4 animate-spin"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                      />
                    </svg>
                  )}
                  {generateButtonLabel}
                </Button>
              )}
              {!canGenerate && !isRunning && !isSubmitting && !postSubmitLocked && (
                <p className="text-xs text-muted-foreground">
                  Upload at least one image and fill in material + size.
                </p>
              )}
            </div>

            {/* Submit feedback banner */}
            {submitBanner && (
              <div
                role="status"
                aria-live="polite"
                className={`flex items-center justify-between rounded-lg border px-4 py-3 text-sm ${
                  submitBanner.type === "success"
                    ? "border-[#4ADE80]/20 bg-[#4ADE80]/[0.06] text-[#4ADE80]"
                    : "border-[#F87171]/20 bg-[#F87171]/[0.06] text-[#F87171]"
                }`}
              >
                <span>{submitBanner.message}</span>
                {submitBanner.type === "success" && (
                  <Link
                    href="/jobs"
                    className="ml-4 shrink-0 font-medium underline underline-offset-2 hover:no-underline"
                  >
                    Go to Jobs
                  </Link>
                )}
                <button
                  type="button"
                  onClick={() => setSubmitBanner(null)}
                  className="ml-4 shrink-0 text-current opacity-60 hover:opacity-100"
                  aria-label="Dismiss"
                >
                  ✕
                </button>
              </div>
            )}

            {isRunning && (
              <p className="rounded-lg border border-border/60 bg-accent/30 px-4 py-2.5 text-sm text-muted-foreground">
                Generation is running in the background — you can close this tab
                and we&apos;ll email you when it&apos;s done.
              </p>
            )}
          </CardContent>
        </Card>

        {error && (
          <div className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 p-4">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        {events.length > 0 && (
          <Card className="mt-4 shadow-sm">
            <CardContent className="pt-6 pb-4">
              <WorkflowPipeline
                events={events}
                isRunning={isRunning}
                promptProgress={promptProgress}
                imageProgress={imageProgress}
              />
            </CardContent>
          </Card>
        )}

        {hasResults && (
          <Tabs defaultValue="listing" className="mt-6">
            <TabsList>
              <TabsTrigger value="listing">Listing</TabsTrigger>
              <TabsTrigger value="images">
                Images
                {generatedImages.length > 0 && (
                  <span className="ml-1.5 text-xs text-muted-foreground">
                    ({generatedImages.length})
                  </span>
                )}
              </TabsTrigger>
              {strategy && <TabsTrigger value="strategy">Strategy</TabsTrigger>}
            </TabsList>

            <TabsContent value="listing" className="mt-4">
              {results?.listing ? (
                <ListingDisplay listing={results.listing} />
              ) : (
                <div className="rounded-lg border border-dashed border-border p-12 text-center">
                  <p className="text-sm text-muted-foreground">
                    {isRunning ? "Generating listing…" : "No listing data yet."}
                  </p>
                </div>
              )}
            </TabsContent>

            <TabsContent value="images" className="mt-4">
              <ImageGrid
                images={generatedImages}
                isGenerating={isRunning}
                imageProgress={imageProgress}
              />
            </TabsContent>

            {strategy && (
              <TabsContent value="strategy" className="mt-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Image Strategy</CardTitle>
                    <p className="text-sm text-muted-foreground">
                      {strategy.analysis.target_customer}
                    </p>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {strategy.slots.map((slot) => (
                      <div
                        key={slot.slot}
                        className="flex items-start gap-3 rounded-md border border-border/60 p-3"
                      >
                        <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold">
                          {slot.slot}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-sm font-medium">
                              {slot.type.replace(/_/g, " ")}
                            </span>
                            <span
                              className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                                slot.category === "required"
                                  ? "bg-[#60A5FA]/10 text-[#60A5FA]"
                                  : "bg-[#A78BFA]/10 text-[#A78BFA]"
                              }`}
                            >
                              {slot.category}
                            </span>
                          </div>
                          <p className="mt-0.5 text-xs text-muted-foreground">
                            {slot.description}
                          </p>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </TabsContent>
            )}
          </Tabs>
        )}
      </main>
    </div>
  );
}

// --- Root page: gate on auth ---

export default function Home() {
  const { loading, isAuthenticated } = useAuth();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#FAFAF9]">
        <div className="flex flex-col items-center gap-3 text-[#A3A3A3]">
          <svg
            className="h-8 w-8 animate-spin"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
          <p className="text-sm">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LandingPage />;
  }

  return <AuthenticatedHome />;
}

"use client";

import { useState, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ImageUploader } from "@/components/image-uploader";
import { ListingDisplay } from "@/components/listing-display";
import { ImageGrid } from "@/components/image-grid";
import { WorkflowPipeline } from "@/components/workflow-pipeline";
import { NavBar } from "@/components/nav-bar";
import { useSSE } from "@/lib/use-sse";
import { useAuth } from "@/lib/auth";
import { API_BASE } from "@/lib/api";
import type { GenerateResults, ImageResult, ImageStrategy, SSEEvent } from "@/types";

/** How long (ms) the "Job submitted" button stays disabled after a successful submit */
const POST_SUBMIT_LOCK_MS = 5000;

interface SubmitBanner {
  type: "success" | "error";
  message: string;
}

// --- Unauthenticated landing page ---

function DemoPreview({ file }: { file: File }) {
  const [previewUrl] = useState(() => URL.createObjectURL(file));

  return (
    <div className="rounded-xl overflow-hidden border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-sm">
      <div className="relative aspect-square max-h-64 bg-gray-50 dark:bg-gray-800 flex items-center justify-center overflow-hidden">
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
        <div className="h-4 rounded bg-gray-200 dark:bg-gray-700 w-3/4 animate-pulse" />
        <div className="h-3 rounded bg-gray-100 dark:bg-gray-800 w-full animate-pulse" />
        <div className="h-3 rounded bg-gray-100 dark:bg-gray-800 w-5/6 animate-pulse" />
      </div>
    </div>
  );
}

function LandingPage() {
  const [demoFile, setDemoFile] = useState<File | null>(null);

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 via-white to-amber-50 dark:from-gray-950 dark:via-gray-900 dark:to-gray-950">
      {/* Header */}
      <header className="border-b bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-2">
            <span className="text-xl">🛍️</span>
            <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">
              Etsy Listing Agent
            </h1>
          </div>
          <a
            href={`${API_BASE}/api/auth/login`}
            className="inline-flex items-center gap-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 shadow-sm hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
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
        <section className="text-center space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full bg-orange-100 dark:bg-orange-900/40 px-4 py-1.5 text-sm font-medium text-orange-700 dark:text-orange-300">
            <span>✨</span>
            <span>AI-powered Etsy listings in minutes</span>
          </div>
          <h2 className="text-4xl sm:text-5xl font-bold text-gray-900 dark:text-gray-100 leading-tight">
            Turn product photos into{" "}
            <span className="text-orange-500">optimized Etsy listings</span>
          </h2>
          <p className="text-lg text-gray-600 dark:text-gray-400 max-w-2xl mx-auto">
            Upload your jewelry or craft photos and let our AI write SEO titles,
            keyword tags, and descriptions — plus generate professional product
            images in 10 creative styles.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <a
              href={`${API_BASE}/api/auth/login`}
              className="inline-flex items-center gap-2 rounded-lg bg-orange-500 hover:bg-orange-600 px-8 py-3 text-base font-semibold text-white shadow-md transition-colors"
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  fill="white"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="white"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="white"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="white"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Get started free with Google
            </a>
            <span className="text-sm text-gray-400 dark:text-gray-500">
              No credit card required
            </span>
          </div>
        </section>

        {/* Features */}
        <section className="grid sm:grid-cols-3 gap-6">
          {[
            {
              icon: "🧠",
              title: "AI Strategy",
              desc: "Claude analyzes your product and plans 10 images covering key customer purchase moments.",
            },
            {
              icon: "🖼️",
              title: "Professional Photos",
              desc: "Gemini generates studio-quality product images in 10 creative directions — lifestyle, macro, packaging and more.",
            },
            {
              icon: "📝",
              title: "SEO Listings",
              desc: "Titles, tags, and descriptions written for Etsy search — optimized for your product category.",
            },
          ].map(({ icon, title, desc }) => (
            <Card key={title} className="border-0 shadow-sm bg-white dark:bg-gray-900">
              <CardContent className="pt-6 space-y-2">
                <span className="text-3xl">{icon}</span>
                <h3 className="font-semibold text-gray-900 dark:text-gray-100">
                  {title}
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">{desc}</p>
              </CardContent>
            </Card>
          ))}
        </section>

        {/* Demo area */}
        <section className="space-y-6">
          <div className="text-center space-y-2">
            <h3 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
              Try it — upload a photo to preview
            </h3>
            <p className="text-gray-500 dark:text-gray-400 text-sm">
              Sign in with Google to run the full AI generation pipeline.
            </p>
          </div>
          <div className="grid sm:grid-cols-2 gap-8 items-start max-w-3xl mx-auto">
            {/* Upload area */}
            <div className="space-y-3">
              <DemoUploadZone onFile={setDemoFile} hasFile={!!demoFile} />
              {demoFile && (
                <a
                  href={`${API_BASE}/api/auth/login`}
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-orange-500 hover:bg-orange-600 px-6 py-3 text-sm font-semibold text-white transition-colors"
                >
                  Sign in to generate full listing
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
                <div className="rounded-xl border-2 border-dashed border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 aspect-square max-h-64 flex flex-col items-center justify-center gap-3 text-gray-400 dark:text-gray-600">
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

      <footer className="border-t py-8 text-center text-sm text-gray-400 dark:text-gray-600">
        Etsy Listing Agent &mdash; Built with Claude &amp; Gemini
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
      className={`w-full rounded-xl border-2 border-dashed p-8 flex flex-col items-center gap-3 transition-colors focus:outline-none focus:ring-2 focus:ring-orange-400 ${
        dragOver
          ? "border-orange-400 bg-orange-50 dark:bg-orange-950/30"
          : hasFile
            ? "border-green-400 bg-green-50 dark:bg-green-950/20"
            : "border-gray-300 bg-white dark:bg-gray-900 hover:border-gray-400 dark:border-gray-700"
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
          <p className="text-sm text-green-700 dark:text-green-400 font-medium">
            Photo uploaded — sign in to generate
          </p>
        </>
      ) : (
        <>
          <svg
            className="h-8 w-8 text-gray-400"
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
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Drop a product photo here
          </p>
          <p className="text-xs text-gray-400 dark:text-gray-500">
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

// --- Authenticated home hub ---

function AuthenticatedHome() {
  const [files, setFiles] = useState<File[]>([]);
  const [material, setMaterial] = useState("");
  const [size, setSize] = useState("");
  const [results, setResults] = useState<GenerateResults | null>(null);
  const [generatedImages, setGeneratedImages] = useState<ImageResult[]>([]);
  const [imageProgress, setImageProgress] = useState({ total: 10, completed: 0 });
  const [promptProgress, setPromptProgress] = useState({ total: 10, completed: 0 });
  const [strategy, setStrategy] = useState<ImageStrategy | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showUploadForm, setShowUploadForm] = useState(false);

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

    // Reset state
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

      // Start the SSE stream — this internally does the POST and streams results.
      // We do a quick pre-flight check: if the fetch immediately fails (non-2xx),
      // use-sse calls onError. We show a success banner right after start() begins
      // (before stream completes) so the user knows the job was accepted.
      start("/api/generate/upload", formData);

      // Show success banner immediately after the request is accepted.
      // The stream continues in the background.
      setSubmitBanner({
        type: "success",
        message: "Job created! Track progress in Jobs →",
      });

      // Lock the button for POST_SUBMIT_LOCK_MS to prevent duplicate submissions.
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

  const hasResults = results?.listing || generatedImages.length > 0 || strategy;

  const generateButtonLabel = isSubmitting
    ? "Submitting…"
    : postSubmitLocked
    ? "Job Submitted"
    : "Generate listing";

  const inputClass =
    "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50";

  // Hub view — choose workflow
  if (!showUploadForm && !isRunning && !hasResults) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
        <header className="border-b bg-white dark:bg-gray-900">
          <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
            <div className="flex items-center gap-2">
              <span>🛍️</span>
              <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Etsy Listing Agent
              </h1>
            </div>
            <a
              href={`${API_BASE}/api/auth/logout`}
              className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              Sign out
            </a>
          </div>
        </header>

        <main className="mx-auto max-w-4xl px-4 py-12 space-y-10">
          <div className="text-center space-y-2">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
              How would you like to start?
            </h2>
            <p className="text-gray-500 dark:text-gray-400 text-sm">
              Choose a workflow to generate your Etsy listings
            </p>
          </div>

          <div className="grid sm:grid-cols-2 gap-6">
            {/* Upload workflow */}
            <button
              type="button"
              onClick={() => setShowUploadForm(true)}
              className="text-left rounded-xl border-2 border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-6 hover:border-orange-400 hover:shadow-md transition-all group focus:outline-none focus:ring-2 focus:ring-orange-400"
            >
              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-orange-100 dark:bg-orange-900/40 text-orange-600 dark:text-orange-400 group-hover:bg-orange-200 dark:group-hover:bg-orange-900/60 transition-colors">
                  <svg
                    className="h-6 w-6"
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
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100 group-hover:text-orange-600 dark:group-hover:text-orange-400">
                    Upload Photos
                  </h3>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Upload product images directly from your computer. Best for
                    one-off listings.
                  </p>
                  <span className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-orange-500">
                    Get started
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
                  </span>
                </div>
              </div>
            </button>

            {/* Google Drive workflow */}
            <a
              href="/dashboard"
              className="text-left rounded-xl border-2 border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-6 hover:border-blue-400 hover:shadow-md transition-all group focus:outline-none focus:ring-2 focus:ring-blue-400 block"
            >
              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 group-hover:bg-blue-200 dark:group-hover:bg-blue-900/60 transition-colors">
                  <svg
                    className="h-6 w-6"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                  >
                    <path d="M4.433 22 1 16.25l5.217-9.083L9.65 13H8.35l-5 8.667zm2.65 0 5.217-9.083-2.434-4.25h4.868L20 22zM15.85 13l2.433-4.25L20.566 2H8.35l2.433 4.167zM11.133 8.75l-1.35-2.333h4.434l-1.35 2.333z" />
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100 group-hover:text-blue-600 dark:group-hover:text-blue-400">
                    From Google Drive
                  </h3>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Browse your Drive folders. Best for batch processing with an
                    Excel product catalog.
                  </p>
                  <span className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-blue-500">
                    Open Drive browser
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
                  </span>
                </div>
              </div>
            </a>
          </div>

          {/* Recent jobs placeholder */}
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
              Recent jobs
            </h3>
            <div className="rounded-lg border border-dashed border-gray-200 dark:border-gray-700 py-8 text-center">
              <p className="text-sm text-gray-400 dark:text-gray-600">
                Your recent generation jobs will appear here.
              </p>
            </div>
          </div>
        </main>
      </div>
    );
  }

  // Upload form + results view
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      {/* Header */}
      <header className="border-b bg-white dark:bg-gray-900">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            {!isRunning && (
              <button
                type="button"
                onClick={() => {
                  setShowUploadForm(false);
                  setResults(null);
                  setGeneratedImages([]);
                  setStrategy(null);
                  setError(null);
                }}
                className="mr-1 rounded-md p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                aria-label="Back to home"
              >
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
                    d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18"
                  />
                </svg>
              </button>
            )}
            <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Etsy Listing Agent
            </h1>
          </div>
          <a
            href={`${API_BASE}/api/auth/logout`}
            className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            Sign out
          </a>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
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
                    ? "border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-300"
                    : "border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-400"
                }`}
              >
                <span>{submitBanner.message}</span>
                {submitBanner.type === "success" && (
                  <a
                    href="/jobs"
                    className="ml-4 shrink-0 font-medium underline underline-offset-2 hover:no-underline"
                  >
                    Go to Jobs
                  </a>
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
                                  ? "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-400"
                                  : "bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-400"
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
      <div className="flex h-screen items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="flex flex-col items-center gap-3 text-gray-400">
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

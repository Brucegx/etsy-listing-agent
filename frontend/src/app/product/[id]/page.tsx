"use client";

import { useParams, useSearchParams, useRouter } from "next/navigation";
import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { NavBar } from "@/components/nav-bar";
import { GenerationProgress } from "@/components/generation-progress";
import { ListingDisplay } from "@/components/listing-display";
import { PromptCards } from "@/components/prompt-cards";
import { ImageGrid } from "@/components/image-grid";
import { StatusBadge } from "@/components/status-badge";
import { useSSE } from "@/lib/use-sse";
import { api, API_BASE } from "@/lib/api";
import type { GenerateResults, ImageResult, SSEEvent, Job } from "@/types";

// ── Stage progress bar (used during SSE streaming) ────────────────────────────

const STAGE_ORDER = [
  "preprocess",
  "strategy",
  "prompt",
  "image_gen",
  "listing",
  "complete",
] as const;

type Stage = (typeof STAGE_ORDER)[number];

const STAGE_LABELS: Record<Stage, string> = {
  preprocess: "Pre-processing",
  strategy: "Analysing product",
  prompt: "Building prompts",
  image_gen: "Generating images",
  listing: "Writing listing",
  complete: "Done",
};

function getStageName(node?: string): Stage {
  if (!node) return "preprocess";
  for (const s of STAGE_ORDER) {
    if (node.toLowerCase().includes(s)) return s;
  }
  return "preprocess";
}

interface StageProgressProps {
  currentStage: Stage;
  isRunning: boolean;
  progressPct: number;
}

function StageProgress({ currentStage, isRunning, progressPct }: StageProgressProps) {
  const currentIdx = STAGE_ORDER.indexOf(currentStage);

  return (
    <div className="space-y-3">
      {/* Stage stepper */}
      <div className="flex items-center gap-0.5 overflow-x-auto pb-1">
        {STAGE_ORDER.map((stage, idx) => {
          const isActive = stage === currentStage;
          const isDone = idx < currentIdx;

          return (
            <div key={stage} className="flex items-center">
              <div
                className={`flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-all ${
                  isDone
                    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400"
                    : isActive
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                {isDone ? "✓" : null}
                {STAGE_LABELS[stage]}
              </div>
              {idx < STAGE_ORDER.length - 1 && (
                <div
                  className={`mx-0.5 h-px w-4 shrink-0 ${
                    isDone ? "bg-emerald-300 dark:bg-emerald-700" : "bg-border"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Progress bar */}
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all duration-700"
          style={{ width: `${progressPct}%` }}
        />
      </div>

      {isRunning && (
        <p className="rounded-lg border border-border/60 bg-accent/30 px-4 py-2.5 text-sm text-muted-foreground">
          Running in the background — you can{" "}
          <span className="font-medium">close this tab</span> and we&apos;ll
          email you when your listing is ready. Track progress in{" "}
          <a href="/jobs" className="font-medium text-foreground underline underline-offset-2">
            Jobs
          </a>
          .
        </p>
      )}
    </div>
  );
}

// ── Completed job image gallery ───────────────────────────────────────────────

interface CompletedJobGalleryProps {
  job: Job;
}

function CompletedJobGallery({ job }: CompletedJobGalleryProps) {
  if (!job.image_urls || job.image_urls.length === 0) return null;

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <StatusBadge status="completed" />
        <span className="text-sm text-muted-foreground">
          {job.image_urls.length} images generated
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
        {job.image_urls.map((url, i) => (
          <a
            key={i}
            href={`${API_BASE}${url}`}
            target="_blank"
            rel="noopener noreferrer"
            className="group overflow-hidden rounded-lg border border-border/60 bg-muted"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`${API_BASE}${url}`}
              alt={`Generated image ${i + 1}`}
              className="aspect-square w-full object-cover transition-transform duration-200 group-hover:scale-105"
              loading="lazy"
            />
          </a>
        ))}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ProductPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const productId = params.id as string;

  const folderId = searchParams.get("folder") || "";
  const excelFileId = searchParams.get("excel") || "";
  const category = searchParams.get("category") || "";

  const [results, setResults] = useState<GenerateResults | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [generatedImages, setGeneratedImages] = useState<ImageResult[]>([]);
  const [imageProgress, setImageProgress] = useState({ total: 9, completed: 0 });
  const [currentStage, setCurrentStage] = useState<Stage>("preprocess");
  const [progressPct, setProgressPct] = useState(0);
  const [completedJob, setCompletedJob] = useState<Job | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  const { events, isRunning, start, stop } = useSSE({
    onEvent: (event: SSEEvent) => {
      if (event.event === "progress") {
        const stage = getStageName(event.data.node);
        setCurrentStage(stage);
        const stageIdx = STAGE_ORDER.indexOf(stage);
        setProgressPct(Math.round((stageIdx / (STAGE_ORDER.length - 1)) * 90));
      }
      if (event.event === "image_complete") {
        const img = event.data as ImageResult;
        setGeneratedImages((prev) => [...prev, img]);
        setImageProgress((prev) => ({ ...prev, completed: prev.completed + 1 }));
      }
      if (event.event === "image_done") {
        const d = event.data as { total: number; failed: number };
        setImageProgress((prev) => ({ ...prev, total: d.total }));
      }
    },
    onComplete: (data) => {
      const d = data as { results?: GenerateResults; job_id?: string };
      if (d.results) setResults(d.results);
      if (d.job_id) setJobId(d.job_id);
      setCurrentStage("complete");
      setProgressPct(100);
    },
  });

  const handleGenerate = useCallback(() => {
    setResults(null);
    setGeneratedImages([]);
    setImageProgress({ total: 9, completed: 0 });
    setCurrentStage("preprocess");
    setProgressPct(0);
    setCompletedJob(null);
    setJobId(null);
    setSaveStatus(null);
    start("/api/generate/single", {
      drive_folder_id: folderId,
      product_id: productId,
      category: category,
      excel_file_id: excelFileId,
    });
  }, [folderId, productId, category, excelFileId, start]);

  const handleSave = async () => {
    if (!results || !folderId) return;
    setSaving(true);
    setSaveStatus(null);
    try {
      const resp = await api.save.results({
        drive_folder_id: folderId,
        product_id: productId,
        listing: results.listing as Record<string, unknown> | undefined,
        prompts: results.prompts as Record<string, unknown> | undefined,
        product_data: results.product_data as Record<string, unknown> | undefined,
      });
      setSaveStatus(`Saved ${resp.uploaded.length} file(s) to Drive`);
    } catch (err) {
      setSaveStatus(
        `Save failed: ${err instanceof Error ? err.message : "Unknown error"}`
      );
    } finally {
      setSaving(false);
    }
  };

  const listing = results?.listing;
  const prompts = results?.prompts?.prompts;
  const promptCount = prompts?.length || 0;
  const showProgress = events.length > 0 || isRunning;

  return (
    <div className="min-h-screen bg-background">
      <NavBar />

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        {/* Header */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => router.back()}>
              ← Back
            </Button>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">
                {productId}
              </h1>
              {category && (
                <p className="text-sm capitalize text-muted-foreground">{category}</p>
              )}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {isRunning && (
              <Button variant="outline" size="sm" onClick={stop}>
                Stop
              </Button>
            )}
            <Button
              onClick={handleGenerate}
              disabled={isRunning || !folderId}
              size="sm"
            >
              {isRunning ? "Generating…" : "Generate"}
            </Button>
            {results && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleSave}
                disabled={saving}
              >
                {saving ? "Saving…" : "Save to Drive"}
              </Button>
            )}
          </div>
        </div>

        {/* Missing folder warning */}
        {!folderId && (
          <Card className="mb-4">
            <CardContent className="py-6">
              <p className="text-sm text-muted-foreground text-center">
                Missing folder context. Please navigate from the dashboard.
              </p>
            </CardContent>
          </Card>
        )}

        {/* Save status */}
        {saveStatus && (
          <p
            className={`mb-4 text-sm ${
              saveStatus.startsWith("Save failed")
                ? "text-destructive"
                : "text-muted-foreground"
            }`}
          >
            {saveStatus}
          </p>
        )}

        {/* Job ID link */}
        {jobId && (
          <div className="mb-4 flex items-center gap-2 text-xs text-muted-foreground">
            <span>Job</span>
            <code className="rounded bg-muted px-1.5 py-0.5 font-mono">{jobId}</code>
            <a href="/jobs" className="underline underline-offset-2 hover:text-foreground">
              View in Jobs
            </a>
          </div>
        )}

        {/* Stage progress */}
        {showProgress && (
          <Card className="mb-6 shadow-sm">
            <CardContent className="pt-5 pb-4">
              <StageProgress
                currentStage={currentStage}
                isRunning={isRunning}
                progressPct={progressPct}
              />
            </CardContent>
          </Card>
        )}

        {/* Verbose SSE log (collapsed by default) */}
        {events.length > 0 && (
          <details className="mb-6">
            <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
              Show detailed log ({events.length} events)
            </summary>
            <div className="mt-2 rounded-xl border border-border/60 bg-muted/30 p-4">
              <GenerationProgress events={events} isRunning={isRunning} />
            </div>
          </details>
        )}

        {/* Completed job gallery */}
        {completedJob && (
          <div className="mb-6">
            <CompletedJobGallery job={completedJob} />
          </div>
        )}

        {/* Results tabs */}
        <Tabs defaultValue="listing">
          <TabsList>
            <TabsTrigger value="listing">Listing</TabsTrigger>
            <TabsTrigger value="prompts">
              Prompts{promptCount > 0 && ` (${promptCount})`}
            </TabsTrigger>
            <TabsTrigger value="images">
              Images
              {generatedImages.length > 0 && ` (${generatedImages.length})`}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="listing" className="mt-4">
            {listing ? (
              <ListingDisplay listing={listing} />
            ) : (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Etsy Listing</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    {isRunning
                      ? "Generating listing…"
                      : "Click Generate to create the listing."}
                  </p>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="prompts" className="mt-4">
            {prompts && prompts.length > 0 ? (
              <PromptCards prompts={prompts} />
            ) : (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Image Prompts</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    {isRunning
                      ? "Building prompts…"
                      : "Prompts will appear here after generation."}
                  </p>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="images" className="mt-4">
            <ImageGrid
              images={generatedImages}
              isGenerating={isRunning}
              imageProgress={imageProgress}
            />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

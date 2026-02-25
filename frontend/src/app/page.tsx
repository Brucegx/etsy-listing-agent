"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
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

// ── Feature list ────────────────────────────────────────────────────────────

const FEATURES = [
  {
    icon: "📸",
    title: "10 AI Product Photos",
    description:
      "Studio-quality photography across angles, lifestyle scenes, and macro shots — all generated from your raw product images.",
  },
  {
    icon: "✍️",
    title: "SEO-Optimised Listings",
    description:
      "Title, description, and 13 tags crafted around Etsy search patterns and your target customer's exact search intent.",
  },
  {
    icon: "⚡",
    title: "Async — Close the Tab",
    description:
      "Generation runs in the background. We'll email you when your listing is ready. No waiting, no babysitting.",
  },
  {
    icon: "🔁",
    title: "Repeatable at Scale",
    description:
      "API access for batch processing. Feed in a folder, get back listings. Works with Google Drive or direct upload.",
  },
];

const STEPS = [
  { step: "01", title: "Upload photos", desc: "Drop your raw product images — phone shots are fine." },
  { step: "02", title: "AI analyses", desc: "Claude studies your product and plans 10 image directions." },
  { step: "03", title: "Images generated", desc: "Gemini renders professional photos for each direction." },
  { step: "04", title: "Listing created", desc: "SEO-rich title, description, and tags — ready to paste." },
];

// ── Landing hero (unauthenticated) ──────────────────────────────────────────

function LandingHero() {
  return (
    <section className="relative overflow-hidden py-20 sm:py-28">
      <div className="hero-gradient pointer-events-none absolute inset-0" aria-hidden="true" />
      <div className="relative mx-auto max-w-4xl px-4 text-center sm:px-6">
        <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/80 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur">
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: "oklch(0.62 0.17 48)" }}
            aria-hidden="true"
          />
          Powered by Claude + Gemini 2.5 Flash
        </div>
        <h1 className="mt-4 text-4xl font-bold tracking-tight text-foreground sm:text-5xl lg:text-6xl">
          Professional Etsy listings
          <br />
          <span style={{ color: "oklch(0.62 0.17 48)" }}>without a photographer</span>
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-base text-muted-foreground sm:text-lg">
          Upload raw product images. Get 10 studio-quality AI photos, an
          SEO-optimised title, description, and 13 tags — in minutes, not days.
        </p>
        <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
          <a href={`${API_BASE}/api/auth/login`}>
            <Button size="lg" className="w-full sm:w-auto">
              Get started free
            </Button>
          </a>
          <Link href="#how-it-works">
            <Button variant="outline" size="lg" className="w-full sm:w-auto">
              See how it works
            </Button>
          </Link>
        </div>
      </div>
    </section>
  );
}

// ── How it works ─────────────────────────────────────────────────────────────

function HowItWorks() {
  return (
    <section id="how-it-works" className="py-16 sm:py-20">
      <div className="mx-auto max-w-5xl px-4 sm:px-6">
        <h2 className="text-center text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
          From raw photo to live listing in 4 steps
        </h2>
        <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s) => (
            <div
              key={s.step}
              className="relative rounded-xl border border-border/60 bg-card p-5 shadow-sm"
            >
              <div
                className="mb-3 text-3xl font-bold tabular-nums"
                style={{ color: "oklch(0.62 0.17 48 / 0.3)" }}
              >
                {s.step}
              </div>
              <h3 className="font-semibold text-foreground">{s.title}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{s.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Features ─────────────────────────────────────────────────────────────────

function Features() {
  return (
    <section className="border-t border-border/40 bg-muted/30 py-16 sm:py-20">
      <div className="mx-auto max-w-5xl px-4 sm:px-6">
        <h2 className="text-center text-2xl font-semibold tracking-tight sm:text-3xl">
          Everything a top Etsy seller needs
        </h2>
        <div className="mt-10 grid gap-5 sm:grid-cols-2">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="flex gap-4 rounded-xl border border-border/60 bg-card p-5 shadow-sm"
            >
              <span className="shrink-0 text-2xl" role="img" aria-label="">
                {f.icon}
              </span>
              <div>
                <h3 className="font-semibold text-foreground">{f.title}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{f.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── CTA banner ───────────────────────────────────────────────────────────────

function CTABanner() {
  return (
    <section className="py-16 sm:py-20">
      <div className="mx-auto max-w-3xl px-4 text-center sm:px-6">
        <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Ready to 10× your listing quality?
        </h2>
        <p className="mt-3 text-muted-foreground">
          Sign in with Google and start generating in under a minute.
        </p>
        <a href={`${API_BASE}/api/auth/login`} className="mt-6 inline-block">
          <Button size="lg">Sign in with Google — it&apos;s free</Button>
        </a>
      </div>
    </section>
  );
}

// ── Upload tool (authenticated quick-try) ────────────────────────────────────

function UploadTool() {
  const [files, setFiles] = useState<File[]>([]);
  const [material, setMaterial] = useState("");
  const [size, setSize] = useState("");
  const [results, setResults] = useState<GenerateResults | null>(null);
  const [generatedImages, setGeneratedImages] = useState<ImageResult[]>([]);
  const [imageProgress, setImageProgress] = useState({ total: 10, completed: 0 });
  const [promptProgress, setPromptProgress] = useState({ total: 10, completed: 0 });
  const [strategy, setStrategy] = useState<ImageStrategy | null>(null);
  const [error, setError] = useState<string | null>(null);

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
    onError: (msg) => setError(msg),
  });

  const canGenerate = files.length > 0 && material.trim() !== "" && size.trim() !== "";

  const handleGenerate = useCallback(() => {
    setResults(null);
    setGeneratedImages([]);
    setImageProgress({ total: 10, completed: 0 });
    setPromptProgress({ total: 10, completed: 0 });
    setStrategy(null);
    setError(null);
    const formData = new FormData();
    for (const file of files) formData.append("images", file);
    formData.append("material", material.trim());
    formData.append("size", size.trim());
    start("/api/generate/upload", formData);
  }, [files, material, size, start]);

  const hasResults = results?.listing || generatedImages.length > 0 || strategy;

  const inputClass =
    "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <section className="border-t border-border/40 bg-muted/20 py-12 sm:py-16">
      <div className="mx-auto max-w-3xl px-4 sm:px-6">
        <h2 className="mb-1 text-xl font-semibold">Try it now</h2>
        <p className="mb-6 text-sm text-muted-foreground">
          Upload photos, fill in details, and hit Generate.
        </p>

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
                <Button onClick={handleGenerate} disabled={!canGenerate} size="lg">
                  Generate listing
                </Button>
              )}
              {!canGenerate && !isRunning && (
                <p className="text-xs text-muted-foreground">
                  Upload at least one image and fill in material + size.
                </p>
              )}
            </div>

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
      </div>
    </section>
  );
}

// ── Footer ────────────────────────────────────────────────────────────────────

function Footer() {
  return (
    <footer className="border-t border-border/40 py-8">
      <div className="mx-auto max-w-7xl px-4 text-center text-xs text-muted-foreground sm:px-6">
        © {new Date().getFullYear()} Etsy Listing Agent. Built with Claude + Gemini.
      </div>
    </footer>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Home() {
  const { isAuthenticated, loading } = useAuth();

  return (
    <div className="min-h-screen bg-background">
      <NavBar />

      {!loading && (
        <>
          {!isAuthenticated && (
            <>
              <LandingHero />
              <HowItWorks />
              <Features />
              <CTABanner />
            </>
          )}

          <UploadTool />
        </>
      )}

      <Footer />
    </div>
  );
}

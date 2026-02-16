"use client";

import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ImageUploader } from "@/components/image-uploader";
import { ListingDisplay } from "@/components/listing-display";
import { ImageGrid } from "@/components/image-grid";
import { WorkflowPipeline } from "@/components/workflow-pipeline";
import { useSSE } from "@/lib/use-sse";
import type { GenerateResults, ImageResult, ImageStrategy, SSEEvent } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
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

  const handleError = useCallback((msg: string) => {
    setError(msg);
  }, []);

  const { events, isRunning, start, stop } = useSSE({
    onEvent: handleEvent,
    onComplete: handleComplete,
    onError: handleError,
  });

  const canGenerate = files.length > 0 && material.trim() !== "" && size.trim() !== "";

  const handleGenerate = useCallback(() => {
    // Reset state
    setResults(null);
    setGeneratedImages([]);
    setImageProgress({ total: 10, completed: 0 });
    setPromptProgress({ total: 10, completed: 0 });
    setStrategy(null);
    setError(null);

    const formData = new FormData();
    for (const file of files) {
      formData.append("images", file);
    }
    formData.append("material", material.trim());
    formData.append("size", size.trim());

    start("/api/generate/upload", formData);
  }, [files, material, size, start]);

  const hasResults = results?.listing || generatedImages.length > 0 || strategy;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      {/* Header */}
      <header className="border-b bg-white dark:bg-gray-900">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
          <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Etsy Listing Agent
          </h1>
          <a
            href={`${API_BASE}/api/auth/login`}
            className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            Login
          </a>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-4 py-8 space-y-8">
        {/* Upload Form */}
        <Card>
          <CardHeader>
            <CardTitle>Generate Etsy Listing</CardTitle>
            <p className="text-sm text-muted-foreground">
              Upload product images and enter details to generate an optimized Etsy listing with AI product images.
            </p>
          </CardHeader>
          <CardContent className="space-y-6">
            <ImageUploader
              files={files}
              onChange={setFiles}
              disabled={isRunning}
            />

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label
                  htmlFor="material"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5"
                >
                  Material
                </label>
                <input
                  id="material"
                  type="text"
                  value={material}
                  onChange={(e) => setMaterial(e.target.value)}
                  placeholder="e.g. 925 silver, copper, brass"
                  disabled={isRunning}
                  className="
                    w-full rounded-md border border-gray-300 bg-white
                    px-3 py-2 text-sm
                    placeholder:text-gray-400
                    focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500
                    disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-500
                    dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100
                    dark:placeholder:text-gray-500 dark:focus:border-blue-400
                    dark:disabled:bg-gray-900
                  "
                />
              </div>
              <div>
                <label
                  htmlFor="size"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5"
                >
                  Size
                </label>
                <input
                  id="size"
                  type="text"
                  value={size}
                  onChange={(e) => setSize(e.target.value)}
                  placeholder="e.g. 2cm x 1.5cm"
                  disabled={isRunning}
                  className="
                    w-full rounded-md border border-gray-300 bg-white
                    px-3 py-2 text-sm
                    placeholder:text-gray-400
                    focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500
                    disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-500
                    dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100
                    dark:placeholder:text-gray-500 dark:focus:border-blue-400
                    dark:disabled:bg-gray-900
                  "
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
                >
                  Generate
                </Button>
              )}
              {!canGenerate && !isRunning && (
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  Upload at least one image and fill in material and size.
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Error */}
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950">
            <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
          </div>
        )}

        {/* Workflow Pipeline */}
        {events.length > 0 && (
          <Card>
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

        {/* Results */}
        {hasResults && (
          <Tabs defaultValue="listing">
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
              {strategy && (
                <TabsTrigger value="strategy">Strategy</TabsTrigger>
              )}
            </TabsList>

            <TabsContent value="listing" className="mt-4">
              {results?.listing ? (
                <ListingDisplay listing={results.listing} />
              ) : (
                <div className="rounded-lg border border-dashed border-gray-300 p-12 text-center dark:border-gray-600">
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {isRunning
                      ? "Generating listing..."
                      : "No listing data available."}
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
                  <CardContent className="space-y-4">
                    <div className="grid gap-2">
                      {strategy.slots.map((slot) => (
                        <div
                          key={slot.slot}
                          className="flex items-start gap-3 rounded-md border p-3"
                        >
                          <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gray-100 text-xs font-medium dark:bg-gray-800">
                            {slot.slot}
                          </span>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium">
                                {slot.type.replace(/_/g, " ")}
                              </span>
                              <span
                                className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                                  slot.category === "required"
                                    ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
                                    : "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300"
                                }`}
                              >
                                {slot.category}
                              </span>
                            </div>
                            <p className="text-xs text-muted-foreground mt-0.5">
                              {slot.description}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
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

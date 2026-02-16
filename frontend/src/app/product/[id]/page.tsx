"use client";

import { useParams, useSearchParams, useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { GenerationProgress } from "@/components/generation-progress";
import { ListingDisplay } from "@/components/listing-display";
import { PromptCards } from "@/components/prompt-cards";
import { ImageGrid } from "@/components/image-grid";
import { useSSE } from "@/lib/use-sse";
import { api } from "@/lib/api";
import type { GenerateResults, ImageResult, SSEEvent } from "@/types";

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

  const { events, isRunning, start, stop } = useSSE({
    onEvent: (event: SSEEvent) => {
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
      const d = data as { results?: GenerateResults };
      if (d.results) setResults(d.results);
    },
  });

  const handleGenerate = () => {
    setResults(null);
    setGeneratedImages([]);
    setImageProgress({ total: 9, completed: 0 });
    start("/api/generate/single", {
      drive_folder_id: folderId,
      product_id: productId,
      category: category,
      excel_file_id: excelFileId,
    });
  };

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
      setSaveStatus(`Save failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setSaving(false);
    }
  };

  const listing = results?.listing;
  const prompts = results?.prompts?.prompts;
  const promptCount = prompts?.length || 0;

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => router.back()}>
            &larr; Back
          </Button>
          <div>
            <h1 className="text-2xl font-bold">Product: {productId}</h1>
            {category && (
              <p className="text-sm text-muted-foreground capitalize">
                {category}
              </p>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          {isRunning && (
            <Button variant="outline" onClick={stop}>
              Stop
            </Button>
          )}
          <Button onClick={handleGenerate} disabled={isRunning || !folderId}>
            {isRunning ? "Generating..." : "Generate"}
          </Button>
          {results && (
            <Button variant="outline" onClick={handleSave} disabled={saving}>
              {saving ? "Saving..." : "Save to Drive"}
            </Button>
          )}
        </div>
      </div>

      {!folderId && (
        <Card>
          <CardContent className="py-6">
            <p className="text-sm text-muted-foreground text-center">
              Missing folder context. Please navigate from the dashboard.
            </p>
          </CardContent>
        </Card>
      )}

      {saveStatus && (
        <p className={`text-sm ${saveStatus.startsWith("Save failed") ? "text-destructive" : "text-muted-foreground"}`}>
          {saveStatus}
        </p>
      )}

      {(events.length > 0 || isRunning) && (
        <GenerationProgress events={events} isRunning={isRunning} />
      )}

      <Tabs defaultValue="listing">
        <TabsList>
          <TabsTrigger value="listing">Listing</TabsTrigger>
          <TabsTrigger value="prompts">
            Prompts{promptCount > 0 && ` (${promptCount})`}
          </TabsTrigger>
          <TabsTrigger value="images">Images</TabsTrigger>
        </TabsList>

        <TabsContent value="listing">
          {listing ? (
            <ListingDisplay listing={listing} />
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Etsy Listing</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Click &quot;Generate&quot; to create the listing.
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="prompts">
          {prompts && prompts.length > 0 ? (
            <PromptCards prompts={prompts} />
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Image Prompts (9)</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  NanoBanana prompts will appear here after generation.
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="images">
          <ImageGrid
            images={generatedImages}
            isGenerating={isRunning}
            imageProgress={imageProgress}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

"use client";

import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { NavBar } from "@/components/nav-bar";
import { DriveBrowser } from "@/components/drive-browser";
import type { DriveFolder, DriveFile } from "@/types";

const EXCEL_MIME_TYPES = new Set([
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.google-apps.spreadsheet",
]);

export default function Dashboard() {
  const { user, loading, isAuthenticated } = useAuth();
  const router = useRouter();
  const [selectedFolder, setSelectedFolder] = useState<DriveFolder | null>(null);
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [products, setProducts] = useState<string[]>([]);
  const [category, setCategory] = useState("");
  const [excelFileId, setExcelFileId] = useState<string | null>(null);
  const [loadingProducts, setLoadingProducts] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push("/");
    }
  }, [loading, isAuthenticated, router]);

  useEffect(() => {
    if (!selectedFolder) {
      setFiles([]);
      setProducts([]);
      setCategory("");
      setExcelFileId(null);
      setError(null);
      return;
    }

    async function loadProducts() {
      setLoadingProducts(true);
      setError(null);
      try {
        const fileData = await api.drive.listFiles(selectedFolder!.id);
        setFiles(fileData.files);

        const excelFile = fileData.files.find((f) => EXCEL_MIME_TYPES.has(f.mimeType));

        if (!excelFile) {
          setError("No Excel file found in this folder.");
          setProducts([]);
          setLoadingProducts(false);
          return;
        }

        setExcelFileId(excelFile.id);

        const data = await api.products.list(selectedFolder!.id, excelFile.id);
        setProducts(data.products);
        setCategory(data.category);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load products");
        setProducts([]);
      } finally {
        setLoadingProducts(false);
      }
    }

    loadProducts();
  }, [selectedFolder]);

  // Image preview thumbnails for files in the selected folder
  const imageFiles = files.filter((f) => f.mimeType.startsWith("image/"));

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <div className="flex h-[60vh] items-center justify-center">
          <div className="space-y-2 text-center">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent mx-auto" />
            <p className="text-sm text-muted-foreground">Loading…</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <NavBar />

      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight">Drive Dashboard</h1>
          {user && (
            <p className="mt-0.5 text-sm text-muted-foreground">
              Signed in as {user.email}
            </p>
          )}
        </div>

        <p className="mb-6 text-sm text-muted-foreground">
          Select a Google Drive folder containing your product images and an
          Excel spreadsheet. Each row in the sheet becomes a product to generate.
        </p>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Drive browser */}
          <DriveBrowser onFolderSelect={setSelectedFolder} />

          {/* Folder details & product list */}
          <div className="space-y-4">
            {selectedFolder ? (
              <Card className="shadow-sm">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">{selectedFolder.name}</CardTitle>
                    <Button
                      onClick={() => setSelectedFolder(null)}
                      variant="ghost"
                      size="sm"
                    >
                      Clear
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Image previews */}
                  {imageFiles.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-medium text-muted-foreground">
                        Images in folder ({imageFiles.length})
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {imageFiles.slice(0, 6).map((f) => (
                          <div
                            key={f.id}
                            className="h-14 w-14 overflow-hidden rounded-lg border border-border/60 bg-muted"
                          >
                            {/* Drive thumbnail via Drive API embed URL */}
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                              src={`https://drive.google.com/thumbnail?id=${f.id}&sz=w120`}
                              alt={f.name}
                              className="h-full w-full object-cover"
                              loading="lazy"
                            />
                          </div>
                        ))}
                        {imageFiles.length > 6 && (
                          <div className="flex h-14 w-14 items-center justify-center rounded-lg border border-border/60 bg-muted text-xs text-muted-foreground">
                            +{imageFiles.length - 6}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Product list */}
                  {loadingProducts ? (
                    <div className="space-y-2">
                      {[1, 2, 3].map((i) => (
                        <Skeleton key={i} className="h-10 w-full" />
                      ))}
                    </div>
                  ) : error ? (
                    <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3">
                      <p className="text-sm text-destructive">{error}</p>
                    </div>
                  ) : products.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No products found.</p>
                  ) : (
                    <div>
                      <p className="mb-2 text-xs text-muted-foreground">
                        {products.length} product{products.length !== 1 ? "s" : ""}
                        {category && ` · "${category}"`}
                      </p>
                      <ul className="space-y-1">
                        {products.map((productId) => (
                          <li key={productId}>
                            <button
                              className="group w-full flex items-center justify-between rounded-lg border border-border/40 bg-background px-3 py-2.5 text-sm transition-colors hover:border-primary/40 hover:bg-accent text-left"
                              onClick={() => {
                                const params = new URLSearchParams({
                                  folder: selectedFolder.id,
                                  excel: excelFileId || "",
                                  category: category,
                                });
                                router.push(
                                  `/product/${encodeURIComponent(productId)}?${params}`
                                );
                              }}
                            >
                              <span className="font-medium">{productId}</span>
                              <span className="text-muted-foreground text-xs group-hover:text-foreground transition-colors">
                                Generate →
                              </span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </CardContent>
              </Card>
            ) : (
              <div className="flex h-full min-h-[200px] flex-col items-center justify-center rounded-xl border border-dashed border-border/60 bg-muted/20 px-6 py-12 text-center">
                <span className="mb-2 text-3xl" role="img" aria-label="">📂</span>
                <p className="text-sm text-muted-foreground">
                  Select a folder on the left to preview its contents.
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

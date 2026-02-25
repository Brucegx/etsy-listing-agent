"use client";

import { useAuth } from "@/lib/auth";
import { api, API_BASE } from "@/lib/api";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { NavBar } from "@/components/nav-bar";
import { DriveBrowser } from "@/components/drive-browser";
import { UsageGuide } from "@/components/usage-guide";
import type { DriveFolder, DriveFile } from "@/types";

const EXCEL_MIME_TYPES = new Set([
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.google-apps.spreadsheet",
]);

/**
 * Detects whether an API error looks like a Google OAuth token expiry.
 * Common signals: 401 response, "Invalid Credentials", "Token has been expired".
 */
function isSessionExpiredError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  const msg = err.message.toLowerCase();
  return (
    msg.includes("401") ||
    msg.includes("invalid credentials") ||
    msg.includes("token has been expired") ||
    msg.includes("token expired") ||
    msg.includes("unauthorized") ||
    msg.includes("access token")
  );
}

function SessionExpiredBanner() {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/40 p-4 flex items-start gap-3">
      <svg
        className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
        />
      </svg>
      <div className="flex-1 min-w-0 space-y-2">
        <p className="text-sm font-medium text-amber-800 dark:text-amber-300">
          Your Google session has expired
        </p>
        <p className="text-sm text-amber-700 dark:text-amber-400">
          Please sign in again to reconnect your Google Drive.
        </p>
        <a
          href={`${API_BASE}/api/auth/login`}
          className="inline-flex items-center gap-2 rounded-md bg-amber-600 hover:bg-amber-700 px-4 py-2 text-sm font-medium text-white transition-colors"
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
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
          Sign in with Google
        </a>
      </div>
    </div>
  );
}

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
  const [sessionExpired, setSessionExpired] = useState(false);
  const [showGuide, setShowGuide] = useState(false);

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
      setSessionExpired(false);
      return;
    }

    async function loadProducts() {
      setLoadingProducts(true);
      setError(null);
      setSessionExpired(false);
      try {
        const fileData = await api.drive.listFiles(selectedFolder!.id);
        setFiles(fileData.files);

        const excelFile = fileData.files.find((f) => EXCEL_MIME_TYPES.has(f.mimeType));

        if (!excelFile) {
          setError("No Excel or Google Sheets file found in this folder. Add a spreadsheet with product details.");
          setProducts([]);
          setLoadingProducts(false);
          return;
        }

        setExcelFileId(excelFile.id);

        const data = await api.products.list(selectedFolder!.id, excelFile.id);
        setProducts(data.products);
        setCategory(data.category);
      } catch (err) {
        if (isSessionExpiredError(err)) {
          setSessionExpired(true);
          setError(null);
        } else {
          setError(err instanceof Error ? err.message : "Failed to load products");
        }
        setProducts([]);
      } finally {
        setLoadingProducts(false);
      }
    }

    loadProducts();
  }, [selectedFolder]);

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
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Drive Dashboard</h1>
            {user && (
              <p className="mt-0.5 text-sm text-muted-foreground">
                Signed in as {user.email}
              </p>
            )}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowGuide(true)}
            className="text-muted-foreground"
          >
            <svg
              className="h-4 w-4 mr-1.5"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 5.25h.008v.008H12v-.008Z"
              />
            </svg>
            How to organize
          </Button>
        </div>

        <p className="mb-6 text-sm text-muted-foreground">
          Select a Google Drive folder containing your product images and an
          Excel spreadsheet. Each row in the sheet becomes a product to generate.
        </p>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Drive browser */}
          <DriveBrowser
            onFolderSelect={setSelectedFolder}
            onSessionExpired={() => setSessionExpired(true)}
          />

          {/* Folder details & product list */}
          <div className="space-y-4">
            {sessionExpired && <SessionExpiredBanner />}

            {selectedFolder && !sessionExpired && (
              <Card className="shadow-sm">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-base truncate max-w-[200px]" title={selectedFolder.name}>
                      {selectedFolder.name}
                    </CardTitle>
                    <Button
                      onClick={() => setSelectedFolder(null)}
                      variant="ghost"
                      size="sm"
                      className="shrink-0"
                    >
                      Clear
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {loadingProducts ? (
                    <div className="space-y-2" role="status" aria-label="Loading products">
                      {[1, 2, 3].map((i) => (
                        <Skeleton key={i} className="h-10 w-full" />
                      ))}
                      <p className="text-xs text-muted-foreground text-center pt-1">
                        Reading folder contents...
                      </p>
                    </div>
                  ) : error ? (
                    <div className="space-y-3">
                      <div className="flex items-start gap-2 text-sm text-destructive">
                        <svg
                          className="h-4 w-4 shrink-0 mt-0.5"
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
                        <p>{error}</p>
                      </div>
                      <button
                        className="text-xs text-muted-foreground underline hover:text-foreground transition-colors"
                        onClick={() => setShowGuide(true)}
                      >
                        Learn how to set up your folder
                      </button>
                    </div>
                  ) : products.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No products found.
                    </p>
                  ) : (
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground mb-2">
                        {products.length} product{products.length !== 1 ? "s" : ""} found
                        {category && ` in "${category}"`}
                      </p>
                      <ul className="space-y-1">
                        {products.map((productId) => (
                          <li key={productId}>
                            <button
                              className="w-full flex items-center justify-between p-2.5 rounded-md hover:bg-muted text-sm transition-colors text-left"
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
                              <span className="font-medium truncate max-w-[180px]" title={productId}>
                                {productId}
                              </span>
                              <span className="text-muted-foreground text-xs shrink-0">
                                Open &rarr;
                              </span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* File listing for selected folder (non-products context) */}
            {files.length > 0 && !loadingProducts && !error && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-muted-foreground font-normal">
                    Files in folder ({files.length})
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-1">
                    {files.map((f) => (
                      <li
                        key={f.id}
                        className="flex items-center gap-2 text-xs text-muted-foreground py-1"
                      >
                        <svg
                          className="h-3.5 w-3.5 shrink-0"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth={1.5}
                          viewBox="0 0 24 24"
                          aria-hidden="true"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
                          />
                        </svg>
                        <span className="truncate max-w-[220px]" title={f.name}>
                          {f.name}
                        </span>
                        {f.size && (
                          <span className="shrink-0 text-muted-foreground/60">
                            {(parseInt(f.size) / 1024).toFixed(0)} KB
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}

            {!selectedFolder && !sessionExpired && (
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

      {/* Usage guide modal */}
      {showGuide && <UsageGuide onClose={() => setShowGuide(false)} />}
    </div>
  );
}

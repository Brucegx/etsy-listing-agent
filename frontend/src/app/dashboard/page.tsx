"use client";

import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { DriveBrowser } from "@/components/drive-browser";
import type { DriveFolder, DriveFile } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

  // When folder is selected, find the Excel file and fetch products
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
        // List files to find Excel
        const fileData = await api.drive.listFiles(selectedFolder!.id);
        setFiles(fileData.files);

        const excelFile = fileData.files.find((f) =>
          EXCEL_MIME_TYPES.has(f.mimeType)
        );

        if (!excelFile) {
          setError("No Excel file found in this folder.");
          setProducts([]);
          setLoadingProducts(false);
          return;
        }

        setExcelFileId(excelFile.id);

        // Fetch product list
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

  if (loading)
    return (
      <div className="flex h-screen items-center justify-center">
        Loading...
      </div>
    );

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          {user && (
            <p className="text-sm text-muted-foreground">{user.email}</p>
          )}
        </div>
        <Button
          variant="outline"
          onClick={async () => {
            await fetch(`${API_BASE}/api/auth/logout`, {
              method: "POST",
              credentials: "include",
            });
            router.push("/");
          }}
        >
          Logout
        </Button>
      </div>

      <p className="text-muted-foreground mb-6">
        Select a Google Drive folder containing your product images and Excel
        spreadsheet.
      </p>

      <div className="grid gap-6 lg:grid-cols-2">
        <DriveBrowser onFolderSelect={setSelectedFolder} />

        <div className="space-y-4">
          {selectedFolder && (
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">
                    {selectedFolder.name}
                  </CardTitle>
                  <Button
                    onClick={() => setSelectedFolder(null)}
                    variant="ghost"
                    size="sm"
                  >
                    Clear
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {loadingProducts ? (
                  <div className="space-y-2">
                    {[1, 2, 3].map((i) => (
                      <Skeleton key={i} className="h-10 w-full" />
                    ))}
                  </div>
                ) : error ? (
                  <p className="text-sm text-destructive">{error}</p>
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
                            <span className="font-medium">{productId}</span>
                            <span className="text-muted-foreground text-xs">
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
        </div>
      </div>
    </div>
  );
}

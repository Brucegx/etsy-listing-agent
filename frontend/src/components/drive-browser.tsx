"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { DriveFolder } from "@/types";

interface DriveBrowserProps {
  onFolderSelect: (folder: DriveFolder) => void;
  onSessionExpired?: () => void;
}

export function DriveBrowser({ onFolderSelect, onSessionExpired }: DriveBrowserProps) {
  const [folders, setFolders] = useState<DriveFolder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [path, setPath] = useState<{ id: string | null; name: string }[]>([
    { id: null, name: "My Drive" },
  ]);

  const currentParent = path[path.length - 1].id;

  const loadFolders = useCallback(async (parentId: string | null) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.drive.listFolders(parentId || undefined);
      setFolders(data.folders);
    } catch (err) {
      const isSessionErr =
        err instanceof Error &&
        (() => {
          const msg = err.message.toLowerCase();
          return (
            msg.includes("401") ||
            msg.includes("invalid credentials") ||
            msg.includes("token has been expired") ||
            msg.includes("token expired") ||
            msg.includes("unauthorized") ||
            msg.includes("access token")
          );
        })();

      if (isSessionErr && onSessionExpired) {
        onSessionExpired();
        setError(null);
      } else {
        const message =
          err instanceof Error ? err.message : "Failed to load folders";
        setError(message);
      }
      setFolders([]);
    } finally {
      setLoading(false);
    }
  }, [onSessionExpired]);

  useEffect(() => {
    loadFolders(currentParent);
  }, [currentParent, loadFolders]);

  const navigateInto = (folder: DriveFolder) => {
    setPath((prev) => [...prev, { id: folder.id, name: folder.name }]);
  };

  const navigateBack = (index: number) => {
    setPath((prev) => prev.slice(0, index + 1));
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Google Drive</CardTitle>
        {/* Breadcrumb navigation */}
        <nav aria-label="Drive folder breadcrumb">
          <ol className="flex items-center gap-1 text-sm text-muted-foreground flex-wrap">
            {path.map((p, i) => (
              <li key={i} className="flex items-center gap-1">
                {i > 0 && (
                  <span aria-hidden="true" className="text-muted-foreground/50">
                    /
                  </span>
                )}
                <button
                  onClick={() => navigateBack(i)}
                  className={`hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 rounded px-0.5 ${
                    i === path.length - 1
                      ? "font-medium text-foreground"
                      : ""
                  }`}
                  aria-current={i === path.length - 1 ? "location" : undefined}
                >
                  {p.name}
                </button>
              </li>
            ))}
          </ol>
        </nav>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-2" role="status" aria-label="Loading folders">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
            <span className="sr-only">Loading folders...</span>
          </div>
        ) : error ? (
          <div className="text-center py-4 space-y-2">
            <p className="text-sm text-destructive">{error}</p>
            <Button
              size="sm"
              variant="outline"
              onClick={() => loadFolders(currentParent)}
            >
              Retry
            </Button>
          </div>
        ) : folders.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4 text-center">
            No folders found
          </p>
        ) : (
          <ul className="space-y-1" role="list">
            {folders.map((folder) => (
              <li key={folder.id}>
                <div
                  className="flex items-center justify-between p-2 rounded-md hover:bg-muted cursor-pointer transition-colors focus-within:ring-2 focus-within:ring-ring"
                  role="button"
                  tabIndex={0}
                  aria-label={`Open folder ${folder.name}`}
                  onClick={() => navigateInto(folder)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      navigateInto(folder);
                    }
                  }}
                >
                  <span className="flex items-center gap-2 text-sm min-w-0">
                    {/* Folder icon */}
                    <svg
                      className="h-4 w-4 text-muted-foreground shrink-0"
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />
                    </svg>
                    <span className="truncate">{folder.name}</span>
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    className="ml-2 shrink-0"
                    onClick={(e) => {
                      e.stopPropagation();
                      onFolderSelect(folder);
                    }}
                    onKeyDown={(e) => e.stopPropagation()}
                  >
                    Select
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

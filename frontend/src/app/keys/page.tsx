"use client";

import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NavBar } from "@/components/nav-bar";
import { API_BASE } from "@/lib/api";

interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used?: string;
}

export default function KeysPage() {
  const { loading, isAuthenticated } = useAuth();
  const router = useRouter();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [keysLoading, setKeysLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push("/");
    }
  }, [loading, isAuthenticated, router]);

  // Fetch keys from API
  useEffect(() => {
    if (!isAuthenticated) return;
    async function fetchKeys() {
      setKeysLoading(true);
      try {
        const res = await fetch(`${API_BASE}/api/keys`, {
          credentials: "include",
        });
        if (res.ok) {
          const data = await res.json();
          setKeys(data.keys ?? []);
        } else if (res.status === 404) {
          // Endpoint may not be implemented yet — show empty state
          setKeys([]);
        } else {
          setError("Failed to load API keys.");
        }
      } catch {
        // Network error — show empty state rather than crashing
        setKeys([]);
      } finally {
        setKeysLoading(false);
      }
    }
    fetchKeys();
  }, [isAuthenticated]);

  const handleCreate = async () => {
    if (!newKeyName.trim()) return;
    setCreating(true);
    try {
      const res = await fetch(`${API_BASE}/api/keys`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newKeyName.trim() }),
      });
      if (res.ok) {
        const data = await res.json();
        setRevealedKey(data.key);
        setKeys((prev) => [...prev, data.meta]);
        setNewKeyName("");
      } else {
        setError("Failed to create API key.");
      }
    } catch {
      setError("Network error creating API key.");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await fetch(`${API_BASE}/api/keys/${id}`, {
        method: "DELETE",
        credentials: "include",
      });
      setKeys((prev) => prev.filter((k) => k.id !== id));
    } catch {
      setError("Failed to delete API key.");
    }
  };

  const handleCopy = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  const exampleCurl = `curl -X POST https://your-domain.com/api/v1/generate \\
  -H "Authorization: Bearer YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"product_id": "ring-001", "category": "jewelry"}'`;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <NavBar />

      <main className="mx-auto max-w-3xl px-4 py-8 space-y-6">
        {/* Context header — "what is this for?" */}
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-6 space-y-4">
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center rounded-full bg-violet-100 dark:bg-violet-900/40 px-3 py-1 text-xs font-semibold text-violet-700 dark:text-violet-300">
              For Developers
            </span>
            <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">
              Programmatic access to the generation API
            </h2>
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            API keys let you call the listing generation service from your own
            scripts, automations, or integrations — without using the web UI.
            Include the key in the{" "}
            <code className="rounded bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 text-xs font-mono">
              Authorization
            </code>{" "}
            header of every request.
          </p>

          {/* Example curl */}
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400">
              Example request
            </p>
            <div className="relative rounded-lg bg-gray-900 dark:bg-gray-950 border border-gray-700 dark:border-gray-800">
              <pre className="overflow-x-auto px-4 py-3 text-xs text-green-300 font-mono leading-relaxed">
                {exampleCurl}
              </pre>
              <button
                type="button"
                onClick={() => handleCopy(exampleCurl)}
                className="absolute top-2 right-2 rounded-md px-2 py-1 text-xs text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
              >
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-500">
            <svg
              className="h-4 w-4 text-blue-400 shrink-0"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="m11.25 11.25.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z"
              />
            </svg>
            Full OpenAPI documentation is available at{" "}
            <a
              href={`${API_BASE}/api/docs`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-500 hover:underline"
            >
              /api/docs
            </a>
          </div>
        </div>

        {/* Revealed key notice */}
        {revealedKey && (
          <div className="rounded-lg border border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950/40 p-4 space-y-2">
            <p className="text-sm font-medium text-green-800 dark:text-green-300">
              Key created — copy it now. You won&apos;t see it again.
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 rounded bg-white dark:bg-gray-900 border border-green-200 dark:border-green-800 px-3 py-2 text-xs font-mono text-gray-700 dark:text-gray-300 truncate">
                {revealedKey}
              </code>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleCopy(revealedKey)}
              >
                {copied ? "Copied!" : "Copy"}
              </Button>
            </div>
            <button
              className="text-xs text-green-700 dark:text-green-400 underline"
              onClick={() => setRevealedKey(null)}
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/40 p-3">
            <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
          </div>
        )}

        {/* Keys list */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Your API Keys</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {keysLoading ? (
              <div className="space-y-2">
                {[1, 2].map((i) => (
                  <div
                    key={i}
                    className="h-12 rounded-md bg-gray-100 dark:bg-gray-800 animate-pulse"
                  />
                ))}
              </div>
            ) : keys.length === 0 ? (
              <div className="text-center py-6 text-sm text-muted-foreground">
                No API keys yet. Create one below.
              </div>
            ) : (
              <ul className="space-y-2">
                {keys.map((key) => (
                  <li
                    key={key.id}
                    className="flex items-center justify-between rounded-lg border border-gray-200 dark:border-gray-700 px-4 py-3 gap-3"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                        {key.name}
                      </p>
                      <p className="text-xs text-muted-foreground font-mono">
                        {key.prefix}••••••••
                        {key.last_used && ` · Last used ${key.last_used}`}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30 shrink-0"
                      onClick={() => handleDelete(key.id)}
                    >
                      Revoke
                    </Button>
                  </li>
                ))}
              </ul>
            )}

            {/* Create key form */}
            <div className="border-t pt-4 space-y-3">
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Create a new key
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  placeholder="Key name (e.g. My Script)"
                  className="flex-1 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:text-gray-100"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleCreate();
                  }}
                />
                <Button
                  onClick={handleCreate}
                  disabled={creating || !newKeyName.trim()}
                >
                  {creating ? "Creating..." : "Create"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Security notice */}
        <div className="flex items-start gap-2 text-xs text-muted-foreground">
          <svg
            className="h-4 w-4 shrink-0 mt-0.5"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z"
            />
          </svg>
          Keep your API keys private. Do not share them in public repositories or
          client-side code. Revoke any key you suspect has been compromised.
        </div>
      </main>
    </div>
  );
}

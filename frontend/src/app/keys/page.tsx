"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { NavBar } from "@/components/nav-bar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ApiKey, ApiKeyCreated } from "@/types";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(iso));
}

// ── New key dialog ────────────────────────────────────────────────────────────

interface NewKeyFormProps {
  onCreated: (key: ApiKeyCreated) => void;
  onCancel: () => void;
}

function NewKeyForm({ onCreated, onCancel }: NewKeyFormProps) {
  const [name, setName] = useState("");
  const [rateLimit, setRateLimit] = useState(60);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const key = await api.keys.create(name.trim(), rateLimit);
      onCreated(key);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create API key");
    } finally {
      setCreating(false);
    }
  };

  const inputClass =
    "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/30 disabled:opacity-50";

  return (
    <Card className="border-primary/30 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Create new API key</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="key-name" className="block text-sm font-medium">
              Key name
            </label>
            <input
              id="key-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Production, My Script"
              maxLength={255}
              required
              disabled={creating}
              className={inputClass}
            />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="rate-limit" className="block text-sm font-medium">
              Rate limit (requests/minute)
            </label>
            <input
              id="rate-limit"
              type="number"
              value={rateLimit}
              onChange={(e) => setRateLimit(parseInt(e.target.value) || 60)}
              min={1}
              max={6000}
              disabled={creating}
              className={inputClass}
            />
            <p className="text-xs text-muted-foreground">Between 1 and 6,000 rpm.</p>
          </div>
          {error && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={creating || !name.trim()}>
              {creating ? "Creating…" : "Create key"}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
              Cancel
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

// ── Key reveal dialog ─────────────────────────────────────────────────────────

interface NewKeyRevealProps {
  created: ApiKeyCreated;
  onDismiss: () => void;
}

function NewKeyReveal({ created, onDismiss }: NewKeyRevealProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(created.raw_key);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard not available — user can select manually
    }
  };

  return (
    <Card className="border-emerald-400/40 bg-emerald-50/50 dark:bg-emerald-900/20 shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base text-emerald-700 dark:text-emerald-400">
          <span aria-hidden="true">✓</span>
          API key created — save it now
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          This is the only time the key will be shown. Copy it and store it
          securely — it cannot be retrieved later.
        </p>
        <div className="flex items-center gap-2">
          <code className="flex-1 overflow-x-auto rounded-md border border-border/60 bg-background px-3 py-2 font-mono text-xs">
            {created.raw_key}
          </code>
          <Button variant="outline" size="sm" onClick={handleCopy}>
            {copied ? "Copied!" : "Copy"}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Use as bearer token: <code className="text-foreground">Authorization: Bearer {"{key}"}</code>
        </p>
        <Button variant="outline" size="sm" onClick={onDismiss}>
          Done — I&apos;ve saved it
        </Button>
      </CardContent>
    </Card>
  );
}

// ── Key row ───────────────────────────────────────────────────────────────────

interface KeyRowProps {
  apiKey: ApiKey;
  onRevoke: (id: number) => void;
  revoking: boolean;
}

function KeyRow({ apiKey, onRevoke, revoking }: KeyRowProps) {
  return (
    <div
      className={`flex items-start gap-4 rounded-xl border border-border/60 p-4 transition-opacity ${
        apiKey.revoked ? "opacity-50" : "bg-card shadow-sm hover:shadow-md"
      }`}
    >
      {/* Key icon */}
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted text-base">
        {apiKey.revoked ? "🔐" : "🔑"}
      </div>

      {/* Details */}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium text-foreground">{apiKey.name}</span>
          {apiKey.revoked && (
            <span className="rounded-full border border-rose-200 bg-rose-100 px-2 py-0.5 text-xs text-rose-700 dark:border-rose-800 dark:bg-rose-900/40 dark:text-rose-400">
              Revoked
            </span>
          )}
        </div>
        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
          <span>Created {formatDate(apiKey.created_at)}</span>
          <span>{apiKey.rate_limit_rpm} rpm</span>
          {apiKey.last_used_at && (
            <span>Last used {formatDate(apiKey.last_used_at)}</span>
          )}
          {!apiKey.last_used_at && !apiKey.revoked && <span>Never used</span>}
        </div>
        <p className="mt-1.5 font-mono text-xs text-muted-foreground">
          eta_{'·'.repeat(20)}
          <span className="ml-0.5 text-[10px]">(hidden)</span>
        </p>
      </div>

      {/* Revoke button */}
      {!apiKey.revoked && (
        <Button
          variant="ghost"
          size="sm"
          className="shrink-0 text-destructive hover:bg-destructive/10 hover:text-destructive"
          onClick={() => onRevoke(apiKey.id)}
          disabled={revoking}
          aria-label={`Revoke key "${apiKey.name}"`}
        >
          Revoke
        </Button>
      )}
    </div>
  );
}

// ── Docs snippet ──────────────────────────────────────────────────────────────

function DocsSnippet() {
  return (
    <Card className="shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold">Quick start</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-xs">
        <p className="text-muted-foreground">
          Pass your API key as a bearer token in the{" "}
          <code className="rounded bg-muted px-1 py-0.5">Authorization</code> header:
        </p>
        <pre className="overflow-x-auto rounded-lg border border-border/60 bg-muted/50 p-3 font-mono leading-relaxed">
          {`POST /api/v1/generate
Authorization: Bearer eta_<your-key>
Content-Type: multipart/form-data

# Returns { job_id } immediately.
# Poll GET /api/jobs/{job_id} for status.`}
        </pre>
        <p className="text-muted-foreground">
          Generation is async — poll{" "}
          <code className="rounded bg-muted px-1 py-0.5">GET /api/jobs/{"{job_id}"}</code> or
          pass a <code className="rounded bg-muted px-1 py-0.5">callback_url</code> for webhook
          notification.
        </p>
      </CardContent>
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function KeysPage() {
  const { isAuthenticated, loading: authLoading } = useAuth();
  const router = useRouter();

  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [newKey, setNewKey] = useState<ApiKeyCreated | null>(null);
  const [revoking, setRevoking] = useState<number | null>(null);

  const fetchKeys = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.keys.list();
      setKeys(res.keys);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load API keys");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.push("/");
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    if (isAuthenticated) fetchKeys();
  }, [isAuthenticated, fetchKeys]);

  const handleCreated = (key: ApiKeyCreated) => {
    setNewKey(key);
    setShowForm(false);
    fetchKeys();
  };

  const handleRevoke = async (id: number) => {
    if (!confirm("Are you sure you want to revoke this key? This cannot be undone.")) return;
    setRevoking(id);
    try {
      await api.keys.revoke(id);
      setKeys((prev) =>
        prev.map((k) => (k.id === id ? { ...k, revoked: true } : k))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revoke key");
    } finally {
      setRevoking(null);
    }
  };

  const activeKeys = keys.filter((k) => !k.revoked);
  const revokedKeys = keys.filter((k) => k.revoked);

  return (
    <div className="min-h-screen bg-background">
      <NavBar />

      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">API Keys</h1>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {activeKeys.length} active key{activeKeys.length !== 1 ? "s" : ""}
            </p>
          </div>
          {!showForm && !newKey && (
            <Button size="sm" onClick={() => setShowForm(true)}>
              New key
            </Button>
          )}
        </div>

        <div className="space-y-4">
          {/* New key reveal banner */}
          {newKey && (
            <NewKeyReveal created={newKey} onDismiss={() => setNewKey(null)} />
          )}

          {/* Create form */}
          {showForm && (
            <NewKeyForm
              onCreated={handleCreated}
              onCancel={() => setShowForm(false)}
            />
          )}

          {/* Error */}
          {error && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          {/* Keys list */}
          {loading && keys.length === 0 ? (
            <div className="space-y-3">
              {[1, 2].map((i) => (
                <div key={i} className="flex items-center gap-4 rounded-xl border border-border/60 bg-card p-4">
                  <Skeleton className="h-9 w-9 rounded-lg" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-3 w-48" />
                  </div>
                </div>
              ))}
            </div>
          ) : activeKeys.length === 0 && revokedKeys.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border/60 bg-muted/20 px-6 py-14 text-center">
              <span className="mb-3 text-4xl" role="img" aria-label="">🔑</span>
              <h3 className="font-semibold">No API keys yet</h3>
              <p className="mt-1 max-w-xs text-sm text-muted-foreground">
                Create a key to start using the programmatic API.
              </p>
              <Button size="sm" className="mt-4" onClick={() => setShowForm(true)}>
                Create first key
              </Button>
            </div>
          ) : (
            <>
              {activeKeys.length > 0 && (
                <div className="space-y-3">
                  {activeKeys.map((key) => (
                    <KeyRow
                      key={key.id}
                      apiKey={key}
                      onRevoke={handleRevoke}
                      revoking={revoking === key.id}
                    />
                  ))}
                </div>
              )}

              {revokedKeys.length > 0 && (
                <div className="mt-6 space-y-3">
                  <h2 className="text-sm font-medium text-muted-foreground">
                    Revoked keys
                  </h2>
                  {revokedKeys.map((key) => (
                    <KeyRow
                      key={key.id}
                      apiKey={key}
                      onRevoke={handleRevoke}
                      revoking={false}
                    />
                  ))}
                </div>
              )}
            </>
          )}

          {/* Docs */}
          <div className="pt-2">
            <DocsSnippet />
          </div>
        </div>
      </main>
    </div>
  );
}

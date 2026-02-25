"use client";

import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used: string | null;
}

interface CreatedKey extends ApiKey {
  key: string;
}

export default function ApiKeysPage() {
  const { loading, isAuthenticated } = useAuth();
  const router = useRouter();

  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loadingKeys, setLoadingKeys] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newKeyName, setNewKeyName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createdKey, setCreatedKey] = useState<CreatedKey | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [revokingId, setRevokingId] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push("/");
    }
  }, [loading, isAuthenticated, router]);

  async function fetchKeys() {
    setLoadingKeys(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/keys`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error(`Failed to fetch keys: ${res.statusText}`);
      const data = await res.json();
      setKeys(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load keys");
    } finally {
      setLoadingKeys(false);
    }
  }

  useEffect(() => {
    if (isAuthenticated) {
      fetchKeys();
    }
  }, [isAuthenticated]);

  async function handleCreate() {
    if (!newKeyName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/keys`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newKeyName.trim() }),
      });
      if (!res.ok) throw new Error(`Failed to create key: ${res.statusText}`);
      const data: CreatedKey = await res.json();
      setCreatedKey(data);
      setNewKeyName("");
      await fetchKeys();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create key");
    } finally {
      setCreating(false);
    }
  }

  async function handleRevoke(keyId: string) {
    setRevokingId(keyId);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/keys/${keyId}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok) throw new Error(`Failed to revoke key: ${res.statusText}`);
      setKeys((prev) => prev.filter((k) => k.id !== keyId));
      if (createdKey?.id === keyId) setCreatedKey(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revoke key");
    } finally {
      setRevokingId(null);
    }
  }

  async function handleCopy(text: string, id: string) {
    await navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">Loading...</div>
    );
  }

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold">API Keys</h1>
        <Button variant="outline" onClick={() => router.push("/dashboard")}>
          Dashboard
        </Button>
      </div>

      <p className="text-muted-foreground mb-6">
        Manage API keys for programmatic access to the listing generation API.
      </p>

      {/* Create new key */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Create New Key</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <input
              data-testid="key-name-input"
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="Key name (e.g. Production)"
              className="flex-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreate();
              }}
            />
            <Button
              data-testid="create-key-btn"
              onClick={handleCreate}
              disabled={creating || !newKeyName.trim()}
            >
              {creating ? "Creating..." : "Create Key"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Newly created key — shown once */}
      {createdKey && (
        <Card
          data-testid="new-key-banner"
          className="mb-6 border-green-200 bg-green-50"
        >
          <CardHeader className="pb-2">
            <CardTitle className="text-base text-green-800">
              Key created — copy it now
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-green-700 mb-3">
              This key will not be shown again. Store it securely.
            </p>
            <div className="flex items-center gap-2 rounded-md border border-green-200 bg-white p-3">
              <code
                data-testid="new-key-value"
                className="flex-1 text-sm font-mono break-all"
              >
                {createdKey.key}
              </code>
              <Button
                data-testid="copy-new-key-btn"
                variant="outline"
                size="sm"
                onClick={() => handleCopy(createdKey.key, createdKey.id)}
              >
                {copiedId === createdKey.id ? "Copied!" : "Copy"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {error && (
        <div
          data-testid="keys-error"
          className="rounded-lg border border-red-200 bg-red-50 p-4 mb-4"
        >
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Existing keys */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Your Keys</CardTitle>
        </CardHeader>
        <CardContent>
          {loadingKeys ? (
            <p
              data-testid="keys-loading"
              className="text-sm text-muted-foreground"
            >
              Loading...
            </p>
          ) : keys.length === 0 ? (
            <p
              data-testid="keys-empty"
              className="text-sm text-muted-foreground"
            >
              No API keys yet. Create one above.
            </p>
          ) : (
            <ul data-testid="keys-list" className="divide-y">
              {keys.map((key) => (
                <li
                  key={key.id}
                  data-testid={`key-item-${key.id}`}
                  className="flex items-center justify-between py-3"
                >
                  <div>
                    <p className="text-sm font-medium">{key.name}</p>
                    <p className="text-xs text-muted-foreground font-mono">
                      {key.prefix}••••
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Created {new Date(key.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      data-testid={`copy-key-btn-${key.id}`}
                      variant="outline"
                      size="sm"
                      onClick={() => handleCopy(key.prefix + "••••", key.id)}
                    >
                      {copiedId === key.id ? "Copied!" : "Copy"}
                    </Button>
                    <Button
                      data-testid={`revoke-key-btn-${key.id}`}
                      variant="destructive"
                      size="sm"
                      onClick={() => handleRevoke(key.id)}
                      disabled={revokingId === key.id}
                    >
                      {revokingId === key.id ? "Revoking..." : "Revoke"}
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

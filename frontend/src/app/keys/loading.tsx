// Loading skeleton for the /keys route segment.

export default function KeysLoading() {
  return (
    <div className="min-h-screen bg-background">
      {/* Nav skeleton */}
      <div className="border-b border-border/40 bg-background px-4 py-3">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="h-6 w-36 animate-pulse rounded-md bg-muted" />
          <div className="h-8 w-24 animate-pulse rounded-md bg-muted" />
        </div>
      </div>

      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        <div className="mb-6 space-y-2">
          <div className="h-7 w-40 animate-pulse rounded-md bg-muted" />
          <div className="h-4 w-56 animate-pulse rounded-md bg-muted" />
        </div>

        {/* New key form skeleton */}
        <div className="mb-6 rounded-xl border border-border/60 bg-card p-5">
          <div className="h-5 w-32 animate-pulse rounded bg-muted mb-4" />
          <div className="flex gap-3">
            <div className="h-9 flex-1 animate-pulse rounded-lg bg-muted" />
            <div className="h-9 w-28 animate-pulse rounded-lg bg-muted" />
          </div>
        </div>

        {/* API key rows skeleton */}
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="flex items-center gap-4 rounded-xl border border-border/60 bg-card p-4"
            >
              <div className="flex-1 space-y-1.5">
                <div className="h-4 w-32 animate-pulse rounded bg-muted" />
                <div className="h-3 w-48 animate-pulse rounded bg-muted" />
              </div>
              <div className="h-8 w-16 animate-pulse rounded bg-muted" />
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

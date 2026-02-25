// Loading skeleton for the /jobs/[id] route segment.

export default function JobLoading() {
  return (
    <div className="min-h-screen bg-background">
      {/* Nav skeleton */}
      <div className="border-b border-border/40 bg-background px-4 py-3">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="h-6 w-36 animate-pulse rounded-md bg-muted" />
          <div className="h-8 w-24 animate-pulse rounded-md bg-muted" />
        </div>
      </div>

      <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
        {/* Status bar skeleton */}
        <div className="mb-6 flex items-center gap-4 rounded-xl border border-border/60 bg-card p-4">
          <div className="h-8 w-8 animate-pulse rounded-full bg-muted" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-40 animate-pulse rounded bg-muted" />
            <div className="h-3 w-24 animate-pulse rounded bg-muted" />
          </div>
        </div>

        {/* Image grid skeleton */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 10 }).map((_, i) => (
            <div
              key={i}
              className="aspect-square animate-pulse rounded-xl bg-muted"
            />
          ))}
        </div>

        {/* Listing skeleton */}
        <div className="mt-8 space-y-3 rounded-xl border border-border/60 bg-card p-5">
          <div className="h-5 w-32 animate-pulse rounded bg-muted" />
          <div className="h-4 w-full animate-pulse rounded bg-muted" />
          <div className="h-4 w-4/5 animate-pulse rounded bg-muted" />
          <div className="h-4 w-3/5 animate-pulse rounded bg-muted" />
        </div>
      </main>
    </div>
  );
}

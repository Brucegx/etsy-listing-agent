// Loading skeleton for the /dashboard route.
// Shown while the dashboard page segment is loading (data fetching, auth check).

export default function DashboardLoading() {
  return (
    <div className="min-h-screen bg-background">
      {/* Nav skeleton */}
      <div className="border-b border-border/40 bg-background px-4 py-3">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="h-6 w-36 animate-pulse rounded-md bg-muted" />
          <div className="h-8 w-24 animate-pulse rounded-md bg-muted" />
        </div>
      </div>

      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        {/* Page title skeleton */}
        <div className="mb-6 space-y-2">
          <div className="h-7 w-40 animate-pulse rounded-md bg-muted" />
          <div className="h-4 w-64 animate-pulse rounded-md bg-muted" />
        </div>

        {/* Job cards skeleton */}
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="flex items-center gap-4 rounded-xl border border-border/60 bg-card p-4 shadow-sm"
            >
              {/* Thumbnail placeholder */}
              <div className="h-16 w-16 shrink-0 animate-pulse rounded-lg bg-muted" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-1/3 animate-pulse rounded bg-muted" />
                <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
              </div>
              <div className="h-6 w-20 animate-pulse rounded-full bg-muted" />
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

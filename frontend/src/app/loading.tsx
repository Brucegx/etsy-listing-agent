// Root-level loading skeleton shown while the home page segment loads.

export default function RootLoading() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Nav skeleton */}
      <div className="border-b border-border/40 bg-background px-4 py-3">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="h-6 w-36 animate-pulse rounded-md bg-muted" />
          <div className="h-8 w-24 animate-pulse rounded-md bg-muted" />
        </div>
      </div>

      {/* Hero skeleton */}
      <div className="mx-auto mt-16 w-full max-w-2xl space-y-4 px-4">
        <div className="h-4 w-32 animate-pulse rounded-full bg-muted mx-auto" />
        <div className="h-10 w-full animate-pulse rounded-lg bg-muted" />
        <div className="h-10 w-4/5 animate-pulse rounded-lg bg-muted mx-auto" />
        <div className="h-5 w-2/3 animate-pulse rounded-md bg-muted mx-auto" />
        <div className="flex justify-center gap-3 pt-2">
          <div className="h-10 w-32 animate-pulse rounded-lg bg-muted" />
          <div className="h-10 w-32 animate-pulse rounded-lg bg-muted" />
        </div>
      </div>
    </div>
  );
}

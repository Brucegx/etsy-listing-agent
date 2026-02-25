"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

interface DashboardErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function DashboardError({ error, reset }: DashboardErrorProps) {
  useEffect(() => {
    console.error("[DashboardError]", error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-5 px-4 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10 text-2xl">
        ⚠
      </div>
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Could not load your jobs</h2>
        <p className="max-w-sm text-sm text-muted-foreground">
          There was a problem fetching your job history. This might be a
          temporary issue — try refreshing.
        </p>
      </div>
      <div className="flex gap-3">
        <Button onClick={reset}>Refresh</Button>
        <Button variant="outline" asChild>
          <Link href="/">Home</Link>
        </Button>
      </div>
    </div>
  );
}

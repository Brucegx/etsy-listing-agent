"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

interface JobErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function JobError({ error, reset }: JobErrorProps) {
  useEffect(() => {
    console.error("[JobError]", error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-5 px-4 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10 text-2xl">
        ⚠
      </div>
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Could not load this job</h2>
        <p className="max-w-sm text-sm text-muted-foreground">
          The job may have been deleted, or there was a network issue. Try
          going back to your dashboard.
        </p>
      </div>
      <div className="flex gap-3">
        <Button onClick={reset}>Try again</Button>
        <Button variant="outline" asChild>
          <Link href="/dashboard">Dashboard</Link>
        </Button>
      </div>
    </div>
  );
}

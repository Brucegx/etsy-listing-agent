"use client";

// Global error boundary for the root layout.
// Next.js renders this when an unhandled error occurs in any route segment
// that does not have its own error.tsx.

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

interface GlobalErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ error, reset }: GlobalErrorProps) {
  useEffect(() => {
    // Log the error to the console (replace with a real error tracker later)
    console.error("[GlobalError]", error);
  }, [error]);

  return (
    <html lang="en">
      <body className="antialiased">
        <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-4 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-destructive/10 text-3xl">
            ⚠
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight">
              Something went wrong
            </h1>
            <p className="max-w-sm text-sm text-muted-foreground">
              An unexpected error occurred. Our team has been notified. You can
              try again or return to the home page.
            </p>
          </div>
          <div className="flex gap-3">
            <Button onClick={reset}>Try again</Button>
            <Button variant="outline" asChild>
              <a href="/">Go home</a>
            </Button>
          </div>
          {process.env.NODE_ENV !== "production" && (
            <details className="mt-4 max-w-lg rounded-lg border border-border/60 bg-muted/40 p-4 text-left">
              <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
                Error details (dev only)
              </summary>
              <pre className="mt-2 overflow-auto whitespace-pre-wrap text-xs text-destructive">
                {error.message}
                {error.stack && `\n\n${error.stack}`}
              </pre>
            </details>
          )}
        </div>
      </body>
    </html>
  );
}

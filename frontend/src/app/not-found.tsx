// Global 404 page shown when no route matches.
// This is a Server Component (no "use client" needed).

import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-4 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted text-4xl font-bold text-muted-foreground">
        404
      </div>
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">
          Page not found
        </h1>
        <p className="max-w-sm text-sm text-muted-foreground">
          The page you are looking for does not exist or has been moved.
        </p>
      </div>
      <div className="flex gap-3">
        <Button asChild>
          <Link href="/">Go home</Link>
        </Button>
        <Button variant="outline" asChild>
          <Link href="/dashboard">My jobs</Link>
        </Button>
      </div>
    </div>
  );
}

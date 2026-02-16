"use client";

import { Badge } from "@/components/ui/badge";
import type { SSEEvent } from "@/types";

interface GenerationProgressProps {
  events: SSEEvent[];
  isRunning: boolean;
}

export function GenerationProgress({
  events,
  isRunning,
}: GenerationProgressProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <h3 className="font-semibold">Generation Progress</h3>
        {isRunning && <Badge variant="secondary">Running...</Badge>}
      </div>
      <div className="space-y-1 max-h-64 overflow-y-auto">
        {events.map((e, i) => (
          <div key={i} className="flex items-center gap-2 text-sm">
            <Badge
              variant={e.event === "error" ? "destructive" : "outline"}
              className="text-xs"
            >
              {e.event}
            </Badge>
            <span className="text-muted-foreground">
              {"message" in e.data
                ? e.data.message
                : JSON.stringify(e.data)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

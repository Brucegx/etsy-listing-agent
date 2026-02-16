"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";
import type { SSEEvent } from "@/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type PhaseStatus = "pending" | "processing" | "completed" | "error";

interface PhaseState {
  id: string;
  label: string;
  status: PhaseStatus;
  counter?: string; // e.g. "3/10"
}

export interface WorkflowPipelineProps {
  events: SSEEvent[];
  isRunning: boolean;
  promptProgress?: { total: number; completed: number };
  imageProgress?: { total: number; completed: number };
}

// ---------------------------------------------------------------------------
// Phase definitions and SSE-to-phase mapping
// ---------------------------------------------------------------------------

/** Ordered pipeline phases */
const PHASE_IDS = ["analyze", "strategy", "generate", "images", "complete"] as const;
type PhaseId = (typeof PHASE_IDS)[number];

const PHASE_LABELS: Record<PhaseId, string> = {
  analyze: "Analyze",
  strategy: "Strategy",
  generate: "Generate",
  images: "Images",
  complete: "Complete",
};

/** Map an SSE node name (from data.node or data.stage) to a pipeline phase */
function nodeToPhase(node: string): PhaseId | null {
  switch (node) {
    case "preprocess":
    case "preprocess_review":
    case "preprocessing":
    case "preprocessing_review":
      return "analyze";

    case "strategy":
    case "strategy_review":
      return "strategy";

    case "nanobanana_fan_out":
    case "nanobanana":
    case "prompt_node":
    case "prompt_aggregator":
    case "nanobanana_aggregated":
    case "nanobanana_review":
    case "listing_fan_out":
    case "listing":
    case "listing_review":
      return "generate";

    case "image_gen":
    case "image_gen_complete":
    case "image_gen_failed":
      return "images";

    case "completed":
      return "complete";

    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Derive pipeline state from SSE events
// ---------------------------------------------------------------------------

function derivePipelineState(
  events: SSEEvent[],
  isRunning: boolean,
  promptProgress?: { total: number; completed: number },
  imageProgress?: { total: number; completed: number },
): PhaseState[] {
  // Find the highest (rightmost) phase that has been touched
  let highestPhaseIndex = -1;
  let hasError = false;
  let isComplete = false;

  for (const event of events) {
    if (event.event === "start") {
      // Workflow started — first phase begins processing
      highestPhaseIndex = Math.max(highestPhaseIndex, 0);
      continue;
    }

    if (event.event === "complete") {
      isComplete = true;
      continue;
    }

    if (event.event === "error") {
      hasError = true;
      continue;
    }

    if (event.event === "progress") {
      // Prefer node over stage for mapping since node is the actual LangGraph node
      const key = event.data.node || event.data.stage;
      const phase = nodeToPhase(key);
      if (phase) {
        const idx = PHASE_IDS.indexOf(phase);
        if (idx > highestPhaseIndex) {
          highestPhaseIndex = idx;
        }
      }
    }

    // strategy_complete means strategy phase completed, generate is next
    if (event.event === "strategy_complete") {
      const idx = PHASE_IDS.indexOf("strategy");
      if (idx > highestPhaseIndex) {
        highestPhaseIndex = idx;
      }
    }

    // image_complete / image_done means images phase is active
    if (event.event === "image_complete" || event.event === "image_done") {
      const idx = PHASE_IDS.indexOf("images");
      if (idx > highestPhaseIndex) {
        highestPhaseIndex = idx;
      }
    }
  }

  // Build phase states
  return PHASE_IDS.map((id, idx) => {
    let status: PhaseStatus = "pending";

    if (isComplete) {
      // Everything is completed
      status = "completed";
    } else if (hasError && !isRunning) {
      // Error occurred and we've stopped
      if (idx < highestPhaseIndex) {
        status = "completed";
      } else if (idx === highestPhaseIndex) {
        status = "error";
      }
      // else: pending
    } else if (idx < highestPhaseIndex) {
      status = "completed";
    } else if (idx === highestPhaseIndex) {
      // The current phase: processing if still running, completed if we moved past it
      status = isRunning ? "processing" : "completed";
    }
    // else: pending

    // Counter text
    let counter: string | undefined;
    if (id === "generate" && promptProgress && promptProgress.total > 0) {
      counter = `${promptProgress.completed}/${promptProgress.total}`;
    }
    if (id === "images" && imageProgress && imageProgress.total > 0) {
      counter = `${imageProgress.completed}/${imageProgress.total}`;
    }

    return { id, label: PHASE_LABELS[id], status, counter };
  });
}

// ---------------------------------------------------------------------------
// SVG Icons (inline, no external deps)
// ---------------------------------------------------------------------------

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={3}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={3}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

/** Phase-specific icons shown in the default/processing state */
function PhaseIcon({ phaseId, className }: { phaseId: string; className?: string }) {
  switch (phaseId) {
    case "analyze":
      // Magnifying glass
      return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      );
    case "strategy":
      // Lightbulb
      return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M9 18h6" />
          <path d="M10 22h4" />
          <path d="M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z" />
        </svg>
      );
    case "generate":
      // Pencil / edit
      return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 20h9" />
          <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
        </svg>
      );
    case "images":
      // Image / photo
      return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <polyline points="21 15 16 10 5 21" />
        </svg>
      );
    case "complete":
      // Flag
      return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" />
          <line x1="4" y1="22" x2="4" y2="15" />
        </svg>
      );
    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Phase Node Component
// ---------------------------------------------------------------------------

function PipelineNode({ phase }: { phase: PhaseState }) {
  const { status, label, counter, id } = phase;

  // Outer circle styles by status
  const circleClasses = cn(
    "relative flex items-center justify-center rounded-full w-11 h-11 sm:w-12 sm:h-12 transition-all duration-300",
    {
      // Pending: muted
      "bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500":
        status === "pending",
      // Processing: active with ring animation
      "bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 ring-2 ring-emerald-400/60 dark:ring-emerald-500/50":
        status === "processing",
      // Completed: solid teal/emerald
      "bg-emerald-500 dark:bg-emerald-600 text-white":
        status === "completed",
      // Error: red
      "bg-red-500 dark:bg-red-600 text-white":
        status === "error",
    },
  );

  // Label styles
  const labelClasses = cn(
    "text-xs sm:text-sm font-medium mt-2 text-center transition-colors duration-300",
    {
      "text-gray-400 dark:text-gray-500": status === "pending",
      "text-emerald-700 dark:text-emerald-400": status === "processing",
      "text-gray-700 dark:text-gray-300": status === "completed",
      "text-red-600 dark:text-red-400": status === "error",
    },
  );

  return (
    <div className="flex flex-col items-center gap-0" role="listitem">
      <div className={circleClasses}>
        {/* Pulse ring animation for processing */}
        {status === "processing" && (
          <span
            className="absolute inset-0 rounded-full animate-ping bg-emerald-400/30 dark:bg-emerald-500/20"
            style={{ animationDuration: "1.5s" }}
            aria-hidden="true"
          />
        )}

        {/* Icon */}
        {status === "completed" ? (
          <CheckIcon className="w-5 h-5 sm:w-6 sm:h-6" />
        ) : status === "error" ? (
          <XIcon className="w-5 h-5 sm:w-6 sm:h-6" />
        ) : (
          <PhaseIcon phaseId={id} className="w-5 h-5 sm:w-6 sm:h-6" />
        )}
      </div>

      {/* Label */}
      <span className={labelClasses}>{label}</span>

      {/* Counter badge */}
      {counter && (status === "processing" || status === "completed") && (
        <span
          className={cn(
            "mt-0.5 text-[10px] sm:text-xs font-mono tabular-nums px-1.5 py-0.5 rounded-full",
            status === "processing"
              ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300"
              : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
          )}
        >
          {counter}
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Connector Line Component
// ---------------------------------------------------------------------------

function ConnectorLine({
  leftStatus,
  rightStatus,
  isVertical,
}: {
  leftStatus: PhaseStatus;
  rightStatus: PhaseStatus;
  isVertical: boolean;
}) {
  // The line is "filled" when the left node is completed
  const isFilled = leftStatus === "completed";
  // The line is "active" when it connects to a processing node
  const isActive = leftStatus === "completed" && rightStatus === "processing";

  const lineClasses = cn(
    "transition-all duration-500",
    isVertical ? "w-0.5 h-6" : "h-0.5 flex-1 min-w-6 max-w-20",
    isFilled
      ? "bg-emerald-400 dark:bg-emerald-500"
      : "bg-gray-200 dark:bg-gray-700",
  );

  return (
    <div
      className={cn(
        "flex items-center justify-center",
        isVertical ? "py-0" : "px-0",
      )}
      aria-hidden="true"
    >
      <div className={lineClasses}>
        {/* Shimmer animation on active connector */}
        {isActive && (
          <div
            className={cn(
              "rounded-full bg-emerald-300/60 dark:bg-emerald-400/40 animate-pulse",
              isVertical ? "w-full h-full" : "w-full h-full",
            )}
          />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function WorkflowPipeline({
  events,
  isRunning,
  promptProgress,
  imageProgress,
}: WorkflowPipelineProps) {
  const phases = useMemo(
    () => derivePipelineState(events, isRunning, promptProgress, imageProgress),
    [events, isRunning, promptProgress, imageProgress],
  );

  return (
    <div role="list" aria-label="Workflow progress">
      {/* Desktop / Tablet: Horizontal */}
      <div className="hidden sm:flex items-start justify-center gap-0">
        {phases.map((phase, idx) => (
          <div key={phase.id} className="flex items-start">
            <PipelineNode phase={phase} />
            {idx < phases.length - 1 && (
              <div className="flex items-center pt-5 sm:pt-[22px]">
                <ConnectorLine
                  leftStatus={phase.status}
                  rightStatus={phases[idx + 1].status}
                  isVertical={false}
                />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Mobile: Vertical */}
      <div className="flex sm:hidden flex-col items-center gap-0">
        {phases.map((phase, idx) => (
          <div key={phase.id} className="flex flex-col items-center">
            <PipelineNode phase={phase} />
            {idx < phases.length - 1 && (
              <ConnectorLine
                leftStatus={phase.status}
                rightStatus={phases[idx + 1].status}
                isVertical={true}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

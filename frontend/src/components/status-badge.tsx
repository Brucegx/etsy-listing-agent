import { cn } from "@/lib/utils";
import type { JobStatus } from "@/types";

interface StatusBadgeProps {
  status: JobStatus | string;
  className?: string;
}

const STATUS_CONFIG: Record<
  string,
  { label: string; classes: string; pulse?: boolean }
> = {
  queued: {
    label: "Queued",
    classes:
      "bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800/60 dark:text-slate-400 dark:border-slate-700",
  },
  strategy: {
    label: "Analyzing",
    classes:
      "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/40 dark:text-amber-400 dark:border-amber-800",
    pulse: true,
  },
  batch_submitted: {
    label: "Submitted",
    classes:
      "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/40 dark:text-amber-400 dark:border-amber-800",
    pulse: true,
  },
  generating: {
    label: "Generating",
    classes:
      "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/40 dark:text-amber-400 dark:border-amber-800",
    pulse: true,
  },
  completed: {
    label: "Completed",
    classes:
      "bg-emerald-100 text-emerald-700 border-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-400 dark:border-emerald-800",
  },
  failed: {
    label: "Failed",
    classes:
      "bg-rose-100 text-rose-700 border-rose-200 dark:bg-rose-900/40 dark:text-rose-400 dark:border-rose-800",
  },
};

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? {
    label: status,
    classes:
      "bg-muted text-muted-foreground border-border",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        config.classes,
        className
      )}
    >
      {config.pulse && (
        <span
          className="h-1.5 w-1.5 rounded-full bg-current animate-status-pulse"
          aria-hidden="true"
        />
      )}
      {config.label}
    </span>
  );
}

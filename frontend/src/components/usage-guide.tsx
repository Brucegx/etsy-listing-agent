"use client";

import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";

interface UsageGuideProps {
  onClose: () => void;
}

const steps = [
  {
    icon: "📁",
    title: "Create a folder per product",
    desc: 'In Google Drive, make one folder for each product you want to list. For example: "Silver Ring A", "Copper Cuff B". Keep folder names short and descriptive.',
  },
  {
    icon: "📊",
    title: "Add an Excel or Google Sheets file",
    desc: "Inside the folder, add a spreadsheet with product details — material, size, category, and any other relevant info. The agent reads this to write accurate listings.",
    example: "Columns: product_id | material | size | category | notes",
  },
  {
    icon: "🖼️",
    title: "Add 5–10 product photos",
    desc: "Include clear product photos. Mix angles: front, back, detail shots, and scale shots. Higher quality = better AI results. JPG/PNG, under 10 MB each.",
  },
  {
    icon: "✅",
    title: "Select the folder in the Drive browser",
    desc: 'Click "Select" next to your product folder. The agent will detect the spreadsheet, list your products, and let you generate a full listing for each one.',
  },
];

export function UsageGuide({ onClose }: UsageGuideProps) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  // Trap focus inside dialog
  useEffect(() => {
    dialogRef.current?.focus();
  }, []);

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
      aria-modal="true"
      role="dialog"
      aria-labelledby="usage-guide-title"
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose();
      }}
    >
      <div
        ref={dialogRef}
        tabIndex={-1}
        className="relative w-full max-w-lg rounded-xl bg-white dark:bg-gray-900 shadow-xl outline-none max-h-[90vh] overflow-y-auto"
      >
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-6 py-4 border-b bg-white dark:bg-gray-900">
          <div>
            <h2
              id="usage-guide-title"
              className="text-lg font-semibold text-gray-900 dark:text-gray-100"
            >
              How to organize your product photos
            </h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              Set up your Google Drive for best results
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close guide"
            className="rounded-md p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 18 18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Steps */}
        <div className="px-6 py-5 space-y-5">
          {steps.map((step, i) => (
            <div key={i} className="flex gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gray-100 dark:bg-gray-800 text-xl">
                {step.icon}
              </div>
              <div className="flex-1 min-w-0 space-y-1">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                  {step.title}
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  {step.desc}
                </p>
                {step.example && (
                  <div className="mt-2 rounded-md bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 px-3 py-2">
                    <code className="text-xs text-gray-600 dark:text-gray-400 font-mono">
                      {step.example}
                    </code>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Example folder structure */}
        <div className="px-6 pb-5 space-y-2">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Example folder structure
          </h3>
          <div className="rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 px-4 py-3 font-mono text-xs text-gray-600 dark:text-gray-400 space-y-1">
            <div>📁 My Drive</div>
            <div className="pl-4">📁 Jewelry Products</div>
            <div className="pl-8">📁 Silver Ring A</div>
            <div className="pl-12">📄 products.xlsx</div>
            <div className="pl-12">🖼️ front.jpg</div>
            <div className="pl-12">🖼️ side.jpg</div>
            <div className="pl-12">🖼️ detail.jpg</div>
            <div className="pl-8">📁 Copper Cuff B</div>
            <div className="pl-12">📄 products.xlsx</div>
            <div className="pl-12">🖼️ photo_1.jpg</div>
            <div className="pl-12">🖼️ photo_2.jpg</div>
          </div>
          <p className="text-xs text-muted-foreground">
            Each folder should contain 5–10 product photos for best AI results.
          </p>
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 px-6 py-4 border-t bg-white dark:bg-gray-900">
          <Button onClick={onClose} className="w-full">
            Got it, let&apos;s go
          </Button>
        </div>
      </div>
    </div>
  );
}

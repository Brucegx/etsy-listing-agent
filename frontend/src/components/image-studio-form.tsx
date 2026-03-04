"use client";

import { useCallback, useState } from "react";
import { ImageUploader } from "@/components/image-uploader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { ImageCategory, AspectRatio, ImageConfig } from "@/types";

// ─── Image type card data ───────────────────────────────────────────────────

interface ImageTypeOption {
  value: ImageCategory;
  label: string;
  labelCn: string;
  description: string;
  icon: React.ReactNode;
  accentClass: string;
  bgClass: string;
  borderClass: string;
  selectedBorderClass: string;
  selectedBgClass: string;
  iconBgClass: string;
}

const WhiteBgIcon = () => (
  <svg className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
    <rect x="3" y="3" width="18" height="18" rx="2" strokeLinejoin="round" />
    <circle cx="12" cy="12" r="3.5" />
    <path strokeLinecap="round" d="M12 3v2M12 19v2M3 12h2M19 12h2" />
  </svg>
);

const SceneIcon = () => (
  <svg className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M13.5 12a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
    <rect x="3" y="3" width="18" height="18" rx="2" />
  </svg>
);

const ModelIcon = () => (
  <svg className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
  </svg>
);

const DetailIcon = () => (
  <svg className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 15.803a7.5 7.5 0 0010.607 0z" />
    <circle cx="10.5" cy="10.5" r="2" />
  </svg>
);

const IMAGE_TYPE_OPTIONS: ImageTypeOption[] = [
  {
    value: "white_bg",
    label: "White BG",
    labelCn: "白底图",
    description: "Clean white background, product center stage",
    icon: <WhiteBgIcon />,
    accentClass: "text-slate-600 dark:text-slate-300",
    bgClass: "bg-slate-50 dark:bg-slate-900/40",
    borderClass: "border-slate-200 dark:border-slate-700",
    selectedBorderClass: "border-slate-500 dark:border-slate-400",
    selectedBgClass: "bg-slate-50 dark:bg-slate-900/60",
    iconBgClass: "bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-300",
  },
  {
    value: "scene",
    label: "Scene",
    labelCn: "场景图",
    description: "Lifestyle context with props and setting",
    icon: <SceneIcon />,
    accentClass: "text-emerald-700 dark:text-emerald-300",
    bgClass: "bg-emerald-50 dark:bg-emerald-900/30",
    borderClass: "border-emerald-200 dark:border-emerald-800",
    selectedBorderClass: "border-emerald-500 dark:border-emerald-400",
    selectedBgClass: "bg-emerald-50 dark:bg-emerald-900/50",
    iconBgClass: "bg-emerald-100 dark:bg-emerald-900/60 text-emerald-600 dark:text-emerald-300",
  },
  {
    value: "model",
    label: "Model",
    labelCn: "模特图",
    description: "Worn on a person for scale and appeal",
    icon: <ModelIcon />,
    accentClass: "text-violet-700 dark:text-violet-300",
    bgClass: "bg-violet-50 dark:bg-violet-900/30",
    borderClass: "border-violet-200 dark:border-violet-800",
    selectedBorderClass: "border-violet-500 dark:border-violet-400",
    selectedBgClass: "bg-violet-50 dark:bg-violet-900/50",
    iconBgClass: "bg-violet-100 dark:bg-violet-900/60 text-violet-600 dark:text-violet-300",
  },
  {
    value: "detail",
    label: "Detail",
    labelCn: "细节图",
    description: "Close-up macro shots of texture and craft",
    icon: <DetailIcon />,
    accentClass: "text-amber-700 dark:text-amber-300",
    bgClass: "bg-amber-50 dark:bg-amber-900/30",
    borderClass: "border-amber-200 dark:border-amber-800",
    selectedBorderClass: "border-amber-500 dark:border-amber-400",
    selectedBgClass: "bg-amber-50 dark:bg-amber-900/50",
    iconBgClass: "bg-amber-100 dark:bg-amber-900/60 text-amber-600 dark:text-amber-300",
  },
];

const COUNT_OPTIONS = [1, 3, 4, 5, 9];
const RATIO_OPTIONS: { value: AspectRatio; label: string; desc: string }[] = [
  { value: "1:1", label: "1:1", desc: "Square" },
  { value: "3:4", label: "3:4", desc: "Portrait" },
  { value: "4:3", label: "4:3", desc: "Landscape" },
];

// ─── Sub-components ─────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 mb-2.5">
      {children}
    </p>
  );
}

function SegmentedControl<T extends string | number>({
  options,
  value,
  onChange,
  disabled,
  renderOption,
}: {
  options: T[];
  value: T;
  onChange: (v: T) => void;
  disabled?: boolean;
  renderOption?: (v: T) => React.ReactNode;
}) {
  return (
    <div className="inline-flex rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800/60 p-0.5 gap-0.5">
      {options.map((opt) => {
        const isSelected = opt === value;
        return (
          <button
            key={String(opt)}
            type="button"
            onClick={() => !disabled && onChange(opt)}
            disabled={disabled}
            className={`
              relative px-4 py-1.5 rounded-md text-sm font-medium transition-all
              focus:outline-none focus:ring-2 focus:ring-amber-400 focus:ring-offset-1
              ${
                isSelected
                  ? "bg-white dark:bg-gray-900 shadow-sm text-gray-900 dark:text-gray-100"
                  : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
              }
              ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"}
            `}
          >
            {renderOption ? renderOption(opt) : String(opt)}
          </button>
        );
      })}
    </div>
  );
}

// ─── Props ──────────────────────────────────────────────────────────────────

interface ImageStudioFormProps {
  onSubmit: (files: File[], productInfo: string, config: ImageConfig) => void;
  isSubmitting: boolean;
  isLocked: boolean;
}

// ─── Main Component ──────────────────────────────────────────────────────────

export function ImageStudioForm({
  onSubmit,
  isSubmitting,
  isLocked,
}: ImageStudioFormProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<ImageCategory | null>(null);
  const [additionalPrompt, setAdditionalPrompt] = useState("");
  const [productInfo, setProductInfo] = useState("");
  const [count, setCount] = useState<number>(4);
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>("1:1");

  const canSubmit =
    files.length > 0 && !isSubmitting && !isLocked;

  const handleSubmit = useCallback(() => {
    if (!canSubmit) return;
    const config: ImageConfig = {
      category: selectedCategory,
      additional_prompt: additionalPrompt.trim(),
      count,
      aspect_ratio: aspectRatio,
    };
    onSubmit(files, productInfo.trim(), config);
  }, [canSubmit, files, selectedCategory, additionalPrompt, productInfo, count, aspectRatio, onSubmit]);

  const textareaClass =
    "w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm placeholder:text-muted-foreground focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-400/30 disabled:cursor-not-allowed disabled:opacity-50 resize-none";

  return (
    <div className="space-y-6">
      {/* Step 1 — Upload */}
      <Card className="border-gray-200 dark:border-gray-700 shadow-none">
        <CardContent className="pt-5">
          <SectionLabel>1. Upload your product photo</SectionLabel>
          <ImageUploader
            files={files}
            onChange={setFiles}
            disabled={isSubmitting || isLocked}
          />
        </CardContent>
      </Card>

      {/* Step 2 — Image type */}
      <Card className="border-gray-200 dark:border-gray-700 shadow-none">
        <CardContent className="pt-5">
          <SectionLabel>2. Choose image type (optional)</SectionLabel>
          <div className="grid grid-cols-2 gap-3">
            {IMAGE_TYPE_OPTIONS.map((opt) => {
              const isSelected = selectedCategory === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  disabled={isSubmitting || isLocked}
                  onClick={() =>
                    setSelectedCategory(isSelected ? null : opt.value)
                  }
                  className={`
                    relative text-left rounded-xl border-2 p-4 transition-all
                    focus:outline-none focus:ring-2 focus:ring-amber-400
                    disabled:cursor-not-allowed disabled:opacity-50
                    ${
                      isSelected
                        ? `${opt.selectedBorderClass} ${opt.selectedBgClass} shadow-sm`
                        : `${opt.borderClass} bg-white dark:bg-gray-900 hover:shadow-sm hover:${opt.selectedBorderClass}`
                    }
                  `}
                >
                  {isSelected && (
                    <span className="absolute top-2.5 right-2.5 flex h-4 w-4 items-center justify-center rounded-full bg-amber-500">
                      <svg className="h-2.5 w-2.5 text-white" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                      </svg>
                    </span>
                  )}
                  <div className={`mb-2.5 flex h-10 w-10 items-center justify-center rounded-lg ${opt.iconBgClass}`}>
                    {opt.icon}
                  </div>
                  <div>
                    <p className={`text-sm font-semibold leading-tight ${isSelected ? opt.accentClass : "text-gray-900 dark:text-gray-100"}`}>
                      {opt.label}
                      <span className="ml-1.5 text-xs font-normal opacity-60">{opt.labelCn}</span>
                    </p>
                    <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400 leading-snug">
                      {opt.description}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
          <p className="mt-2 text-xs text-gray-400 dark:text-gray-500">
            Leave unselected to let AI choose the best type automatically.
          </p>
        </CardContent>
      </Card>

      {/* Step 3 — Count + Ratio */}
      <Card className="border-gray-200 dark:border-gray-700 shadow-none">
        <CardContent className="pt-5 space-y-5">
          <SectionLabel>3. Output settings</SectionLabel>

          <div className="space-y-2.5">
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Number of images
            </p>
            <SegmentedControl
              options={COUNT_OPTIONS}
              value={count}
              onChange={setCount}
              disabled={isSubmitting || isLocked}
              renderOption={(v) => String(v)}
            />
          </div>

          <div className="space-y-2.5">
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Aspect ratio
            </p>
            <SegmentedControl
              options={RATIO_OPTIONS.map((r) => r.value)}
              value={aspectRatio}
              onChange={setAspectRatio}
              disabled={isSubmitting || isLocked}
              renderOption={(v) => {
                const opt = RATIO_OPTIONS.find((r) => r.value === v)!;
                return (
                  <span className="flex flex-col items-center leading-tight">
                    <span>{opt.label}</span>
                    <span className="text-[10px] opacity-60">{opt.desc}</span>
                  </span>
                );
              }}
            />
          </div>
        </CardContent>
      </Card>

      {/* Step 4 — Optional text fields */}
      <Card className="border-gray-200 dark:border-gray-700 shadow-none">
        <CardContent className="pt-5 space-y-4">
          <SectionLabel>4. Additional details (optional)</SectionLabel>

          <div className="space-y-1.5">
            <label htmlFor="product-info" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Product description
            </label>
            <textarea
              id="product-info"
              value={productInfo}
              onChange={(e) => setProductInfo(e.target.value)}
              disabled={isSubmitting || isLocked}
              rows={2}
              placeholder="e.g. 925银戒指，2cm宽，蓝色锆石"
              className={textareaClass}
            />
            <p className="text-xs text-gray-400 dark:text-gray-500">
              Help the AI understand your product — material, size, color, style.
            </p>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="style-prompt" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Style prompt
            </label>
            <textarea
              id="style-prompt"
              value={additionalPrompt}
              onChange={(e) => setAdditionalPrompt(e.target.value)}
              disabled={isSubmitting || isLocked}
              rows={2}
              placeholder="e.g. 背景要有绿植，暖色调光线，柔和散景"
              className={textareaClass}
            />
            <p className="text-xs text-gray-400 dark:text-gray-500">
              Describe the mood, lighting, background, or props you want.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Submit */}
      <div className="flex items-center gap-4">
        <Button
          onClick={handleSubmit}
          disabled={!canSubmit}
          size="lg"
          aria-busy={isSubmitting}
          className="bg-amber-500 hover:bg-amber-600 text-white font-semibold shadow-sm"
        >
          {isSubmitting && (
            <svg
              className="mr-2 h-4 w-4 animate-spin"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          )}
          {isSubmitting
            ? "Submitting…"
            : isLocked
            ? "Job Submitted"
            : "Generate Images"}
        </Button>
        {!canSubmit && !isSubmitting && !isLocked && (
          <p className="text-xs text-muted-foreground">
            Upload at least one product photo to continue.
          </p>
        )}
      </div>
    </div>
  );
}

"use client";

import { useCallback, useState } from "react";
import { ImageUploader } from "@/components/image-uploader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { ImageCategory, AspectRatio, ImageConfig, ImageModel, ImageResolution } from "@/types";

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
    accentClass: "text-[#1A1A1A]",
    bgClass: "bg-[#F5F5F0]",
    borderClass: "border-[#E8E8E3]",
    selectedBorderClass: "border-[#D4A853]",
    selectedBgClass: "bg-[#D4A853]/5",
    iconBgClass: "bg-[#F5F5F0] text-[#737373]",
  },
  {
    value: "scene",
    label: "Scene",
    labelCn: "场景图",
    description: "Lifestyle context with props and setting",
    icon: <SceneIcon />,
    accentClass: "text-[#1A1A1A]",
    bgClass: "bg-[#F5F5F0]",
    borderClass: "border-[#E8E8E3]",
    selectedBorderClass: "border-[#D4A853]",
    selectedBgClass: "bg-[#D4A853]/5",
    iconBgClass: "bg-emerald-50 text-emerald-600",
  },
  {
    value: "model",
    label: "Model",
    labelCn: "模特图",
    description: "Worn on a person for scale and appeal",
    icon: <ModelIcon />,
    accentClass: "text-[#1A1A1A]",
    bgClass: "bg-[#F5F5F0]",
    borderClass: "border-[#E8E8E3]",
    selectedBorderClass: "border-[#D4A853]",
    selectedBgClass: "bg-[#D4A853]/5",
    iconBgClass: "bg-violet-50 text-violet-600",
  },
  {
    value: "detail",
    label: "Detail",
    labelCn: "细节图",
    description: "Close-up macro shots of texture and craft",
    icon: <DetailIcon />,
    accentClass: "text-[#1A1A1A]",
    bgClass: "bg-[#F5F5F0]",
    borderClass: "border-[#E8E8E3]",
    selectedBorderClass: "border-[#D4A853]",
    selectedBgClass: "bg-[#D4A853]/5",
    iconBgClass: "bg-[#D4A853]/10 text-[#D4A853]",
  },
];

const COUNT_OPTIONS = [1, 3, 4, 5, 9];
const RATIO_OPTIONS: { value: AspectRatio; label: string; desc: string }[] = [
  { value: "1:1", label: "1:1", desc: "Square" },
  { value: "3:4", label: "3:4", desc: "Portrait" },
  { value: "4:3", label: "4:3", desc: "Landscape" },
];

// Only Pro model — Flash has no price advantage at 1K/2K resolutions
const DEFAULT_MODEL: ImageModel = "gemini-3-pro-image-preview";

const RESOLUTION_OPTIONS: { value: ImageResolution; label: string; desc: string }[] = [
  { value: "1k", label: "1K", desc: "Standard" },
  { value: "2k", label: "2K", desc: "High Res" },
];

// ─── Sub-components ─────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-semibold uppercase tracking-wide text-[#737373] mb-2.5">
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
    <div className="inline-flex rounded-lg border border-[#E8E8E3] bg-[#F5F5F0] p-0.5 gap-0.5">
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
              focus:outline-none focus:ring-2 focus:ring-[#D4A853]/30 focus:ring-offset-1
              ${
                isSelected
                  ? "bg-white shadow-sm text-[#D4A853] border border-[#D4A853]/40"
                  : "text-[#737373] hover:text-[#1A1A1A]"
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

// ─── Credit cost constants ───────────────────────────────────────────────────

const CREDITS_PER_IMAGE: Record<string, number> = {
  "1k": 7,
  "2k": 10,
};

// ─── Props ──────────────────────────────────────────────────────────────────

interface ImageStudioFormProps {
  onSubmit: (files: File[], productInfo: string, config: ImageConfig) => void;
  isSubmitting: boolean;
  isLocked: boolean;
  creditBalance?: number;
  isAdmin?: boolean;
}

// ─── Main Component ──────────────────────────────────────────────────────────

export function ImageStudioForm({
  onSubmit,
  isSubmitting,
  isLocked,
  creditBalance,
  isAdmin = false,
}: ImageStudioFormProps) {
  const [files, setFiles] = useState<File[]>([]);
  const selectedModel: ImageModel = DEFAULT_MODEL;
  const [selectedResolution, setSelectedResolution] = useState<ImageResolution>("2k");
  const [selectedCategory, setSelectedCategory] = useState<ImageCategory | null>(null);
  const [additionalPrompt, setAdditionalPrompt] = useState("");
  const [productInfo, setProductInfo] = useState("");
  const [count, setCount] = useState<number>(4);
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>("1:1");

  const estimatedCost = count * (CREDITS_PER_IMAGE[selectedResolution] ?? 7);
  const hasInsufficientCredits =
    !isAdmin &&
    typeof creditBalance === "number" &&
    creditBalance < estimatedCost;

  const canSubmit =
    files.length > 0 && !isSubmitting && !isLocked && !hasInsufficientCredits;

  const handleSubmit = useCallback(() => {
    if (!canSubmit) return;
    const config: ImageConfig = {
      category: selectedCategory,
      additional_prompt: additionalPrompt.trim(),
      count,
      aspect_ratio: aspectRatio,
      model: selectedModel,
      resolution: selectedResolution,
    };
    onSubmit(files, productInfo.trim(), config);
  }, [canSubmit, files, selectedCategory, additionalPrompt, productInfo, count, aspectRatio, selectedResolution, onSubmit]);

  const textareaClass =
    "w-full rounded-lg border border-[#E8E8E3] bg-[#F5F5F0] px-3 py-2.5 text-sm text-[#1A1A1A] placeholder:text-[#A3A3A3] focus:border-[#D4A853] focus:outline-none focus:ring-2 focus:ring-[#D4A853]/30 disabled:cursor-not-allowed disabled:opacity-50 resize-none";

  return (
    <div className="space-y-6">
      {/* Step 1 — Upload */}
      <Card className="bg-white border-[#E8E8E3] shadow-sm">
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
      <Card className="bg-white border-[#E8E8E3] shadow-sm">
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
                    focus:outline-none focus:ring-2 focus:ring-[#D4A853]/30
                    disabled:cursor-not-allowed disabled:opacity-50
                    ${
                      isSelected
                        ? `${opt.selectedBorderClass} ${opt.selectedBgClass} shadow-sm`
                        : `${opt.borderClass} bg-[#F5F5F0] hover:border-[#D4D4CF] hover:shadow-sm`
                    }
                  `}
                >
                  {isSelected && (
                    <span className="absolute top-2.5 right-2.5 flex h-4 w-4 items-center justify-center rounded-full bg-[#D4A853]">
                      <svg className="h-2.5 w-2.5 text-white" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                      </svg>
                    </span>
                  )}
                  <div className={`mb-2.5 flex h-10 w-10 items-center justify-center rounded-lg ${opt.iconBgClass}`}>
                    {opt.icon}
                  </div>
                  <div>
                    <p className={`text-sm font-semibold leading-tight ${isSelected ? "text-[#D4A853]" : "text-[#1A1A1A]"}`}>
                      {opt.label}
                      <span className="ml-1.5 text-xs font-normal opacity-60">{opt.labelCn}</span>
                    </p>
                    <p className="mt-0.5 text-xs text-[#737373] leading-snug">
                      {opt.description}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
          <p className="mt-2 text-xs text-[#737373]">
            Leave unselected to let AI choose the best type automatically.
          </p>
        </CardContent>
      </Card>

      {/* Step 4 — Count + Ratio + Resolution */}
      <Card className="bg-white border-[#E8E8E3] shadow-sm">
        <CardContent className="pt-5 space-y-5">
          <SectionLabel>3. Output settings</SectionLabel>

          <div className="space-y-2.5">
            <p className="text-sm font-medium text-[#1A1A1A]">
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
            <p className="text-sm font-medium text-[#1A1A1A]">
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

          <div className="space-y-2.5">
            <p className="text-sm font-medium text-[#1A1A1A]">
              Resolution
            </p>
            <SegmentedControl
              options={RESOLUTION_OPTIONS.map((r) => r.value)}
              value={selectedResolution}
              onChange={setSelectedResolution}
              disabled={isSubmitting || isLocked}
              renderOption={(v) => {
                const opt = RESOLUTION_OPTIONS.find((r) => r.value === v)!;
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

      {/* Step 5 — Optional text fields */}
      <Card className="bg-white border-[#E8E8E3] shadow-sm">
        <CardContent className="pt-5 space-y-4">
          <SectionLabel>4. Additional details (optional)</SectionLabel>

          <div className="space-y-1.5">
            <label htmlFor="product-info" className="block text-sm font-medium text-[#1A1A1A]">
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
            <p className="text-xs text-[#737373]">
              Help the AI understand your product — material, size, color, style.
            </p>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="style-prompt" className="block text-sm font-medium text-[#1A1A1A]">
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
            <p className="text-xs text-[#737373]">
              Describe the mood, lighting, background, or props you want.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Submit */}
      <div className="space-y-2.5">
        {/* Cost preview */}
        {!isLocked && (
          hasInsufficientCredits ? (
            <p className="text-xs font-medium text-red-600">
              Insufficient credits ({creditBalance} remaining, need {estimatedCost})
            </p>
          ) : (
            <p className="text-xs text-[#737373]">
              {isAdmin
                ? `Estimated cost: ${estimatedCost} credits (unlimited)`
                : `Estimated cost: ${estimatedCost} credits`}
            </p>
          )
        )}
        <div className="flex items-center gap-4">
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit}
            size="lg"
            aria-busy={isSubmitting}
            className={`font-semibold shadow-sm ${canSubmit ? "bg-[#D4A853] hover:bg-[#C49A48] text-white" : "bg-[#D4A853]/30 text-white/50"}`}
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
          {!canSubmit && !isSubmitting && !isLocked && !hasInsufficientCredits && (
            <p className="text-xs text-[#737373]">
              Upload at least one product photo to continue.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState, useEffect, useCallback } from "react";
import type { ImageResult } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const DIRECTION_LABELS: Record<string, string> = {
  hero: "Hero Shot",
  size_reference: "Size Reference",
  wearing_a: "Wearing A",
  wearing_b: "Wearing B",
  packaging: "Packaging",
  macro_detail: "Macro Detail",
  art_still_life: "Still Life",
  art_abstract: "Abstract Art",
  art_flat_lay: "Flat Lay",
  scene_daily: "Daily Scene",
  workshop: "Workshop",
  materials: "Materials",
  process: "Process",
  hero_angle_b: "Hero Angle B",
  wearing_couple: "Couple",
  wearing_editorial: "Editorial",
  wearing_intimate: "Intimate",
  art_editorial: "Art Editorial",
  color_variants: "Color Variants",
  styling_options: "Styling Options",
};

function directionLabel(direction: string): string {
  return DIRECTION_LABELS[direction] || direction;
}

function imageUrl(url: string): string {
  if (url.startsWith("http")) return url;
  return `${API_BASE}${url}`;
}

/* ------------------------------------------------------------------ */
/*  Skeleton shimmer placeholder                                       */
/* ------------------------------------------------------------------ */

function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-gray-200 dark:bg-gray-700 ${className}`}
    />
  );
}

/* ------------------------------------------------------------------ */
/*  Single image card                                                  */
/* ------------------------------------------------------------------ */

interface ImageCardProps {
  image: ImageResult;
  isHero?: boolean;
  onClick: () => void;
}

function ImageCard({ image, isHero, onClick }: ImageCardProps) {
  const [loaded, setLoaded] = useState(false);

  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        group relative overflow-hidden rounded-lg
        bg-gray-100 dark:bg-gray-800
        cursor-pointer
        transition-shadow duration-200
        hover:shadow-lg
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
        ${isHero ? "col-span-2 row-span-2" : ""}
      `}
    >
      {/* Aspect wrapper */}
      <div className="aspect-square w-full">
        {/* Skeleton shown until loaded */}
        {!loaded && (
          <div className="absolute inset-0 animate-pulse bg-gray-200 dark:bg-gray-700 rounded-lg" />
        )}

        <img
          src={imageUrl(image.url)}
          alt={directionLabel(image.direction)}
          onLoad={() => setLoaded(true)}
          className={`
            h-full w-full object-cover rounded-lg
            transition-opacity duration-500 ease-in-out
            ${loaded ? "opacity-100" : "opacity-0"}
          `}
        />
      </div>

      {/* Direction badge */}
      <span
        className="
          absolute bottom-2 left-2
          px-2 py-1
          text-xs font-medium
          text-white
          bg-black/60 backdrop-blur-sm
          rounded-md
          pointer-events-none
        "
      >
        {directionLabel(image.direction)}
      </span>
    </button>
  );
}

/* ------------------------------------------------------------------ */
/*  Lightbox overlay                                                   */
/* ------------------------------------------------------------------ */

interface LightboxProps {
  images: ImageResult[];
  currentIndex: number;
  onClose: () => void;
  onNavigate: (index: number) => void;
}

function Lightbox({ images, currentIndex, onClose, onNavigate }: LightboxProps) {
  const current = images[currentIndex];

  const goNext = useCallback(() => {
    onNavigate((currentIndex + 1) % images.length);
  }, [currentIndex, images.length, onNavigate]);

  const goPrev = useCallback(() => {
    onNavigate((currentIndex - 1 + images.length) % images.length);
  }, [currentIndex, images.length, onNavigate]);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight") goNext();
      if (e.key === "ArrowLeft") goPrev();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose, goNext, goPrev]);

  // Lock body scroll while lightbox is open
  useEffect(() => {
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = original;
    };
  }, []);

  if (!current) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`Image lightbox: ${directionLabel(current.direction)}`}
    >
      {/* Close button */}
      <button
        type="button"
        onClick={onClose}
        className="
          absolute top-4 right-4 z-10
          p-2 rounded-full
          text-white/70 hover:text-white
          bg-white/10 hover:bg-white/20
          transition-colors duration-150
          focus:outline-none focus:ring-2 focus:ring-white
        "
        aria-label="Close lightbox"
      >
        <svg
          className="w-6 h-6"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      {/* Previous button */}
      {images.length > 1 && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            goPrev();
          }}
          className="
            absolute left-4 z-10
            p-3 rounded-full
            text-white/70 hover:text-white
            bg-white/10 hover:bg-white/20
            transition-colors duration-150
            focus:outline-none focus:ring-2 focus:ring-white
          "
          aria-label="Previous image"
        >
          <svg
            className="w-6 h-6"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      )}

      {/* Image container -- stop propagation so clicking image doesn't close */}
      <div
        className="relative max-w-4xl max-h-[85vh] mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <img
          src={imageUrl(current.url)}
          alt={directionLabel(current.direction)}
          className="max-w-full max-h-[85vh] rounded-lg object-contain"
        />

        {/* Direction label */}
        <div className="absolute bottom-4 left-4 flex items-center gap-3">
          <span
            className="
              px-3 py-1.5
              text-sm font-medium
              text-white
              bg-black/60 backdrop-blur-sm
              rounded-md
            "
          >
            {directionLabel(current.direction)}
          </span>
          <span className="text-sm text-white/60">
            {currentIndex + 1} / {images.length}
          </span>
        </div>
      </div>

      {/* Next button */}
      {images.length > 1 && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            goNext();
          }}
          className="
            absolute right-4 z-10
            p-3 rounded-full
            text-white/70 hover:text-white
            bg-white/10 hover:bg-white/20
            transition-colors duration-150
            focus:outline-none focus:ring-2 focus:ring-white
          "
          aria-label="Next image"
        >
          <svg
            className="w-6 h-6"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </button>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main ImageGrid component                                           */
/* ------------------------------------------------------------------ */

interface ImageGridProps {
  images: ImageResult[];
  isGenerating: boolean;
  imageProgress: { total: number; completed: number };
}

export function ImageGrid({ images, isGenerating, imageProgress }: ImageGridProps) {
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  // Sort images: hero (index 0) first, then by index
  const sortedImages = [...images].sort((a, b) => a.index - b.index);

  const heroImage = sortedImages.find((img) => img.index === 0);
  const otherImages = sortedImages.filter((img) => img.index !== 0);

  const totalExpected = imageProgress.total || 10;
  const remainingSkeletons = isGenerating
    ? Math.max(0, totalExpected - images.length)
    : 0;

  // Empty + generating = full skeleton grid
  if (isGenerating && images.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-gray-400 border-t-transparent" />
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Generating images {imageProgress.completed}/{imageProgress.total}...
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {/* Hero skeleton spans 2 cols */}
          <Skeleton className="col-span-2 row-span-2 aspect-square" />
          {Array.from({ length: Math.max(0, totalExpected - 1) }, (_, i) => (
            <Skeleton key={`skel-${i}`} className="aspect-square" />
          ))}
        </div>
      </div>
    );
  }

  // Empty + not generating = empty state
  if (!isGenerating && images.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 dark:border-gray-600 p-12 text-center">
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-lg bg-gray-100 dark:bg-gray-800">
          <svg
            className="h-6 w-6 text-gray-400"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0 0 22.5 18.75V5.25A2.25 2.25 0 0 0 20.25 3H3.75A2.25 2.25 0 0 0 1.5 5.25v13.5A2.25 2.25 0 0 0 3.75 21Z"
            />
          </svg>
        </div>
        <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
          No images yet
        </p>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Generated product images will appear here.
        </p>
      </div>
    );
  }

  // Find the index of a given image within sortedImages for lightbox navigation
  function openLightbox(image: ImageResult) {
    const idx = sortedImages.findIndex(
      (img) => img.index === image.index
    );
    setLightboxIndex(idx >= 0 ? idx : 0);
  }

  return (
    <div className="space-y-4">
      {/* Progress text */}
      {isGenerating && (
        <div className="flex items-center gap-2">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Generating images {imageProgress.completed}/{imageProgress.total}...
          </p>
        </div>
      )}

      {/* Image grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {/* Hero image -- spans 2 cols and 2 rows */}
        {heroImage ? (
          <ImageCard
            image={heroImage}
            isHero
            onClick={() => openLightbox(heroImage)}
          />
        ) : (
          isGenerating && (
            <Skeleton className="col-span-2 row-span-2 aspect-square" />
          )
        )}

        {/* Remaining images */}
        {otherImages.map((image) => (
          <ImageCard
            key={image.index}
            image={image}
            onClick={() => openLightbox(image)}
          />
        ))}

        {/* Remaining skeletons for images not yet loaded */}
        {Array.from(
          { length: heroImage ? remainingSkeletons : Math.max(0, remainingSkeletons - 1) },
          (_, i) => (
            <Skeleton key={`remaining-skel-${i}`} className="aspect-square" />
          )
        )}
      </div>

      {/* Lightbox */}
      {lightboxIndex !== null && sortedImages.length > 0 && (
        <Lightbox
          images={sortedImages}
          currentIndex={lightboxIndex}
          onClose={() => setLightboxIndex(null)}
          onNavigate={setLightboxIndex}
        />
      )}
    </div>
  );
}

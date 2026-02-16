"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface ImageUploaderProps {
  files: File[];
  onChange: (files: File[]) => void;
  disabled?: boolean;
}

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const MAX_FILES = 10;

export function ImageUploader({ files, onChange, disabled }: ImageUploaderProps) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const objectUrlsRef = useRef<string[]>([]);

  // Clean up all object URLs on unmount
  useEffect(() => {
    return () => {
      objectUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

  // Rebuild object URLs whenever files change, revoking stale ones
  const [previews, setPreviews] = useState<string[]>([]);

  useEffect(() => {
    // Revoke previous URLs
    objectUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));

    // Create new URLs
    const urls = files.map((file) => URL.createObjectURL(file));
    objectUrlsRef.current = urls;
    setPreviews(urls);

    return () => {
      urls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [files]);

  const handleFiles = useCallback(
    (incoming: FileList | File[]) => {
      const newFiles = Array.from(incoming);

      // Filter out files exceeding max size
      const validFiles: File[] = [];
      const rejected: string[] = [];

      for (const file of newFiles) {
        if (file.size > MAX_FILE_SIZE) {
          rejected.push(file.name);
        } else {
          validFiles.push(file);
        }
      }

      if (rejected.length > 0) {
        alert(
          `The following files exceed the 10 MB limit and were skipped:\n${rejected.join("\n")}`
        );
      }

      // Merge with existing files, capping at MAX_FILES
      const merged = [...files, ...validFiles];
      if (merged.length > MAX_FILES) {
        alert(`You can upload a maximum of ${MAX_FILES} images. Only the first ${MAX_FILES} will be kept.`);
        onChange(merged.slice(0, MAX_FILES));
      } else {
        onChange(merged);
      }
    },
    [files, onChange]
  );

  const removeFile = useCallback(
    (index: number) => {
      const updated = files.filter((_, i) => i !== index);
      onChange(updated);
    },
    [files, onChange]
  );

  const onDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!disabled) setDragOver(true);
    },
    [disabled]
  );

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (disabled) return;
      if (e.dataTransfer.files.length > 0) {
        handleFiles(e.dataTransfer.files);
      }
    },
    [disabled, handleFiles]
  );

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFiles(e.target.files);
      }
      // Reset so the same file(s) can be re-selected
      e.target.value = "";
    },
    [handleFiles]
  );

  const openPicker = useCallback(() => {
    if (!disabled) inputRef.current?.click();
  }, [disabled]);

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <button
        type="button"
        onClick={openPicker}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        disabled={disabled}
        aria-label="Upload product images by dragging and dropping or clicking to select files"
        className={`
          w-full
          rounded-lg border-2 border-dashed
          p-8
          flex flex-col items-center justify-center gap-2
          transition-colors duration-200
          focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
          ${
            disabled
              ? "border-gray-200 bg-gray-50 cursor-not-allowed dark:border-gray-700 dark:bg-gray-900"
              : dragOver
                ? "border-blue-500 bg-blue-50 dark:border-blue-400 dark:bg-blue-950"
                : "border-gray-300 bg-white hover:border-gray-400 dark:border-gray-600 dark:bg-gray-800 dark:hover:border-gray-500"
          }
        `}
      >
        {/* Upload icon */}
        <div
          className={`
            flex h-12 w-12 items-center justify-center rounded-lg
            ${
              dragOver
                ? "bg-blue-100 dark:bg-blue-900"
                : "bg-gray-100 dark:bg-gray-700"
            }
          `}
        >
          <svg
            className={`
              h-6 w-6
              ${
                dragOver
                  ? "text-blue-500 dark:text-blue-400"
                  : "text-gray-400 dark:text-gray-500"
              }
            `}
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5"
            />
          </svg>
        </div>

        <p
          className={`
            text-sm font-medium
            ${
              dragOver
                ? "text-blue-700 dark:text-blue-300"
                : "text-gray-900 dark:text-gray-100"
            }
          `}
        >
          Drag &amp; drop product images
        </p>
        <p
          className={`
            text-xs
            ${
              dragOver
                ? "text-blue-500 dark:text-blue-400"
                : "text-gray-500 dark:text-gray-400"
            }
          `}
        >
          or click to select files
        </p>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
          Up to {MAX_FILES} images, max {MAX_FILE_SIZE / (1024 * 1024)} MB each
        </p>
      </button>

      {/* Hidden file input */}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        onChange={onInputChange}
        className="hidden"
        aria-hidden="true"
        tabIndex={-1}
      />

      {/* Thumbnail preview grid */}
      {files.length > 0 && (
        <div>
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            {files.length} {files.length === 1 ? "image" : "images"} selected
          </p>
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-3">
            {files.map((file, index) => (
              <div
                key={`${file.name}-${file.size}-${index}`}
                className="group relative aspect-square rounded-lg overflow-hidden bg-gray-100 dark:bg-gray-800"
              >
                <img
                  src={previews[index]}
                  alt={file.name}
                  className="h-full w-full object-cover rounded-lg"
                />

                {/* File name overlay on hover */}
                <div
                  className="
                    absolute inset-x-0 bottom-0
                    px-1.5 py-1
                    bg-black/60 backdrop-blur-sm
                    opacity-0 group-hover:opacity-100
                    transition-opacity duration-150
                    pointer-events-none
                  "
                >
                  <p className="text-xs text-white truncate">{file.name}</p>
                </div>

                {/* Remove button */}
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeFile(index);
                  }}
                  disabled={disabled}
                  aria-label={`Remove ${file.name}`}
                  className="
                    absolute top-1.5 right-1.5
                    flex h-6 w-6 items-center justify-center
                    rounded-full
                    bg-black/60 hover:bg-red-600
                    text-white/80 hover:text-white
                    opacity-0 group-hover:opacity-100
                    transition-all duration-150
                    focus:outline-none focus:ring-2 focus:ring-red-500 focus:opacity-100
                    disabled:pointer-events-none
                  "
                >
                  <svg
                    className="h-3.5 w-3.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

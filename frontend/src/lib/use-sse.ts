"use client";

import { useCallback, useRef, useState } from "react";
import type { SSEEvent } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface UseSSEOptions {
  onEvent?: (event: SSEEvent) => void;
  onComplete?: (data: unknown) => void;
  onError?: (error: string) => void;
}

/**
 * Parse SSE text chunks into events.
 * Format: "event: <type>\ndata: <json>\n\n"
 */
function parseSSEChunk(chunk: string): SSEEvent[] {
  const events: SSEEvent[] = [];
  const blocks = chunk.split("\n\n").filter(Boolean);

  for (const block of blocks) {
    let eventType = "";
    let data = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event: ")) {
        eventType = line.slice(7);
      } else if (line.startsWith("data: ")) {
        data = line.slice(6);
      }
    }
    if (eventType && data) {
      try {
        events.push({ event: eventType, data: JSON.parse(data) } as SSEEvent);
      } catch {
        // Skip malformed JSON
      }
    }
  }
  return events;
}

export function useSSE(options: UseSSEOptions = {}) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(
    async (url: string, body?: Record<string, unknown> | FormData) => {
      // Abort any existing stream
      abortRef.current?.abort();

      setEvents([]);
      setIsRunning(true);

      const controller = new AbortController();
      abortRef.current = controller;

      const isFormData = body instanceof FormData;

      try {
        const res = await fetch(`${API_BASE}${url}`, {
          method: "POST",
          // Let browser set Content-Type with boundary for FormData
          ...(isFormData ? {} : { headers: { "Content-Type": "application/json" } }),
          credentials: "include",
          body: isFormData ? body : body ? JSON.stringify(body) : undefined,
          signal: controller.signal,
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }));
          options.onError?.(err.detail || "Request failed");
          setIsRunning(false);
          return;
        }

        const reader = res.body?.getReader();
        if (!reader) {
          options.onError?.("No response body");
          setIsRunning(false);
          return;
        }

        const decoder = new TextDecoder();
        let buffer = "";

        const processBuffer = (buf: string) => {
          const lastDoubleNewline = buf.lastIndexOf("\n\n");
          if (lastDoubleNewline === -1) return buf;

          const complete = buf.slice(0, lastDoubleNewline + 2);
          const remainder = buf.slice(lastDoubleNewline + 2);

          const parsed = parseSSEChunk(complete);
          for (const event of parsed) {
            setEvents((prev) => [...prev, event]);
            options.onEvent?.(event);

            if (event.event === "complete") {
              options.onComplete?.(event.data);
            }
            if (event.event === "error") {
              options.onError?.((event.data as { message: string }).message);
            }
          }
          return remainder;
        };

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          buffer = processBuffer(buffer);
        }

        // Flush any remaining data in the buffer after stream ends
        buffer += decoder.decode();
        processBuffer(buffer);
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          options.onError?.((err as Error).message || "Stream failed");
        }
      } finally {
        setIsRunning(false);
      }
    },
    [options]
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
    setIsRunning(false);
  }, []);

  return { events, isRunning, start, stop };
}

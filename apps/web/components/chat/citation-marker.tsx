"use client";

import { cn } from "@/lib/utils";

interface CitationMarkerProps {
  index: number;
  isActive?: boolean;
  onSelect?: (index: number, target?: HTMLButtonElement) => void;
}

export function CitationMarker({
  index,
  isActive = false,
  onSelect,
}: CitationMarkerProps) {
  return (
    <button
      type="button"
      aria-label={`Open citation ${index}`}
      aria-pressed={isActive}
      onClick={(event) => onSelect?.(index, event.currentTarget)}
      className={cn(
        "inline-flex h-6 min-w-6 items-center justify-center rounded-md border px-1.5 align-baseline font-mono text-[11px] font-semibold leading-none transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/10 focus-visible:ring-offset-0",
        isActive
          ? "border-amber-500 bg-amber-500 text-white"
          : "border-amber-300 bg-amber-100 text-amber-900 hover:border-amber-400 hover:bg-amber-200"
      )}
    >
      [{index}]
    </button>
  );
}

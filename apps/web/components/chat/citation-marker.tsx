"use client";

import { cn } from "@/lib/utils";

interface CitationMarkerProps {
  index: number;
  isActive?: boolean;
  onSelect?: (index: number) => void;
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
      onClick={() => onSelect?.(index)}
      className={cn(
        "inline-flex h-6 min-w-6 items-center justify-center rounded-md border px-1.5 align-baseline text-[11px] font-semibold leading-none transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        isActive
          ? "border-slate-900 bg-slate-900 text-white"
          : "border-slate-300 bg-slate-100 text-slate-700 hover:border-slate-400 hover:bg-slate-200"
      )}
    >
      [{index}]
    </button>
  );
}

"use client";

import type { ChatCitation } from "@/lib/chat-stream";
import { cn } from "@/lib/utils";

interface CitationCardProps {
  citation: ChatCitation;
  isActive?: boolean;
  onSelect?: (index: number) => void;
}

export function CitationCard({
  citation,
  isActive = false,
  onSelect,
}: CitationCardProps) {
  return (
    <button
      type="button"
      aria-label={`View citation ${citation.citation_index} from ${citation.source_title}`}
      aria-pressed={isActive}
      onClick={() => onSelect?.(citation.citation_index)}
      className={cn(
        "w-full rounded-2xl border px-4 py-3 text-left transition-colors shadow-sm focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/10 focus-visible:ring-offset-0",
        isActive
          ? "border-amber-500 bg-amber-500 text-white"
          : "border-amber-200 bg-amber-50/70 hover:border-amber-300 hover:bg-amber-100/70"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p
            className={cn(
              "font-mono text-[11px] font-semibold uppercase tracking-[0.18em]",
              isActive ? "text-white/70" : "text-muted-foreground"
            )}
          >
            Citation [{citation.citation_index}]
          </p>
          <p className="mt-1 truncate text-sm font-semibold">{citation.source_title}</p>
          <p
            className={cn(
              "mt-2 font-mono text-[13px] leading-6",
              isActive ? "text-white/90" : "text-amber-950/90"
            )}
          >
            {citation.quote}
          </p>
        </div>
        <div
          className={cn(
            "shrink-0 font-mono text-right text-xs",
            isActive ? "text-white/80" : "text-muted-foreground"
          )}
        >
          {citation.page ? <p>Page {citation.page}</p> : null}
          <p>Score {citation.score.toFixed(2)}</p>
        </div>
      </div>
    </button>
  );
}

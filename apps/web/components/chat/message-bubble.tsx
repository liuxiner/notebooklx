"use client";

import { CitationMarker } from "@/components/chat/citation-marker";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import type { ChatCitation } from "@/lib/chat-stream";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: ChatCitation[];
  statusMessage?: string | null;
}

interface MessageBubbleProps {
  message: ChatMessage;
  activeCitationIndex?: number | null;
  onCitationSelect?: (index: number) => void;
}

function renderAssistantContent(
  content: string,
  citations: ChatCitation[],
  activeCitationIndex: number | null | undefined,
  onCitationSelect?: (index: number) => void
) {
  const citationIndexSet = new Set(citations.map((citation) => citation.citation_index));
  const segments = content.split(/(\[\d+\])/g).filter(Boolean);

  return (
    <div className="whitespace-pre-wrap text-sm leading-6">
      {segments.map((segment, index) => {
        const match = /^\[(\d+)\]$/.exec(segment);

        if (!match) {
          return <span key={`${segment}-${index}`}>{segment}</span>;
        }

        const citationIndex = Number(match[1]);
        if (!citationIndexSet.has(citationIndex)) {
          return <span key={`${segment}-${index}`}>{segment}</span>;
        }

        return (
          <CitationMarker
            key={`${segment}-${index}`}
            index={citationIndex}
            isActive={activeCitationIndex === citationIndex}
            onSelect={onCitationSelect}
          />
        );
      })}
    </div>
  );
}

export function MessageBubble({
  message,
  activeCitationIndex,
  onCitationSelect,
}: MessageBubbleProps) {
  const isUser = message.role === "user";
  const showStatus = !isUser && message.statusMessage;
  const hasContent = Boolean(message.content.trim());

  return (
    <div className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[88%] rounded-3xl px-4 py-3 shadow-sm",
          isUser
            ? "rounded-br-md bg-primary text-primary-foreground"
            : "rounded-bl-md border border-border bg-card"
        )}
      >
        <p
          className={cn(
            "mb-2 text-[11px] font-semibold uppercase tracking-[0.18em]",
            isUser ? "text-primary-foreground/70" : "text-muted-foreground"
          )}
        >
          {isUser ? "You" : "Assistant"}
        </p>

        {showStatus ? (
          <div className="mb-2 flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner size="sm" className="text-muted-foreground" />
            <span>{message.statusMessage}</span>
          </div>
        ) : null}

        {hasContent ? (
          isUser ? (
            <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
          ) : (
            renderAssistantContent(
              message.content,
              message.citations,
              activeCitationIndex,
              onCitationSelect
            )
          )
        ) : null}

        {!isUser && message.citations.length > 0 ? (
          <p className="mt-3 text-xs text-muted-foreground">
            Uses {message.citations.length} source
            {message.citations.length === 1 ? "" : "s"}.
          </p>
        ) : null}
      </div>
    </div>
  );
}

"use client";

import { CitationMarker } from "@/components/chat/citation-marker";
import { Spinner } from "@/components/ui/spinner";
import type {
  ChatCitation,
  ChatFailureState,
  ChatMetricsEvent,
  ChatQueryRewriteEvent,
  ChatRetrievalEvent,
} from "@/lib/chat-stream";
import { cn } from "@/lib/utils";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: ChatCitation[];
  statusMessage?: string | null;
  guardrail?: ChatFailureState | null;
  retrieval?: ChatRetrievalEvent | null;
  metrics?: ChatMetricsEvent | null;
  queryRewrite?: ChatQueryRewriteEvent | null;
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
  const hasGuardrail = !isUser && Boolean(message.guardrail);
  const hasContent = Boolean(message.content.trim());

  return (
    <div className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[88%] rounded-[1.5rem] px-4 py-3.5 shadow-[0_1px_3px_rgba(15,23,42,0.06)]",
          isUser
            ? "rounded-br-md bg-primary text-primary-foreground"
            : "rounded-bl-md border border-slate-200 bg-slate-50/95 text-slate-800"
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

        {hasGuardrail ? (
          <div
            className={cn(
              "space-y-2 rounded-2xl border px-4 py-3",
              message.guardrail?.retryable
                ? "border-amber-200 bg-amber-50 text-amber-950"
                : "border-rose-200 bg-rose-50 text-rose-950"
            )}
          >
            <p className="text-sm font-semibold">{message.guardrail?.title}</p>
            <p className="text-sm leading-6">{message.guardrail?.message}</p>
            {message.guardrail?.hint ? (
              <p className="text-xs leading-5 text-current/80">{message.guardrail.hint}</p>
            ) : null}
          </div>
        ) : null}

        {!hasGuardrail && hasContent ? (
          isUser ? (
            <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
          ) : (
            <div className="flex items-end gap-1">
              {renderAssistantContent(
                message.content,
                message.citations,
                activeCitationIndex,
                onCitationSelect
              )}
              {showStatus ? (
                <span
                  aria-hidden="true"
                  className="mb-1 inline-block h-4 w-1.5 animate-pulse rounded-full bg-slate-300"
                />
              ) : null}
            </div>
          )
        ) : null}

        {!isUser && message.citations.length > 0 ? (
          <p className="mt-3 font-mono text-xs uppercase tracking-[0.12em] text-muted-foreground">
            Uses {message.citations.length} source
            {message.citations.length === 1 ? "" : "s"}.
          </p>
        ) : null}
      </div>
    </div>
  );
}

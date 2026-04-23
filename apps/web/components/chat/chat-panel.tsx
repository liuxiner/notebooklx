"use client";

import { FormEvent, KeyboardEvent, ReactNode, RefObject, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  AlertCircle,
  Bot,
  Check,
  ChevronDown,
  Eye,
  EyeOff,
  Loader2,
  SendHorizontal,
  Settings,
  Sparkles,
  X,
} from "lucide-react";

import { ChatPanel as ChatPanelV1 } from "@/components/chat/chat-pannel-v1";
import { MarkdownWithCitations } from "@/components/chat/markdown-with-citations";
import type { ChatMessage } from "@/components/chat/message-bubble";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import {
  normalizeChatFailure,
  streamNotebookChat,
  type ChatCitation,
  type ChatCitationsEvent,
  type ChatFailureState,
  type ChatMetricsEvent,
  type ChatQueryRewriteEvent,
  type ChatRetrievalEvent,
  type ChatStatusEvent,
} from "@/lib/chat-stream";
import { useAutoScroll } from "@/hooks/use-auto-scroll";
import { cn } from "@/lib/utils";

interface ChatPanelProps {
  notebookId: string;
  notebookName: string;
  variant?: "grounded" | "scholar";
}

type WorkflowState = "idle" | "active" | "done" | "error";

interface WorkflowNode {
  id: string;
  title: string;
  state: WorkflowState;
  summary: string;
  detailRows: Array<{ label: string; value: string }>;
  detailPanel?: ReactNode;
}

interface CitationPreviewState {
  messageId: string;
  citationIndex: number;
  anchorElement: HTMLButtonElement;
}

const STARTER_PROMPTS = [
  "Summarize the main ideas",
  "Where do the sources disagree?",
  "What evidence supports the key claim?",
];
const DEFAULT_TOP_K = 8;
const MIN_TOP_K = 1;
const MAX_TOP_K = 20;

function createMessageId(prefix: "user" | "assistant") {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function getIsDesktopViewport() {
  if (typeof window === "undefined") {
    return true;
  }

  return window.innerWidth >= 1200;
}

function formatCount(count: number, singular: string, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

function formatSeconds(value: number) {
  return `${value.toFixed(2)}s`;
}

function formatInteger(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatUsd(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: value >= 0.01 ? 2 : 4,
    maximumFractionDigits: value >= 0.01 ? 4 : 6,
  }).format(value);
}

function resolveTopK(value: string): number {
  const parsed = Number.parseInt(value, 10);

  if (Number.isNaN(parsed)) {
    return DEFAULT_TOP_K;
  }

  return Math.min(MAX_TOP_K, Math.max(MIN_TOP_K, parsed));
}

function mergeMetrics(current: ChatMetricsEvent | null | undefined, incoming: ChatMetricsEvent): ChatMetricsEvent {
  return {
    ...(current ?? {}),
    ...incoming,
  };
}

function groupRetrievalChunks(chunks: ChatCitation[]) {
  const groups = new Map<
    string,
    {
      key: string;
      sourceTitle: string;
      chunks: ChatCitation[];
    }
  >();

  for (const chunk of chunks) {
    const sourceTitle = chunk.source_title || "Untitled source";
    const key = chunk.source_id || sourceTitle;
    const existing = groups.get(key);

    if (existing) {
      existing.chunks.push(chunk);
      continue;
    }

    groups.set(key, {
      key,
      sourceTitle,
      chunks: [chunk],
    });
  }

  return Array.from(groups.values());
}

function normalizeEvidenceText(text: string) {
  return text.replace(/\r\n?/g, "\n").trim();
}

function EvidenceText({ text, className }: { text: string; className?: string }) {
  const normalized = normalizeEvidenceText(text);

  if (!normalized) {
    return null;
  }

  const blocks = normalized.split(/\n{2,}/).filter(Boolean);

  return (
    <div className={cn("space-y-3 text-sm leading-6 text-slate-700", className)}>
      {blocks.map((block, blockIndex) => {
        const lines = block
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean);

        if (!lines.length) {
          return null;
        }

        const segments: Array<
          | { type: "paragraph"; items: string[] }
          | { type: "unordered"; items: string[] }
          | { type: "ordered"; items: string[] }
        > = [];

        const flushSegment = (type: "paragraph" | "unordered" | "ordered", items: string[]) => {
          if (!items.length) {
            return;
          }

          segments.push({ type, items: [...items] });
        };

        let currentType: "paragraph" | "unordered" | "ordered" | null = null;
        let currentItems: string[] = [];

        for (const line of lines) {
          const unorderedMatch = /^[-*•]\s+(.+)$/.exec(line);
          const orderedMatch = /^\d+[.)]\s+(.+)$/.exec(line);
          const nextType = unorderedMatch ? "unordered" : orderedMatch ? "ordered" : "paragraph";
          const value = unorderedMatch?.[1] || orderedMatch?.[1] || line;

          if (currentType && currentType !== nextType) {
            flushSegment(currentType, currentItems);
            currentItems = [];
          }

          currentType = nextType;
          currentItems.push(value);
        }

        if (currentType) {
          flushSegment(currentType, currentItems);
        }

        return (
          <div key={`block-${blockIndex}`} className="space-y-3">
            {segments.map((segment, segmentIndex) => {
              if (segment.type === "unordered") {
                return (
                  <ul
                    key={`unordered-${blockIndex}-${segmentIndex}`}
                    className="list-disc space-y-1.5 pl-5 marker:text-[#7483f6]"
                  >
                    {segment.items.map((item, itemIndex) => (
                      <li key={`unordered-${blockIndex}-${segmentIndex}-${itemIndex}`}>{item}</li>
                    ))}
                  </ul>
                );
              }

              if (segment.type === "ordered") {
                return (
                  <ol
                    key={`ordered-${blockIndex}-${segmentIndex}`}
                    className="list-decimal space-y-1.5 pl-5 marker:font-medium marker:text-[#7483f6]"
                  >
                    {segment.items.map((item, itemIndex) => (
                      <li key={`ordered-${blockIndex}-${segmentIndex}-${itemIndex}`}>{item}</li>
                    ))}
                  </ol>
                );
              }

              return (
                <p key={`paragraph-${blockIndex}-${segmentIndex}`} className="break-words">
                  {segment.items.join(" ")}
                </p>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

function EvidenceItemCard({ chunk, showCitationBadge = false }: { chunk: ChatCitation; showCitationBadge?: boolean }) {
  const chunkLabel = typeof chunk.chunk_index === "number" ? `Chunk ${chunk.chunk_index + 1}` : "Chunk";
  const showContext = normalizeEvidenceText(chunk.content) !== normalizeEvidenceText(chunk.quote);

  return (
    <article className="">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          {showCitationBadge ? (
            <span className="rounded-full border border-[#dfe5ff] bg-[#f4f6ff] px-2 py-1 font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-[#5562d8]">
              Citation [{chunk.citation_index}]
            </span>
          ) : null}
          <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            {chunkLabel}
          </span>
        </div>

        <div className="shrink-0 text-right text-xs text-slate-500">
          {chunk.page ? <p>Page {chunk.page}</p> : null}
          <p>Score {chunk.score.toFixed(2)}</p>
        </div>
      </div>

      <div className="mt-3 space-y-3">
        <div className="rounded-[1rem] border border-[#dfe5ff] bg-[#f8f9ff] px-3 py-3">
          <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-[#5562d8]">
            Supporting quote
          </p>
          <EvidenceText text={chunk.quote} className="mt-2 text-slate-700" />
        </div>

        {showContext ? (
          <div className="rounded-[1rem] border border-slate-200 bg-slate-50/80 px-3 py-3">
            <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
              Context excerpt
            </p>
            <EvidenceText text={chunk.content} className="mt-2 text-slate-600" />
          </div>
        ) : null}
      </div>
    </article>
  );
}

function EvidenceCollectionPanel({
  chunks,
  showCitationBadge = false,
  missingCitationIndices = [],
}: {
  chunks: ChatCitation[];
  showCitationBadge?: boolean;
  missingCitationIndices?: number[];
}) {
  const groups = groupRetrievalChunks(chunks);

  return (
    <section className="mt-4">
      {missingCitationIndices.length > 0 ? (
        <div className="mt-3 rounded-[1rem] border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-950">
          Missing citation indices: {missingCitationIndices.join(", ")}
        </div>
      ) : null}

      <div className="mt-3 space-y-3">
        {groups.map((group) => (
          <div key={group.key} className="">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-900">{group.sourceTitle}</p>
                <p className="mt-1 text-xs text-slate-500">{formatCount(group.chunks.length, "chunk")}</p>
              </div>
            </div>

            <div className="mt-3 space-y-2.5">
              {group.chunks.map((chunk) => (
                <EvidenceItemCard
                  key={`${chunk.chunk_id}-${chunk.citation_index}`}
                  chunk={chunk}
                  showCitationBadge={showCitationBadge}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function getCitationPreviewLayout(anchorRect: DOMRect) {
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  const margin = 16;
  const gap = 12;
  const width = Math.min(420, viewportWidth - margin * 2);
  const centeredLeft = Math.max(margin, Math.round((viewportWidth - width) / 2));
  const anchoredLeft = Math.min(Math.max(anchorRect.left, margin), viewportWidth - width - margin);
  const left = viewportWidth < 640 ? centeredLeft : anchoredLeft;
  const spaceBelow = viewportHeight - anchorRect.bottom - gap - margin;
  const spaceAbove = anchorRect.top - gap - margin;

  if (spaceBelow < 220 && spaceAbove < 220) {
    return {
      left: centeredLeft,
      top: margin,
      width,
      maxHeight: viewportHeight - margin * 2,
    };
  }

  if (spaceBelow >= spaceAbove) {
    return {
      left,
      top: Math.min(anchorRect.bottom + gap, viewportHeight - margin - 220),
      width,
      maxHeight: Math.max(220, spaceBelow),
    };
  }

  const maxHeight = Math.max(220, spaceAbove);
  return {
    left,
    top: Math.max(margin, anchorRect.top - maxHeight - gap),
    width,
    maxHeight,
  };
}

function CitationPreviewPortal({
  citation,
  anchorElement,
  onClose,
}: {
  citation: ChatCitation;
  anchorElement: HTMLButtonElement;
  onClose: () => void;
}) {
  const [layout, setLayout] = useState(() => getCitationPreviewLayout(anchorElement.getBoundingClientRect()));

  useEffect(() => {
    const updateLayout = () => {
      if (!anchorElement.isConnected) {
        return;
      }

      setLayout(getCitationPreviewLayout(anchorElement.getBoundingClientRect()));
    };

    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    updateLayout();
    window.addEventListener("resize", updateLayout);
    window.addEventListener("scroll", updateLayout, true);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("resize", updateLayout);
      window.removeEventListener("scroll", updateLayout, true);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [anchorElement, onClose]);

  useEffect(() => {
    const previousBodyOverflow = document.body.style.overflow;
    const previousBodyOverscroll = document.body.style.overscrollBehavior;
    const previousHtmlOverflow = document.documentElement.style.overflow;

    document.body.style.overflow = "hidden";
    document.body.style.overscrollBehavior = "contain";
    document.documentElement.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.body.style.overscrollBehavior = previousBodyOverscroll;
      document.documentElement.style.overflow = previousHtmlOverflow;
    };
  }, []);

  if (typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <div
      className="fixed inset-0 z-[80]"
      onClick={(event) => event.stopPropagation()}
      onMouseDown={(event) => event.stopPropagation()}
      onWheel={(event) => event.stopPropagation()}
      onTouchMove={(event) => event.stopPropagation()}
    >
      <button
        type="button"
        aria-label="Close citation preview overlay"
        className="absolute inset-0 bg-slate-950/18 backdrop-blur-[2px]"
        onClick={onClose}
        onMouseDown={(event) => {
          event.stopPropagation();
        }}
        onWheel={(event) => {
          event.preventDefault();
          event.stopPropagation();
        }}
        onTouchMove={(event) => {
          event.preventDefault();
          event.stopPropagation();
        }}
      />
      <div
        role="dialog"
        aria-label={`Citation ${citation.citation_index} preview`}
        className="fixed overflow-hidden rounded-[1.5rem] border border-slate-200 bg-white/98 shadow-[0_24px_60px_rgba(15,23,42,0.18)] backdrop-blur"
        style={{
          top: `${layout.top}px`,
          left: `${layout.left}px`,
          width: `${layout.width}px`,
          maxHeight: `${layout.maxHeight}px`,
        }}
        onClick={(event) => event.stopPropagation()}
        onMouseDown={(event) => event.stopPropagation()}
        onWheelCapture={(event) => event.stopPropagation()}
        onTouchMoveCapture={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-4 py-4">
          <div className="min-w-0">
            <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-[#5562d8]">
              Citation [{citation.citation_index}]
            </p>
            <p className="mt-1 text-sm font-semibold text-slate-900">{citation.source_title}</p>
          </div>

          <div className="flex items-start gap-3">
            <div className="shrink-0 text-right text-xs text-slate-500">
              {citation.page ? <p>Page {citation.page}</p> : null}
              <p>Score {citation.score.toFixed(2)}</p>
            </div>
            <button
              type="button"
              aria-label="Close citation preview"
              className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 transition hover:bg-slate-50 hover:text-slate-700"
              onClick={onClose}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="max-h-[16rem] overflow-y-auto px-4 py-4">
          <EvidenceItemCard chunk={citation} />
        </div>
      </div>
    </div>,
    document.body,
  );
}

function CitationPreviewModal({ citation, onClose }: { citation: ChatCitation; onClose: () => void }) {
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogPortal>
        <DialogOverlay className="z-[80] bg-transparent backdrop-blur-0" />
        <DialogPrimitive.Content
          aria-label={`Citation ${citation.citation_index} preview`}
          className="fixed inset-x-0 bottom-0 z-[81] flex max-h-[80svh] min-h-0 flex-col overflow-hidden rounded-t-[1.75rem] border border-b-0 border-slate-200 bg-white shadow-[0_-24px_60px_rgba(15,23,42,0.2)] focus:outline-none"
          onOpenAutoFocus={(event) => event.preventDefault()}
        >
          <DialogPrimitive.Title className="sr-only">Citation {citation.citation_index} preview</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">
            Review the supporting quote and source metadata for this citation.
          </DialogPrimitive.Description>
          <div className="mx-auto mt-3 h-1.5 w-14 rounded-full bg-slate-300" />

          <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-4 py-4">
            <div className="min-w-0">
              <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-[#5562d8]">
                Citation [{citation.citation_index}]
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900">{citation.source_title}</p>
            </div>

            <div className="flex items-start gap-3">
              <div className="shrink-0 text-right text-xs text-slate-500">
                {citation.page ? <p>Page {citation.page}</p> : null}
                <p>Score {citation.score.toFixed(2)}</p>
              </div>
            </div>
          </div>

          <div className="min-h-0 overflow-y-auto overscroll-contain px-4 py-4">
            <EvidenceItemCard chunk={citation} />
          </div>
        </DialogPrimitive.Content>
      </DialogPortal>
    </Dialog>
  );
}

function formatChatStatus(payload: ChatStatusEvent): string {
  switch (payload.stage) {
    case "embedding_query":
      return "Embedding your question for retrieval";
    case "retrieving":
      return "Searching this notebook's sources";
    case "waiting_model":
      return "Waiting for the first answer chunk from the model";
    case "streaming":
      return "Streaming the answer into the chat";
    case "grounding":
      return "Checking citation alignment";
    default:
      return payload.message;
  }
}

function formatRewriteStrategy(strategy: string) {
  switch (strategy) {
    case "reference_resolution":
      return "Reference resolution";
    case "standalone_expansion":
      return "Standalone expansion";
    case "keyword_enrichment":
      return "Keyword enrichment";
    case "no_rewrite":
      return "No rewrite";
    default:
      return strategy.replaceAll("_", " ");
  }
}

function describeRewrite(rewrite: ChatQueryRewriteEvent) {
  const searchCount = rewrite.search_queries.length;
  const searchSummary = `${formatCount(
    searchCount,
    "retrieval search",
    "retrieval searches",
  )} prepared for notebook search.`;

  switch (rewrite.strategy) {
    case "reference_resolution":
      return `We resolved context-dependent references before retrieval. ${searchSummary}`;
    case "standalone_expansion":
      return `We expanded this follow-up into a standalone retrieval question. ${searchSummary}`;
    case "keyword_enrichment":
      return `We enriched this question with search-friendly terms before retrieval. ${searchSummary}`;
    default:
      return searchSummary;
  }
}

function getWorkflowStateLabel(state: WorkflowState) {
  switch (state) {
    case "done":
      return "Done";
    case "active":
      return "Live";
    case "error":
      return "Blocked";
    default:
      return "Waiting";
  }
}

function getWorkflowStateIcon(state: WorkflowState) {
  switch (state) {
    case "done":
      return <Check className="h-4 w-4" />;
    case "active":
      return <Loader2 className="h-4 w-4 animate-spin" />;
    case "error":
      return <AlertCircle className="h-4 w-4" />;
    default:
      return <Sparkles className="h-4 w-4" />;
  }
}

function WorkflowDetailNode({
  node,
  isExpanded,
  isLast,
}: {
  node: WorkflowNode;
  isExpanded: boolean;
  isLast: boolean;
}) {
  return (
    <div className="relative pt-1.5 pl-6">
      {!isLast ? <div className="absolute left-[7px] top-12 h-[calc(100%-1.25rem)] w-px bg-[#8a92ff]" /> : null}

      <div
        className={cn(
          "absolute left-0 top-5 flex h-5 w-5 p-1 items-center justify-center rounded-full border-[2px] bg-white shadow-sm",
          node.state === "done" && "border-[#eef0ff] bg-[#4f46e5] text-white",
          node.state === "active" && "border-[#eef0ff] bg-[#6d74ff] text-white",
          node.state === "error" && "border-[#ffe3e6] bg-rose-500 text-white",
          node.state === "idle" && "border-[#eef0ff] bg-white text-[#8a92ff]",
        )}
      >
        {getWorkflowStateIcon(node.state)}
      </div>

      <div>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p
              className={cn(
                "text-[1.05rem] font-semibold tracking-[-0.02em]",
                node.state === "idle" ? "text-[#7d86ec]" : "text-[#363e93]",
              )}
            >
              {node.title}
            </p>
            <p className={cn("mt-1 truncate text-sm", node.state === "idle" ? "text-[#9ea8ff]" : "text-[#7483f6]")}>
              {node.summary}
            </p>
          </div>
        </div>

        {isExpanded ? (
          <div className="mt-3">
            <dl className="grid items-start gap-2 text-sm text-slate-700">
              <div className="grid gap-1 grid-cols-[90px_minmax(0,1fr)]">
                <dt className="flex items-center font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Status
                </dt>
                <dd className="break-words text-sm leading-6 text-slate-700">{getWorkflowStateLabel(node.state)}</dd>
              </div>
              {node.detailRows.map((row) => (
                <div key={`${node.id}-${row.label}`} className="grid items-start gap-1 grid-cols-[90px_minmax(0,1fr)]">
                  <dt className="flex items-center mt-1 font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                    {row.label}
                  </dt>
                  <dd className="break-words text-sm leading-6 text-slate-700">{row.value}</dd>
                </div>
              ))}
            </dl>

            {node.detailPanel}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function MobileSheet({
  open,
  onOpenChange,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: ReactNode;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPortal>
        <DialogOverlay />
        <DialogPrimitive.Content
          className="fixed inset-x-0 bottom-0 z-50 flex h-[90vh] max-h-[90vh] min-h-0 flex-col overflow-hidden rounded-t-[2rem] border border-b-0 border-slate-200 bg-[linear-gradient(180deg,rgba(250,251,255,0.98),rgba(255,255,255,1))] shadow-[0_-24px_60px_rgba(15,23,42,0.18)] focus:outline-none"
          onOpenAutoFocus={(event) => event.preventDefault()}
        >
          <DialogPrimitive.Title className="sr-only">Curator AI Assistant</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">
            Continue the grounded notebook chat in a mobile sheet.
          </DialogPrimitive.Description>
          {children}
        </DialogPrimitive.Content>
      </DialogPortal>
    </Dialog>
  );
}

function ScholarChatPanel({ notebookId, notebookName }: Omit<ChatPanelProps, "variant">) {
  const [draft, setDraft] = useState("");
  const [topKInput, setTopKInput] = useState(String(DEFAULT_TOP_K));
  const [topKDraft, setTopKDraft] = useState(String(DEFAULT_TOP_K));
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [workflowRetrievalEvent, setWorkflowRetrievalEvent] = useState<ChatRetrievalEvent | null>(null);
  const [citationEvents, setCitationEvents] = useState<Record<string, ChatCitationsEvent>>({});
  const [isStreaming, setIsStreaming] = useState(false);
  const [chatFailure, setChatFailure] = useState<ChatFailureState | null>(null);
  const [workflowStage, setWorkflowStage] = useState<string>("idle");
  const [workflowStageStartedAt, setWorkflowStageStartedAt] = useState<number | null>(null);
  const [stageNow, setStageNow] = useState<number>(Date.now());
  const [workflowStatus, setWorkflowStatus] = useState(
    "We search this notebook's sources, draft an answer from the evidence, and show citations you can inspect.",
  );
  const [lastSubmittedQuestion, setLastSubmittedQuestion] = useState<string | null>(null);
  const [activeCitationMessageId, setActiveCitationMessageId] = useState<string | null>(null);
  const [activeCitationIndex, setActiveCitationIndex] = useState<number | null>(null);
  const [citationPreview, setCitationPreview] = useState<CitationPreviewState | null>(null);
  const [isWorkflowExpanded, setIsWorkflowExpanded] = useState(false);
  const [isTopKDialogOpen, setIsTopKDialogOpen] = useState(false);
  const [isDesktopViewport, setIsDesktopViewport] = useState(getIsDesktopViewport);
  const [isMobileSheetOpen, setIsMobileSheetOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const mobileTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const streamingMessageIdRef = useRef<string | null>(null);

  useEffect(() => {
    const handleResize = () => {
      setIsDesktopViewport(getIsDesktopViewport());
    };

    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  useEffect(() => {
    if (isDesktopViewport) {
      setIsMobileSheetOpen(false);
    }
  }, [isDesktopViewport]);

  useEffect(() => {
    if (isMobileSheetOpen) {
      return;
    }

    setCitationPreview(null);
  }, [isMobileSheetOpen]);

  useEffect(() => {
    if (!isDesktopViewport && isStreaming) {
      setIsMobileSheetOpen(true);
    }
  }, [isDesktopViewport, isStreaming]);

  const { forceScroll } = useAutoScroll({
    containerRef: scrollContainerRef,
    bottomRef,
    deps: [messages, isStreaming, isMobileSheetOpen],
  });

  useEffect(() => {
    if (!isStreaming || workflowStageStartedAt === null) {
      return;
    }

    const intervalId = window.setInterval(() => {
      setStageNow(Date.now());
    }, 250);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [isStreaming, workflowStageStartedAt]);

  useEffect(() => {
    if (!isMobileSheetOpen) {
      return;
    }

    const frame = window.requestAnimationFrame(() => {
      mobileTextareaRef.current?.focus();
    });

    return () => {
      window.cancelAnimationFrame(frame);
    };
  }, [isMobileSheetOpen]);

  useEffect(() => {
    if (!isTopKDialogOpen) {
      return;
    }

    setTopKDraft(topKInput);
  }, [isTopKDialogOpen, topKInput]);

  // During streaming, prefer data from the currently-streaming message
  const streamingMessage = isStreaming && streamingMessageIdRef.current
    ? messages.find((m) => m.id === streamingMessageIdRef.current)
    : null;

  const latestAssistantMessageWithCitations =
    (streamingMessage?.citations?.length ? streamingMessage : null) ||
    [...messages].reverse().find((message) => message.role === "assistant" && message.citations.length > 0);
  const latestAssistantMessageWithRetrieval =
    ((streamingMessage?.retrieval?.chunks?.length ?? 0) > 0 ? streamingMessage : null) ||
    [...messages].reverse().find((message) => message.role === "assistant" && (message.retrieval?.chunks.length ?? 0) > 0);
  const latestAssistantMessageWithMetrics =
    (streamingMessage?.metrics ? streamingMessage : null) ||
    [...messages].reverse().find((message) => message.role === "assistant" && Boolean(message.metrics));
  const latestAssistantMessageWithQueryRewrite =
    (streamingMessage?.queryRewrite ? streamingMessage : null) ||
    [...messages].reverse().find((message) => message.role === "assistant" && Boolean(message.queryRewrite));
  const citationPanelMessage =
    messages.find(
      (message) =>
        message.id === activeCitationMessageId && message.role === "assistant" && message.citations.length > 0,
    ) || latestAssistantMessageWithCitations;
  const retrievalPanelMessage =
    messages.find(
      (message) =>
        message.id === activeCitationMessageId &&
        message.role === "assistant" &&
        (message.retrieval?.chunks.length ?? 0) > 0,
    ) || latestAssistantMessageWithRetrieval;
  const metricsPanelMessage =
    messages.find(
      (message) => message.id === activeCitationMessageId && message.role === "assistant" && Boolean(message.metrics),
    ) || latestAssistantMessageWithMetrics;
  const queryRewritePanelMessage =
    messages.find(
      (message) =>
        message.id === activeCitationMessageId && message.role === "assistant" && Boolean(message.queryRewrite),
    ) || latestAssistantMessageWithQueryRewrite;

  const retrievalDiagnostics = retrievalPanelMessage?.retrieval ?? workflowRetrievalEvent;
  const retrievalGroups = groupRetrievalChunks(retrievalDiagnostics?.chunks ?? []);
  const chatMetrics = metricsPanelMessage?.metrics ?? null;
  const queryRewrite = queryRewritePanelMessage?.queryRewrite ?? null;
  const citationDiagnostics = citationPanelMessage ? (citationEvents[citationPanelMessage.id] ?? null) : null;
  const liveStageSeconds =
    workflowStageStartedAt !== null ? Math.max(0, (stageNow - workflowStageStartedAt) / 1000) : null;
  const previewCitationMessage = citationPreview
    ? messages.find(
        (message) =>
          message.id === citationPreview.messageId && message.role === "assistant" && message.citations.length > 0,
      ) || null
    : null;
  const previewCitation = citationPreview
    ? previewCitationMessage?.citations.find((citation) => citation.citation_index === citationPreview.citationIndex) ||
      null
    : null;

  const queryEmbeddingDisplay =
    typeof chatMetrics?.query_embedding_seconds === "number"
      ? formatSeconds(chatMetrics.query_embedding_seconds)
      : workflowStage === "embedding_query" && liveStageSeconds !== null
        ? `${liveStageSeconds.toFixed(1)}s...`
        : "Pending";
  const queryEmbeddingModelDisplay =
    chatMetrics?.query_embedding_model || (workflowStage === "done" ? "Unavailable" : "Pending");
  const queryEmbeddingTokensDisplay =
    typeof chatMetrics?.query_embedding_token_count === "number"
      ? formatInteger(chatMetrics.query_embedding_token_count)
      : workflowStage === "done"
        ? "Unavailable"
        : "Pending";
  const queryEmbeddingCostDisplay =
    typeof chatMetrics?.query_embedding_estimated_cost_usd === "number"
      ? formatUsd(chatMetrics.query_embedding_estimated_cost_usd)
      : typeof chatMetrics?.query_embedding_token_count === "number"
        ? "Not configured"
        : workflowStage === "done"
          ? "Unavailable"
          : "Pending";
  const retrievalDisplay =
    typeof chatMetrics?.retrieval_seconds === "number"
      ? formatSeconds(chatMetrics.retrieval_seconds)
      : workflowStage === "retrieving" && liveStageSeconds !== null
        ? `${liveStageSeconds.toFixed(1)}s...`
        : "Pending";
  const firstChunkDisplay =
    typeof chatMetrics?.time_to_first_delta_seconds === "number"
      ? formatSeconds(chatMetrics.time_to_first_delta_seconds)
      : workflowStage === "waiting_model" && liveStageSeconds !== null
        ? `${liveStageSeconds.toFixed(1)}s...`
        : "Waiting";
  const streamDurationDisplay =
    typeof chatMetrics?.llm_stream_seconds === "number"
      ? formatSeconds(chatMetrics.llm_stream_seconds)
      : workflowStage === "streaming" && liveStageSeconds !== null
        ? `${liveStageSeconds.toFixed(1)}s...`
        : "Pending";
  const streamDeliveryMessage =
    chatMetrics?.stream_delivery === "single_chunk"
      ? "Returned a single stream."
      : chatMetrics?.stream_delivery === "streaming"
        ? "Delivered incremental stream."
        : chatMetrics?.stream_delivery === "no_chunks"
          ? "No LLM deltas were received"
          : "Stream delivery mode ...";
  const promptTokensDisplay =
    typeof chatMetrics?.prompt_tokens === "number"
      ? formatInteger(chatMetrics.prompt_tokens)
      : workflowStage === "done"
        ? "Unavailable"
        : "Pending";
  const completionTokensDisplay =
    typeof chatMetrics?.completion_tokens === "number"
      ? formatInteger(chatMetrics.completion_tokens)
      : workflowStage === "done"
        ? "Unavailable"
        : "Pending";
  const totalTokensDisplay =
    typeof chatMetrics?.total_tokens === "number"
      ? formatInteger(chatMetrics.total_tokens)
      : workflowStage === "done"
        ? "Unavailable"
        : "Pending";
  const cachedTokensDisplay =
    typeof chatMetrics?.cached_tokens === "number" ? formatInteger(chatMetrics.cached_tokens) : null;
  const estimatedCostDisplay =
    typeof chatMetrics?.estimated_cost_usd === "number"
      ? formatUsd(chatMetrics.estimated_cost_usd)
      : typeof chatMetrics?.total_tokens === "number"
        ? "Not configured"
        : workflowStage === "done"
          ? "Unavailable"
          : "Pending";
  const usageSourceMessage =
    chatMetrics?.usage_source === "provider"
      ? "Reported by the model provider."
      : chatMetrics?.usage_source === "estimated"
        ? "Estimated locally."
        : chatMetrics?.usage_source === "mixed"
          ? "Combines provider-reported & local estimates."
          : chatMetrics?.usage_source === "none"
            ? "No model request was needed."
            : "Usage reporting will loads ...";
  const queryEmbeddingMessage =
    typeof chatMetrics?.query_embedding_requests === "number" && chatMetrics.query_embedding_requests > 1
      ? `Query embedding totals cover ${formatCount(chatMetrics.query_embedding_requests, "retrieval query", "retrieval queries")}.`
      : chatMetrics?.query_embedding_model
        ? `Query embedding used ${chatMetrics.query_embedding_model}.`
        : "Embedding configuration will appear after the first metrics update.";

  const canRetryLastQuestion =
    Boolean(lastSubmittedQuestion) &&
    Boolean(chatFailure?.retryable) &&
    chatFailure?.code !== "input_not_allowed" &&
    !isStreaming;

  const totalWorkflowSeconds = (() => {
    const components = [
      chatMetrics?.query_embedding_seconds,
      chatMetrics?.retrieval_seconds,
      chatMetrics?.prepare_seconds,
      chatMetrics?.time_to_first_delta_seconds,
      chatMetrics?.llm_stream_seconds,
    ].filter((value): value is number => typeof value === "number" && Number.isFinite(value));

    if (components.length > 0) {
      return components.reduce((sum, value) => sum + value, 0);
    }

    if (isStreaming && workflowStageStartedAt !== null) {
      return Math.max(0, (stageNow - workflowStageStartedAt) / 1000);
    }

    return null;
  })();

  const workflowStepState = (() => {
    const done = workflowStage === "done";
    const error = workflowStage === "error";
    const embeddingActive = workflowStage === "embedding_query";
    const retrievingActive = workflowStage === "retrieving";
    const synthesisActive =
      workflowStage === "waiting_model" || workflowStage === "streaming" || workflowStage === "grounding";

    return {
      embedding: done ? "done" : error ? "error" : embeddingActive ? "active" : "idle",
      retrieving: done ? "done" : error ? "error" : retrievingActive ? "active" : "idle",
      synthesis: done ? "done" : error ? "error" : synthesisActive ? "active" : "idle",
    } as const;
  })();

  const workflowNodes: WorkflowNode[] = [
    {
      id: "embedding",
      title: "Embedding Query",
      state: workflowStepState.embedding,
      summary:
        typeof chatMetrics?.query_embedding_seconds === "number"
          ? `Embedded the query in ${queryEmbeddingDisplay}.`
          : workflowStage === "embedding_query"
            ? "Vectorizing research intent..."
            : "Waiting for a new query...",
      detailRows: [
        { label: "Duration", value: queryEmbeddingDisplay },
        { label: "Model", value: queryEmbeddingModelDisplay },
        { label: "Tokens", value: queryEmbeddingTokensDisplay },
        { label: "Cost", value: queryEmbeddingCostDisplay },
        { label: "Notes", value: queryEmbeddingMessage },
      ],
    },
    {
      id: "rewrite",
      title: "Query Rewrite",
      state: queryRewrite ? "done" : workflowStage === "embedding_query" ? "active" : "idle",
      summary: queryRewrite
        ? queryRewrite.rewritten
          ? `${formatRewriteStrategy(queryRewrite.strategy)} prepared ${formatCount(
              queryRewrite.search_queries.length,
              "search",
              "searches",
            )}.`
          : "No rewrite was needed for this question."
        : "Rewrite strategy will appear here if the query is expanded.",
      detailRows: [
        { label: "Original", value: queryRewrite?.original_query || "Pending" },
        {
          label: "Strategy",
          value: queryRewrite ? formatRewriteStrategy(queryRewrite.strategy) : "Pending",
        },
        {
          label: "Standalone",
          value: queryRewrite?.standalone_query || "No standalone rewrite captured yet.",
        },
        {
          label: "Search Queries",
          value: queryRewrite?.search_queries.join(" • ") || "No retrieval variants prepared yet.",
        },
      ],
    },
    {
      id: "retrieval",
      title: "Retrieving Top-K",
      state: workflowStepState.retrieving,
      summary: retrievalDiagnostics
        ? `Retrieved ${formatCount(retrievalDiagnostics.chunk_count, "chunk")} across ${formatCount(
            retrievalDiagnostics.source_count,
            "source",
          )} in ${retrievalDisplay}.`
        : workflowStage === "retrieving"
          ? `Searching ${resolveTopK(topKInput)} notebook matches...`
          : "Notebook search evidence will appear after retrieval finishes.",
      detailRows: [
        { label: "Duration", value: retrievalDisplay },
        {
          label: "Coverage",
          value: retrievalDiagnostics
            ? `${formatCount(retrievalDiagnostics.chunk_count, "chunk")} from ${formatCount(
                retrievalDiagnostics.source_count,
                "source",
              )}`
            : "Pending",
        },
        {
          label: "Sources",
          value:
            retrievalGroups.map((group) => group.sourceTitle).join(" • ") ||
            "Source titles will appear after retrieval.",
        },
        { label: "Top-K", value: String(resolveTopK(topKInput)) },
      ],
      detailPanel: retrievalDiagnostics ? <EvidenceCollectionPanel chunks={retrievalDiagnostics.chunks} /> : null,
    },
    {
      id: "citations",
      title: "Citation Binding",
      state: citationDiagnostics ? "done" : workflowStage === "grounding" ? "active" : "idle",
      summary: citationDiagnostics
        ? `${citationDiagnostics.citation_indices.length} citations bound, ${citationDiagnostics.missing_citation_indices.length} missing.`
        : workflowStage === "grounding"
          ? "Binding answer spans to retrieved evidence..."
          : "Citation indices attach after the grounded answer is assembled.",
      detailRows: [
        {
          label: "Bound",
          value: citationDiagnostics?.citation_indices.join(", ") || "Pending",
        },
        {
          label: "Missing",
          value:
            citationDiagnostics && citationDiagnostics.missing_citation_indices.length > 0
              ? citationDiagnostics.missing_citation_indices.join(", ")
              : "None",
        },
        {
          label: "Count",
          value: citationDiagnostics ? String(citationDiagnostics.citations.length) : "Pending",
        },
      ],
      detailPanel: citationDiagnostics ? (
        <EvidenceCollectionPanel
          chunks={citationDiagnostics.citations}
          showCitationBadge
          missingCitationIndices={citationDiagnostics.missing_citation_indices}
        />
      ) : null,
    },
    {
      id: "synthesis",
      title: "Synthesis & Grounding",
      state: workflowStepState.synthesis,
      summary:
        workflowStage === "done"
          ? `Answer grounded and delivered. First chunk in ${firstChunkDisplay}.`
          : workflowStepState.synthesis === "active"
            ? workflowStatus
            : "Model synthesis begins after retrieval is ready.",
      detailRows: [
        { label: "Status", value: workflowStatus },
        { label: "First", value: firstChunkDisplay },
        { label: "Duration", value: streamDurationDisplay },
        { label: "Delivery", value: streamDeliveryMessage },
      ],
    },
    {
      id: "usage",
      title: "Usage & Cost",
      state:
        typeof chatMetrics?.prompt_tokens === "number" || typeof chatMetrics?.estimated_cost_usd === "number"
          ? "done"
          : "idle",
      summary:
        typeof chatMetrics?.total_tokens === "number"
          ? `${totalTokensDisplay} total tokens with estimated cost ${estimatedCostDisplay}.`
          : "Token usage and cost appear when the model responds.",
      detailRows: [
        { label: "Prompt", value: promptTokensDisplay },
        { label: "Completion", value: completionTokensDisplay },
        { label: "Total", value: totalTokensDisplay },
        { label: "Cached", value: cachedTokensDisplay || "Unavailable" },
        { label: "Cost", value: estimatedCostDisplay },
        { label: "Usage", value: usageSourceMessage },
      ],
    },
  ];
  const visibleWorkflowNodes = workflowNodes.filter((node) => {
    if (node.id === "embedding") {
      return true;
    }

    if (node.id === "rewrite") {
      return Boolean(queryRewrite);
    }

    if (node.id === "retrieval") {
      return (
        Boolean(retrievalDiagnostics) ||
        ["retrieving", "waiting_model", "streaming", "grounding", "done", "error"].includes(workflowStage)
      );
    }

    if (node.id === "citations") {
      return Boolean(citationDiagnostics) || workflowStage === "grounding";
    }

    if (node.id === "synthesis") {
      return ["waiting_model", "streaming", "grounding", "done", "error"].includes(workflowStage);
    }

    if (node.id === "usage") {
      return typeof chatMetrics?.prompt_tokens === "number" || typeof chatMetrics?.estimated_cost_usd === "number";
    }

    return false;
  });

  async function submitQuestion(questionInput: string) {
    const question = questionInput.trim();
    if (!question || isStreaming) {
      return;
    }

    const topK = resolveTopK(topKInput);
    const assistantMessageId = createMessageId("assistant");

    setDraft("");
    setTopKInput(String(topK));
    setChatFailure(null);
    setLastSubmittedQuestion(question);
    setWorkflowStage("embedding_query");
    setWorkflowStageStartedAt(Date.now());
    setStageNow(Date.now());
    setWorkflowStatus("Embedding your question for retrieval");
    setIsWorkflowExpanded(false);
    setActiveCitationMessageId(null);
    setActiveCitationIndex(null);
    setCitationPreview(null);
    setWorkflowRetrievalEvent(null);
    setIsStreaming(true);
    streamingMessageIdRef.current = assistantMessageId;
    setMessages((current) => [
      ...current,
      {
        id: createMessageId("user"),
        role: "user",
        content: question,
        citations: [],
      },
      {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        citations: [],
        metrics: null,
        retrieval: null,
        queryRewrite: null,
        statusMessage: "Embedding your question for retrieval",
        guardrail: null,
      },
    ]);

    forceScroll();

    const updateAssistantMessage = (updater: (message: ChatMessage) => ChatMessage) => {
      setMessages((current) =>
        current.map((message) => (message.id === assistantMessageId ? updater(message) : message)),
      );
    };

    try {
      await streamNotebookChat({
        notebookId,
        question,
        topK,
        onStatus: (payload) => {
          const friendlyStatus = formatChatStatus(payload);
          const timestamp = Date.now();
          setWorkflowStage(payload.stage);
          setWorkflowStageStartedAt(timestamp);
          setStageNow(timestamp);
          setWorkflowStatus(friendlyStatus);
          updateAssistantMessage((current) => ({
            ...current,
            statusMessage: friendlyStatus,
          }));
        },
        onMetrics: (payload: ChatMetricsEvent) => {
          updateAssistantMessage((current) => ({
            ...current,
            metrics: mergeMetrics(current.metrics, payload),
          }));
        },
        onQueryRewrite: (payload: ChatQueryRewriteEvent) => {
          updateAssistantMessage((current) => ({
            ...current,
            queryRewrite: payload,
          }));
        },
        onRetrieval: (payload: ChatRetrievalEvent) => {
          setWorkflowRetrievalEvent(payload);
          updateAssistantMessage((current) => ({
            ...current,
            retrieval: payload,
          }));
        },
        onCitations: (payload) => {
          updateAssistantMessage((current) => ({
            ...current,
            citations: payload.citations,
          }));
          setCitationEvents((current) => ({
            ...current,
            [assistantMessageId]: payload,
          }));
        },
        onAnswerDelta: ({ delta }) => {
          updateAssistantMessage((current) => ({
            ...current,
            content: `${current.content}${delta}`,
          }));
        },
        onAnswer: ({ answer }) => {
          updateAssistantMessage((current) => ({
            ...current,
            content: answer,
            statusMessage: null,
            guardrail: null,
          }));
        },
        onDone: () => {
          setWorkflowStage("done");
          setWorkflowStageStartedAt(null);
          setWorkflowStatus("Grounded answer ready");
          updateAssistantMessage((current) => ({
            ...current,
            statusMessage: null,
          }));
        },
      });
    } catch (error) {
      const failure = normalizeChatFailure(error);
      setChatFailure(failure);
      setWorkflowStage("error");
      setWorkflowStageStartedAt(null);
      setWorkflowStatus(failure.message);

      if (failure.code === "input_not_allowed") {
        setDraft(question);
      }

      updateAssistantMessage((current) => ({
        ...current,
        content: failure.message,
        statusMessage: null,
        guardrail: failure,
      }));
    } finally {
      setIsStreaming(false);
      streamingMessageIdRef.current = null;
    }
  }

  async function handleSubmit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    await submitQuestion(draft);
  }

  function handleTextareaKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSubmit();
    }
  }

  function openTopKDialog() {
    setTopKDraft(topKInput);
    setIsTopKDialogOpen(true);
  }

  function handleTopKDialogSubmit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    const nextTopK = String(resolveTopK(topKDraft));
    setTopKInput(nextTopK);
    setTopKDraft(nextTopK);
    setIsTopKDialogOpen(false);
  }

  function handleCitationSelect(messageId: string, citationIndex: number, target?: HTMLButtonElement) {
    setActiveCitationMessageId(messageId);
    setActiveCitationIndex(citationIndex);

    if (!target) {
      setCitationPreview(null);
      return;
    }

    setCitationPreview((current) => {
      if (current && current.messageId === messageId && current.citationIndex === citationIndex) {
        return null;
      }

      return {
        messageId,
        citationIndex,
        anchorElement: target,
      };
    });
  }

  function renderAssistantSections(message: ChatMessage) {
    const isActiveCitationMessage = message.id === citationPanelMessage?.id;

    return (
      <div className="space-y-4 rounded-[2rem] border border-slate-200 bg-white/95 p-4 shadow-[0_18px_45px_rgba(15,23,42,0.08)] tablet:p-5">
        {message.queryRewrite?.rewritten ? (
          <div className="rounded-[1.5rem] border border-[#dfe5ff] bg-[#f8f9ff] p-4">
            <p className="text-sm font-semibold text-[#4c57d7]">Standalone Query Rewrite:</p>
            <p className="mt-2 text-sm leading-6 text-slate-700">{message.queryRewrite.standalone_query}</p>
          </div>
        ) : null}

        {message.statusMessage ? (
          <div className="flex items-center gap-2 rounded-[1.25rem] border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
            <Spinner size="sm" className="text-slate-500" />
            <span>{message.statusMessage}</span>
          </div>
        ) : null}

        {message.guardrail ? (
          <div
            className={cn(
              "rounded-[1.5rem] border px-4 py-4",
              message.guardrail.retryable
                ? "border-amber-200 bg-amber-50 text-amber-950"
                : "border-rose-200 bg-rose-50 text-rose-950",
            )}
          >
            <p className="text-sm font-semibold">{message.guardrail.title}</p>
            <p className="mt-2 text-sm leading-6">{message.guardrail.message}</p>
            {message.guardrail.hint ? (
              <p className="mt-2 text-xs leading-5 text-current/80">{message.guardrail.hint}</p>
            ) : null}
          </div>
        ) : null}

        {message.content.trim() ? (
          <div className="rounded-[1.75rem] bg-[#fbfbfd] px-4 py-5 tablet:px-5">
            <MarkdownWithCitations
              content={message.content}
              citations={message.citations}
              activeCitationIndex={isActiveCitationMessage ? activeCitationIndex : null}
              onCitationSelect={(citationIndex, target) => handleCitationSelect(message.id, citationIndex, target)}
              className="text-[15px] leading-8 tracking-[-0.01em] text-slate-900 tablet:text-[17px]"
            />
          </div>
        ) : null}
      </div>
    );
  }

  function renderConversation() {
    if (messages.length === 0) {
      return (
        <div className="rounded-[1.75rem] border border-slate-200 bg-white/92 p-5 shadow-[0_12px_32px_rgba(15,23,42,0.06)]">
          <div className="flex items-start gap-3">
            <div className="flex p-1.5 items-center justify-center rounded-xl bg-[#4f46e5] text-white">
              <Bot className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Curator assistant</p>
              <p className="mt-1 text-base font-semibold text-slate-900">Start with a grounded question</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                Ask about themes, compare sources, or request a concise summary for {notebookName}.
              </p>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {STARTER_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-[#b9c1ff] hover:bg-[#f5f6ff]"
                onClick={() => {
                  setDraft(prompt);
                  if (!isDesktopViewport) {
                    setIsMobileSheetOpen(true);
                  }
                }}
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      );
    }

    return (
      <div className="space-y-4">
        {messages.map((message) =>
          message.role === "user" ? (
            <div
              key={message.id}
              className="rounded-[1.5rem] bg-slate-100 px-4 py-4 text-[15px] leading-8 text-slate-700"
            >
              {message.content}
            </div>
          ) : (
            <div key={message.id}>{renderAssistantSections(message)}</div>
          ),
        )}
      </div>
    );
  }

  function renderWorkflowPanel() {
    return (
      <section
        className={cn(
          "rounded-[2rem] border border-[#dfe5ff] bg-[linear-gradient(180deg,rgba(238,242,255,0.96),rgba(242,246,255,0.96))] p-5 shadow-[0_14px_34px_rgba(99,113,173,0.12)] transition-[max-height] duration-200 ease-out",
          isWorkflowExpanded ? "max-h-none" : "max-h-[15rem] overflow-hidden",
        )}
      >
        <div className="flex items-center justify-between gap-4 pt-2">
          <div className="text-sm font-semibold uppercase tracking-[0.08em] text-[#4d57db]">Process workflow</div>

          <div className="flex items-center gap-2">
            <div className="font-mono text-xs text-[#7483f6]">
              {totalWorkflowSeconds !== null ? `${totalWorkflowSeconds.toFixed(1)}s total` : "Pending"}
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8 rounded-full border border-[#dfe5ff] bg-white text-[#6674d8] hover:bg-[#f7f8ff] hover:text-[#3f49c9]"
              aria-pressed={isWorkflowExpanded}
              aria-label={isWorkflowExpanded ? "Hide workflow details" : "Show workflow details"}
              onClick={() => setIsWorkflowExpanded((current) => !current)}
            >
              {isWorkflowExpanded ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
            </Button>
          </div>
        </div>

        <div
          className={cn(
            "mt-2 space-y-4 overscroll-contain",
            isWorkflowExpanded ? "max-h-none overflow-visible" : "max-h-[8rem] overflow-y-auto pr-1",
          )}
        >
          {visibleWorkflowNodes.map((node, index) => (
            <WorkflowDetailNode
              key={node.id}
              node={node}
              isExpanded={isWorkflowExpanded}
              isLast={index === visibleWorkflowNodes.length - 1}
            />
          ))}
        </div>

        {canRetryLastQuestion ? (
          <div className="mt-4">
            <Button type="button" variant="outline" onClick={() => void submitQuestion(lastSubmittedQuestion ?? "")}>
              Try again
            </Button>
          </div>
        ) : null}
      </section>
    );
  }

  function renderTopKSettingsDialog() {
    return (
      <Dialog open={isTopKDialogOpen} onOpenChange={setIsTopKDialogOpen}>
        <DialogContent className="max-w-md rounded-[1.75rem] border border-slate-200 bg-[linear-gradient(180deg,rgba(250,251,255,0.98),rgba(255,255,255,1))] p-0 shadow-[0_24px_60px_rgba(15,23,42,0.18)]">
          <form className="space-y-0" onSubmit={handleTopKDialogSubmit}>
            <DialogHeader className="border-b border-slate-200 px-6 py-5 text-left">
              <DialogTitle>Retrieval settings</DialogTitle>
              <DialogDescription>
                Adjust how many notebook chunks are retrieved before answer synthesis. This applies to your next
                question.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 px-6 py-5">
              <div className="rounded-[1.25rem] border border-[#dfe5ff] bg-[#f7f8ff] px-4 py-3 text-sm text-[#4d57db]">
                Current Top-K: <span className="font-semibold">{resolveTopK(topKInput)}</span>
              </div>

              <div className="space-y-2">
                <Label
                  htmlFor="chat-top-k-settings"
                  className="font-mono text-[11px] uppercase tracking-[0.16em] text-slate-500"
                >
                  Retrieving Top-K
                </Label>
                <Input
                  id="chat-top-k-settings"
                  aria-label="Top-K"
                  type="number"
                  inputMode="numeric"
                  min={MIN_TOP_K}
                  max={MAX_TOP_K}
                  step={1}
                  value={topKDraft}
                  onChange={(event) => setTopKDraft(event.target.value)}
                  onBlur={() => setTopKDraft(String(resolveTopK(topKDraft)))}
                />
                <p className="text-sm leading-6 text-slate-500">
                  Choose a value between {MIN_TOP_K} and {MAX_TOP_K}. Higher values widen retrieval coverage but may
                  increase synthesis noise.
                </p>
              </div>
            </div>

            <DialogFooter className="gap-3 border-t border-slate-200 px-6 py-4 sm:justify-end sm:space-x-0">
              <Button type="button" variant="outline" onClick={() => setIsTopKDialogOpen(false)}>
                Cancel
              </Button>
              <Button type="submit">Apply</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    );
  }

  function renderComposer(textareaId: string, textareaRef?: RefObject<HTMLTextAreaElement>) {
    return (
      <form onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor={textareaId}>
          Ask a source-grounded question
        </label>
        <div className="relative">
          <Textarea
            id={textareaId}
            ref={textareaRef}
            placeholder="Ask your scholarship..."
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleTextareaKeyDown}
            disabled={isStreaming}
            className="tablet:min-h-[112px] resize-none rounded-[1.75rem] border-slate-200 bg-white/95 px-5 pr-20 pt-4 text-base shadow-[0_10px_26px_rgba(15,23,42,0.06)] placeholder:text-slate-400 tablet:min-h-[120px]"
          />

          <Button
            type="submit"
            size="icon"
            aria-label="Send"
            disabled={!draft.trim() || isStreaming}
            className="absolute bottom-3 right-3 h-12 w-12 rounded-2xl shadow-[0_12px_24px_rgba(79,70,229,0.22)]"
          >
            <SendHorizontal className="h-4 w-4" />
            <span className="sr-only">Send</span>
          </Button>
        </div>
      </form>
    );
  }

  function renderTopKSettingsButton() {
    return (
      <button
        type="button"
        aria-label="Settings"
        className="flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm transition hover:bg-slate-50 hover:text-slate-700"
        onClick={openTopKDialog}
      >
        <Settings className="h-4 w-4" />
      </button>
    );
  }

  function renderPanelBody() {
    return (
      <div className="space-y-5">
        {renderWorkflowPanel()}
        {renderConversation()}
        <div ref={bottomRef} />
      </div>
    );
  }

  function renderCitationPreview() {
    if (!citationPreview || !previewCitation) {
      return null;
    }

    if (!isDesktopViewport) {
      return <CitationPreviewModal citation={previewCitation} onClose={() => setCitationPreview(null)} />;
    }

    return (
      <CitationPreviewPortal
        citation={previewCitation}
        anchorElement={citationPreview.anchorElement}
        onClose={() => setCitationPreview(null)}
      />
    );
  }

  if (isDesktopViewport) {
    return (
      <>
        {renderTopKSettingsDialog()}
        {renderCitationPreview()}
        <div className="flex min-h-[78svh] flex-col overflow-hidden rounded-[2rem] border border-slate-200 bg-[linear-gradient(180deg,rgba(249,250,255,0.98),rgba(255,255,255,1))] shadow-[0_24px_60px_rgba(15,23,42,0.12)]">
          <div className="border-b border-slate-200 px-5 py-5 tablet:px-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-[2rem] font-semibold tracking-[-0.03em] text-slate-950">Start Query</h2>
              </div>

              <div className="flex items-center gap-2">{renderTopKSettingsButton()}</div>
            </div>
          </div>

          <div ref={scrollContainerRef} className="min-h-0 flex-1 overflow-y-auto px-5 py-5 tablet:px-6 tablet:max-h-[calc(90svh-20rem)]">
            {renderPanelBody()}
          </div>

          <div className="border-t border-slate-200 bg-white/92 px-5 py-4 backdrop-blur tablet:px-6">
            {renderComposer("scholar-chat-question")}
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      {renderTopKSettingsDialog()}
      {renderCitationPreview()}
      {!isMobileSheetOpen ? (
        <button
          type="button"
          className="fixed bottom-4 left-4 right-4 z-40 rounded-[1.75rem] border border-slate-200 bg-white/96 px-5 py-4 text-left shadow-[0_20px_45px_rgba(15,23,42,0.18)] backdrop-blur"
          aria-label="Open chat assistant"
          onClick={() => setIsMobileSheetOpen(true)}
        >
          <div className="flex items-center justify-between gap-3">
            <span className="truncate text-lg text-slate-400">
              {messages.length > 0 ? "Continue exploring..." : "Ask your scholarship..."}
            </span>
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#4f46e5] text-white shadow-[0_12px_24px_rgba(79,70,229,0.25)]">
              <SendHorizontal className="h-5 w-5" />
            </span>
          </div>
        </button>
      ) : null}

      <MobileSheet open={isMobileSheetOpen} onOpenChange={setIsMobileSheetOpen}>
        <div className="mx-auto mt-3 h-1.5 w-14 rounded-full bg-slate-300" />

        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <DialogPrimitive.Close asChild>
            <button
              type="button"
              aria-label="Close chat assistant"
              className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500"
            >
              <ChevronDown className="h-4 w-4" />
            </button>
          </DialogPrimitive.Close>

          <div className="flex items-center gap-2">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-emerald-500" />
            <span className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-700">
              Curator AI Assistant
            </span>
          </div>

          {renderTopKSettingsButton()}
        </div>

        <div ref={scrollContainerRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-4">{renderPanelBody()}</div>

        <div className="border-t border-slate-200 bg-white/96 px-4 py-4 backdrop-blur">
          {renderComposer("scholar-chat-question-mobile", mobileTextareaRef)}
        </div>
      </MobileSheet>
    </>
  );
}

export function ChatPanel(props: ChatPanelProps) {
  if (props.variant !== "scholar") {
    return <ChatPanelV1 {...props} />;
  }

  return <ScholarChatPanel notebookId={props.notebookId} notebookName={props.notebookName} />;
}

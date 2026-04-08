"use client";

import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";

import { CitationCard } from "@/components/chat/citation-card";
import { MessageBubble, type ChatMessage } from "@/components/chat/message-bubble";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import {
  normalizeChatFailure,
  streamNotebookChat,
  type ChatCitation,
  type ChatFailureState,
  type ChatMetricsEvent,
  type ChatQueryRewriteEvent,
  type ChatRetrievalEvent,
  type ChatStatusEvent,
} from "@/lib/chat-stream";

interface ChatPanelProps {
  notebookId: string;
  notebookName: string;
}

type WorkflowTone = "default" | "active" | "warning" | "blocked" | "success";

const STARTER_PROMPTS = [
  "Summarize the main ideas",
  "Where do the sources disagree?",
  "What evidence supports the key claim?",
];
const transparencySectionClasses =
  "space-y-4 rounded-[1.5rem] border border-slate-200 bg-white/88 p-4 shadow-[0_1px_3px_rgba(15,23,42,0.05)] tablet:rounded-[1.75rem] tablet:p-5";
const transparencyCardClasses =
  "rounded-2xl border border-slate-200 bg-slate-50/70 p-4 shadow-[0_1px_2px_rgba(15,23,42,0.04)]";
const transparencyLabelClasses =
  "font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500";

function createMessageId(prefix: "user" | "assistant") {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function formatCount(count: number, singular: string, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

function formatSeconds(value: number) {
  return `${value.toFixed(2)}s`;
}

function mergeMetrics(
  current: ChatMetricsEvent | null | undefined,
  incoming: ChatMetricsEvent
): ChatMetricsEvent {
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

function formatRewriteStrategy(strategy: string): string {
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

function describeRewrite(rewrite: ChatQueryRewriteEvent): string {
  const searchCount = rewrite.search_queries.length;
  const searchSummary = `${formatCount(
    searchCount,
    "retrieval search",
    "retrieval searches"
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

function getWorkflowCardClasses(tone: WorkflowTone): string {
  switch (tone) {
    case "active":
      return "border-sky-200 bg-sky-50 text-sky-950";
    case "warning":
      return "border-amber-200 bg-amber-50 text-amber-950";
    case "blocked":
      return "border-rose-200 bg-rose-50 text-rose-950";
    case "success":
      return "border-emerald-200 bg-emerald-50 text-emerald-950";
    default:
      return "border-slate-200 bg-slate-50 text-slate-900";
  }
}

export function ChatPanel({ notebookId, notebookName }: ChatPanelProps) {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [chatFailure, setChatFailure] = useState<ChatFailureState | null>(null);
  const [workflowStage, setWorkflowStage] = useState<string>("idle");
  const [workflowStageStartedAt, setWorkflowStageStartedAt] = useState<number | null>(null);
  const [stageNow, setStageNow] = useState<number>(Date.now());
  const [workflowStatus, setWorkflowStatus] = useState(
    "We search this notebook's sources, draft an answer from the evidence, and show citations you can inspect."
  );
  const [isQueryRewriteExpanded, setIsQueryRewriteExpanded] = useState(false);
  const [lastSubmittedQuestion, setLastSubmittedQuestion] = useState<string | null>(null);
  const [activeCitationMessageId, setActiveCitationMessageId] = useState<string | null>(
    null
  );
  const [activeCitationIndex, setActiveCitationIndex] = useState<number | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isStreaming]);

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

  const latestAssistantMessageWithCitations = [...messages]
    .reverse()
    .find((message) => message.role === "assistant" && message.citations.length > 0);
  const latestAssistantMessageWithRetrieval = [...messages]
    .reverse()
    .find(
      (message) =>
        message.role === "assistant" && (message.retrieval?.chunks.length ?? 0) > 0
    );
  const latestAssistantMessageWithMetrics = [...messages]
    .reverse()
    .find((message) => message.role === "assistant" && Boolean(message.metrics));
  const latestAssistantMessageWithQueryRewrite = [...messages]
    .reverse()
    .find(
      (message) =>
        message.role === "assistant" && Boolean(message.queryRewrite?.rewritten)
    );
  const latestCompletedAssistantMessage = [...messages].reverse().find(
    (message) =>
      message.role === "assistant" &&
      !message.guardrail &&
      !message.statusMessage &&
      Boolean(message.content.trim())
  );

  const citationPanelMessage =
    messages.find(
      (message) =>
        message.id === activeCitationMessageId &&
        message.role === "assistant" &&
        message.citations.length > 0
    ) || latestAssistantMessageWithCitations;
  const retrievalPanelMessage =
    messages.find(
      (message) =>
        message.id === activeCitationMessageId &&
        message.role === "assistant" &&
        (message.retrieval?.chunks.length ?? 0) > 0
    ) || latestAssistantMessageWithRetrieval;
  const metricsPanelMessage =
    messages.find(
      (message) =>
        message.id === activeCitationMessageId &&
        message.role === "assistant" &&
        Boolean(message.metrics)
    ) || latestAssistantMessageWithMetrics;
  const queryRewritePanelMessage =
    messages.find(
      (message) =>
        message.id === activeCitationMessageId &&
        message.role === "assistant" &&
        Boolean(message.queryRewrite?.rewritten)
    ) || latestAssistantMessageWithQueryRewrite;

  const citationPanelCitations = citationPanelMessage
    ? [...citationPanelMessage.citations].sort(
        (left, right) => left.citation_index - right.citation_index
      )
    : [];
  const retrievalDiagnostics = retrievalPanelMessage?.retrieval ?? null;
  const retrievalGroups = groupRetrievalChunks(retrievalDiagnostics?.chunks ?? []);
  const chatMetrics = metricsPanelMessage?.metrics ?? null;
  const queryRewrite =
    queryRewritePanelMessage?.queryRewrite?.rewritten
      ? queryRewritePanelMessage.queryRewrite
      : null;
  const liveStageSeconds =
    workflowStageStartedAt !== null ? Math.max(0, (stageNow - workflowStageStartedAt) / 1000) : null;

  const selectedCitation =
    citationPanelCitations.find(
      (citation) =>
        citationPanelMessage?.id === activeCitationMessageId &&
        citation.citation_index === activeCitationIndex
    ) || citationPanelCitations[0] || null;

  const queryEmbeddingDisplay =
    typeof chatMetrics?.query_embedding_seconds === "number"
      ? formatSeconds(chatMetrics.query_embedding_seconds)
      : workflowStage === "embedding_query" && liveStageSeconds !== null
        ? `${liveStageSeconds.toFixed(1)}s...`
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
  const streamDeliveryMessage =
    chatMetrics?.stream_delivery === "single_chunk"
      ? "Provider returned a single final stream chunk."
      : chatMetrics?.stream_delivery === "streaming"
        ? "Provider delivered incremental stream chunks."
        : chatMetrics?.stream_delivery === "no_chunks"
          ? "No LLM deltas were received before finalization."
          : null;

  const workflowCard = chatFailure
    ? ({
        tone: chatFailure.retryable ? "warning" : "blocked",
        title: chatFailure.title,
        message: chatFailure.message,
        hint: chatFailure.hint,
      } satisfies {
        tone: WorkflowTone;
        title: string;
        message: string;
        hint: string | null;
      })
    : isStreaming
      ? ({
          tone: "active",
          title: "Working through notebook sources",
          message: workflowStatus,
          hint: "Answers stay grounded in the sources added to this notebook.",
        } satisfies {
          tone: WorkflowTone;
          title: string;
          message: string;
          hint: string | null;
        })
      : latestCompletedAssistantMessage
        ? ({
            tone: "success",
            title: "Grounded answer ready",
            message:
              latestCompletedAssistantMessage.citations.length > 0
                ? "Review the answer above and inspect the citation panel for supporting evidence."
                : "Review the answer above. Citation details will appear here when the response includes grounded references.",
            hint:
              latestCompletedAssistantMessage.citations.length > 0
                ? latestCompletedAssistantMessage.retrieval
                  ? `Retrieved ${formatCount(
                      latestCompletedAssistantMessage.retrieval.chunk_count,
                      "chunk"
                    )} from ${formatCount(
                      latestCompletedAssistantMessage.retrieval.source_count,
                      "source"
                    )}; cited ${formatCount(
                      latestCompletedAssistantMessage.citations.length,
                      "source"
                    )} in the final answer.`
                  : `This answer cited ${latestCompletedAssistantMessage.citations.length} source${
                      latestCompletedAssistantMessage.citations.length === 1 ? "" : "s"
                    }.`
                : "Ask more specific source-grounded follow-ups if you need a tighter evidence trail.",
          } satisfies {
            tone: WorkflowTone;
            title: string;
            message: string;
            hint: string | null;
          })
        : ({
            tone: "default",
            title: "Notebook-only answers",
            message:
              "We search this notebook's sources, draft an answer from the evidence, and show citations you can inspect.",
            hint: "Use concise, source-focused questions for the best grounded answers.",
          } satisfies {
            tone: WorkflowTone;
            title: string;
            message: string;
            hint: string | null;
          });

  const canRetryLastQuestion =
    Boolean(lastSubmittedQuestion) &&
    Boolean(chatFailure?.retryable) &&
    chatFailure?.code !== "input_not_allowed" &&
    !isStreaming;

  async function submitQuestion(questionInput: string) {
    const question = questionInput.trim();
    if (!question || isStreaming) {
      return;
    }

    const assistantMessageId = createMessageId("assistant");

    setDraft("");
    setChatFailure(null);
    setLastSubmittedQuestion(question);
    setWorkflowStage("embedding_query");
    setWorkflowStageStartedAt(Date.now());
    setStageNow(Date.now());
    setWorkflowStatus("Embedding your question for retrieval");
    setIsQueryRewriteExpanded(false);
    setIsStreaming(true);
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

    const updateAssistantMessage = (updater: (message: ChatMessage) => ChatMessage) => {
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantMessageId ? updater(message) : message
        )
      );
    };

    try {
      await streamNotebookChat({
        notebookId,
        question,
        onStatus: (payload) => {
          const friendlyStatus = formatChatStatus(payload);
          setWorkflowStage(payload.stage);
          setWorkflowStageStartedAt(Date.now());
          setStageNow(Date.now());
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
          setIsQueryRewriteExpanded(false);
          updateAssistantMessage((current) => ({
            ...current,
            queryRewrite: payload,
          }));
        },
        onRetrieval: (payload: ChatRetrievalEvent) => {
          updateAssistantMessage((current) => ({
            ...current,
            retrieval: payload,
          }));
        },
        onCitations: ({ citations }) => {
          updateAssistantMessage((current) => ({
            ...current,
            citations,
          }));
          setActiveCitationMessageId(assistantMessageId);
          setActiveCitationIndex(citations[0]?.citation_index ?? null);
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

  function handleCitationSelect(messageId: string, citationIndex: number) {
    setActiveCitationMessageId(messageId);
    setActiveCitationIndex(citationIndex);
  }

  return (
    <Card className="flex h-full min-h-[68svh] flex-col overflow-hidden border-slate-200 bg-white/92 shadow-[0_18px_45px_rgba(15,23,42,0.08)] desktop:min-h-[72vh]">
      <CardHeader className="gap-4 border-b border-slate-200/80 bg-[linear-gradient(180deg,rgba(248,250,252,0.92),rgba(255,255,255,0.98))]">
        <div className="flex flex-col gap-4 tablet:flex-row tablet:items-start tablet:justify-between">
          <div>
            <CardTitle className="text-2xl">Grounded chat</CardTitle>
            <CardDescription>
              Ask questions against the sources in this notebook.
            </CardDescription>
          </div>

          <div className="w-full rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3 shadow-sm tablet:max-w-[220px]">
            <p className={transparencyLabelClasses}>Notebook scope</p>
            <p className="mt-2 text-sm font-semibold leading-6 text-slate-900">
              Answers stay limited to sources added here.
            </p>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex min-h-0 flex-1 flex-col p-0">
        <div className="flex-1 space-y-4 overflow-y-auto bg-white/50 px-3 py-4 xs:px-4 tablet:px-5 tablet:py-5">
          {messages.length === 0 ? (
            <div className="rounded-[1.5rem] border border-dashed border-slate-300 bg-slate-50/80 p-4 tablet:rounded-[1.75rem] tablet:p-5">
              <p className={transparencyLabelClasses}>Starter prompts</p>
              <p className="mt-3 text-sm font-medium text-slate-900">
                Start with a grounded question
              </p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Ask about themes, compare sources, or request a concise summary for{" "}
                {notebookName}.
              </p>

              <div className="mt-4 flex flex-wrap gap-2">
                {STARTER_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-primary/30 hover:bg-slate-50"
                    onClick={() => setDraft(prompt)}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              activeCitationIndex={
                message.id === citationPanelMessage?.id
                  ? selectedCitation?.citation_index ?? null
                  : null
              }
              onCitationSelect={
                message.role === "assistant"
                  ? (citationIndex) => handleCitationSelect(message.id, citationIndex)
                  : undefined
              }
            />
          ))}

          <div ref={bottomRef} />
        </div>

        <div className="order-3 border-t border-slate-200 bg-slate-50/80 px-3 py-4 xs:px-4 tablet:px-5 desktop:order-2">
          <div className="space-y-6">
            {queryRewrite ? (
              <section className={transparencySectionClasses}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900">Query rewrite</h3>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      {describeRewrite(queryRewrite)}
                    </p>
                  </div>

                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    aria-expanded={isQueryRewriteExpanded}
                    onClick={() => setIsQueryRewriteExpanded((current) => !current)}
                  >
                    {isQueryRewriteExpanded ? "Hide rewrite details" : "Show rewrite details"}
                  </Button>
                </div>

                <div className={transparencyCardClasses}>
                  <div className="flex flex-wrap gap-2">
                    <span className="rounded-full border border-slate-200 bg-white px-3 py-1 font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600">
                      {formatRewriteStrategy(queryRewrite.strategy)}
                    </span>
                    <span className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1 font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-sky-700">
                      {formatCount(queryRewrite.search_queries.length, "search", "searches")}
                    </span>
                  </div>

                  {isQueryRewriteExpanded ? (
                    <div className="mt-4 grid gap-4 tablet:grid-cols-2">
                      <div className="space-y-1.5">
                        <p className={transparencyLabelClasses}>
                          Original query
                        </p>
                        <p className="text-sm leading-6 text-slate-900">
                          {queryRewrite.original_query}
                        </p>
                      </div>

                      <div className="space-y-1.5">
                        <p className={transparencyLabelClasses}>
                          Standalone question
                        </p>
                        <p className="text-sm leading-6 text-slate-900">
                          {queryRewrite.standalone_query}
                        </p>
                      </div>

                      <div className="space-y-1.5 tablet:col-span-2">
                        <p className={transparencyLabelClasses}>
                          Retrieval searches
                        </p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {queryRewrite.search_queries.map((searchQuery) => (
                            <span
                              key={searchQuery}
                              className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700"
                            >
                              {searchQuery}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div className="space-y-1.5 tablet:col-span-2">
                        <p className={transparencyLabelClasses}>
                          Rewrite strategy
                        </p>
                        <p className="text-sm leading-6 text-slate-900">
                          {formatRewriteStrategy(queryRewrite.strategy)}
                        </p>
                      </div>
                    </div>
                  ) : null}
                </div>
              </section>
            ) : null}

            <section className={transparencySectionClasses}>
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Chat timing</h3>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  Query embedding, retrieval, and model delivery timings for the
                  current answer.
                </p>
              </div>

              <div className="grid gap-3 xs:grid-cols-2">
                <div className={transparencyCardClasses}>
                  <p className={transparencyLabelClasses}>Model</p>
                  <p className="mt-2 text-sm font-semibold text-slate-900">
                    {chatMetrics?.model || "Pending"}
                  </p>
                </div>

                <div className={transparencyCardClasses}>
                  <p className={transparencyLabelClasses}>Question Embedding</p>
                  <p className="mt-2 text-sm font-semibold text-slate-900">
                    {queryEmbeddingDisplay}
                  </p>
                </div>

                <div className={transparencyCardClasses}>
                  <p className={transparencyLabelClasses}>Retrieval</p>
                  <p className="mt-2 text-sm font-semibold text-slate-900">
                    {retrievalDisplay}
                  </p>
                </div>

                <div className={transparencyCardClasses}>
                  <p className={transparencyLabelClasses}>First Answer Chunk</p>
                  <p className="mt-2 text-sm font-semibold text-slate-900">
                    {firstChunkDisplay}
                  </p>
                </div>

                <div className={transparencyCardClasses}>
                  <p className={transparencyLabelClasses}>Stream Duration</p>
                  <p className="mt-2 text-sm font-semibold text-slate-900">
                    {typeof chatMetrics?.llm_stream_seconds === "number"
                      ? formatSeconds(chatMetrics.llm_stream_seconds)
                      : workflowStage === "streaming" && liveStageSeconds !== null
                        ? `${liveStageSeconds.toFixed(1)}s...`
                        : "Pending"}
                  </p>
                </div>

                <div className={transparencyCardClasses}>
                  <p className={transparencyLabelClasses}>Stream Chunks</p>
                  <p className="mt-2 text-sm font-semibold text-slate-900">
                    {typeof chatMetrics?.delta_chunks_received === "number"
                      ? String(chatMetrics.delta_chunks_received)
                      : "Pending"}
                  </p>
                </div>
              </div>

              {streamDeliveryMessage ? (
                <div className={transparencyCardClasses}>{streamDeliveryMessage}</div>
              ) : null}
            </section>

            <section className={transparencySectionClasses}>
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Retrieved evidence</h3>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  {retrievalDiagnostics
                    ? `${formatCount(
                        retrievalDiagnostics.chunk_count,
                        "chunk"
                      )} from ${formatCount(
                        retrievalDiagnostics.source_count,
                        "source"
                      )} were selected before answer generation.`
                    : "Retrieved chunk diagnostics will appear here once notebook search finishes."}
                </p>
              </div>

              {retrievalDiagnostics ? (
                <div className="grid gap-3">
                  {retrievalGroups.map((group) => (
                    <div
                      key={group.key}
                      className={transparencyCardClasses}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className={transparencyLabelClasses}>Source</p>
                          <p className="mt-1 text-sm font-semibold text-slate-900">
                            {group.sourceTitle}
                          </p>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {formatCount(group.chunks.length, "chunk")}
                        </p>
                      </div>

                      <div className="mt-3 space-y-2">
                        {group.chunks.map((chunk) => (
                          <div
                            key={`${chunk.chunk_id}-${chunk.citation_index}`}
                            className="rounded-xl border border-slate-200 bg-white/80 px-3 py-3"
                          >
                            <div className="flex flex-col gap-2 xs:flex-row xs:items-start xs:justify-between xs:gap-3">
                              <p className="font-mono text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                                Chunk{" "}
                                {typeof chunk.chunk_index === "number"
                                  ? chunk.chunk_index + 1
                                  : chunk.citation_index}
                              </p>
                              <div className="text-right text-xs text-muted-foreground">
                                {chunk.page ? <p>Page {chunk.page}</p> : null}
                                <p>Score {chunk.score.toFixed(2)}</p>
                              </div>
                            </div>
                            <p className="mt-2 font-mono text-[13px] leading-6 text-slate-700">
                              {chunk.quote}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-white/80 p-4 text-sm text-muted-foreground">
                  Retrieved chunk diagnostics will appear here once notebook search
                  completes.
                </div>
              )}
            </section>

            <section className={transparencySectionClasses}>
              <div>
                <h3 className="text-sm font-semibold text-slate-900">
                  Sources used in this answer
                </h3>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  Select a citation marker to inspect the supporting quote and source
                  details.
                </p>
              </div>

              {selectedCitation && citationPanelMessage ? (
                <>
                  <div className={transparencyCardClasses}>
                    <div className="flex flex-col gap-3 xs:flex-row xs:items-start xs:justify-between xs:gap-4">
                      <div>
                        <p className={transparencyLabelClasses}>
                          Citation [{selectedCitation.citation_index}]
                        </p>
                        <p className="mt-1 text-sm font-semibold text-slate-900">
                          {selectedCitation.source_title}
                        </p>
                      </div>
                      <div className="text-right text-xs text-muted-foreground">
                        {selectedCitation.page ? <p>Page {selectedCitation.page}</p> : null}
                        <p>Score {selectedCitation.score.toFixed(2)}</p>
                      </div>
                    </div>

                    <blockquote className="mt-4 border-l-2 border-amber-300 pl-4 font-mono text-[13px] leading-6 text-slate-700">
                      {selectedCitation.quote}
                    </blockquote>

                    {selectedCitation.content !== selectedCitation.quote ? (
                      <p className="mt-3 text-sm leading-6 text-muted-foreground">
                        {selectedCitation.content}
                      </p>
                    ) : null}
                  </div>

                  <div className="grid gap-2">
                    {citationPanelCitations.map((citation) => (
                      <CitationCard
                        key={`${citation.chunk_id}-${citation.citation_index}`}
                        citation={citation}
                        isActive={citation.citation_index === selectedCitation.citation_index}
                        onSelect={(citationIndex) =>
                          handleCitationSelect(citationPanelMessage.id, citationIndex)
                        }
                      />
                    ))}
                  </div>
                </>
              ) : (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-white/80 p-4 text-sm text-muted-foreground">
                  Cited source details will appear here when an answer includes
                  grounded references.
                </div>
              )}
            </section>
          </div>
        </div>

        <div className="order-2 border-t border-slate-200 bg-background/95 p-4 backdrop-blur tablet:p-5 desktop:order-3">
          <div
            className={`mb-4 rounded-[1.75rem] border px-4 py-4 ${getWorkflowCardClasses(
              workflowCard.tone
            )}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1.5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-current/70">
                  Chat workflow
                </p>
                <p className="text-sm font-semibold">{workflowCard.title}</p>
                <p className="text-sm leading-6">{workflowCard.message}</p>
                {workflowCard.hint ? (
                  <p className="text-xs leading-5 text-current/80">{workflowCard.hint}</p>
                ) : null}
              </div>

              {isStreaming ? <Spinner size="sm" className="mt-1 text-current" /> : null}
            </div>

            {canRetryLastQuestion ? (
              <div className="mt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void submitQuestion(lastSubmittedQuestion ?? "")}
                >
                  Try again
                </Button>
              </div>
            ) : null}
          </div>

          <form className="space-y-3" onSubmit={handleSubmit}>
            <label className="sr-only" htmlFor="chat-question">
              Ask a source-grounded question
            </label>
            <Textarea
              id="chat-question"
              placeholder="Ask a source-grounded question..."
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleTextareaKeyDown}
              disabled={isStreaming}
              className="min-h-[104px] resize-none tablet:min-h-[110px]"
            />

            <div className="flex flex-col gap-3 xs:flex-row xs:items-center xs:justify-between">
              <p className="font-mono text-xs uppercase tracking-[0.12em] text-muted-foreground">
                Enter sends. Shift+Enter inserts a new line.
              </p>
              <Button type="submit" disabled={!draft.trim() || isStreaming} className="w-full xs:w-auto">
                Send
              </Button>
            </div>
          </form>
        </div>
      </CardContent>
    </Card>
  );
}

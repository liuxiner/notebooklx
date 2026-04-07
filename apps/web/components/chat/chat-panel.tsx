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
import { streamNotebookChat } from "@/lib/chat-stream";

interface ChatPanelProps {
  notebookId: string;
  notebookName: string;
}

function createMessageId(prefix: "user" | "assistant") {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function ChatPanel({ notebookId, notebookName }: ChatPanelProps) {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeCitationMessageId, setActiveCitationMessageId] = useState<string | null>(
    null
  );
  const [activeCitationIndex, setActiveCitationIndex] = useState<number | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isStreaming]);

  const latestAssistantMessageWithCitations = [...messages]
    .reverse()
    .find((message) => message.role === "assistant" && message.citations.length > 0);

  const citationPanelMessage =
    messages.find(
      (message) =>
        message.id === activeCitationMessageId &&
        message.role === "assistant" &&
        message.citations.length > 0
    ) || latestAssistantMessageWithCitations;

  const citationPanelCitations = citationPanelMessage
    ? [...citationPanelMessage.citations].sort(
        (left, right) => left.citation_index - right.citation_index
      )
    : [];

  const selectedCitation =
    citationPanelCitations.find(
      (citation) =>
        citationPanelMessage?.id === activeCitationMessageId &&
        citation.citation_index === activeCitationIndex
    ) || citationPanelCitations[0] || null;

  async function handleSubmit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();

    const question = draft.trim();
    if (!question || isStreaming) {
      return;
    }

    const assistantMessageId = createMessageId("assistant");

    setDraft("");
    setErrorMessage(null);
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
        statusMessage: "Searching sources",
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
        onStatus: ({ message }) => {
          updateAssistantMessage((current) => ({
            ...current,
            statusMessage: message,
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
          }));
        },
        onDone: () => {
          updateAssistantMessage((current) => ({
            ...current,
            statusMessage: null,
          }));
        },
      });
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Failed to generate a grounded answer.";

      setErrorMessage(message);
      updateAssistantMessage((current) => ({
        ...current,
        content: message,
        statusMessage: null,
      }));
    } finally {
      setIsStreaming(false);
    }
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
    <Card className="flex h-full min-h-[70vh] flex-col overflow-hidden border-slate-200 bg-card/95 shadow-lg">
      <CardHeader className="border-b bg-slate-50/80">
        <CardTitle className="text-xl">Grounded chat</CardTitle>
        <CardDescription>
          Ask questions against the sources in this notebook.
        </CardDescription>
      </CardHeader>

      <CardContent className="flex min-h-0 flex-1 flex-col p-0">
        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-5 sm:px-5">
          {messages.length === 0 ? (
            <div className="rounded-3xl border border-dashed border-border bg-slate-50/70 p-5">
              <p className="text-sm font-medium text-slate-900">
                Start with a grounded question
              </p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Ask about themes, compare sources, or request a concise summary for{" "}
                {notebookName}.
              </p>
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
                  ? (citationIndex) =>
                      handleCitationSelect(message.id, citationIndex)
                  : undefined
              }
            />
          ))}

          {errorMessage ? (
            <p role="alert" className="text-sm text-destructive">
              {errorMessage}
            </p>
          ) : null}

          <div ref={bottomRef} />
        </div>

        <div className="border-t bg-slate-50/80 px-4 py-4 sm:px-5">
          <div className="space-y-4">
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
                <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
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

                  <blockquote className="mt-4 border-l-2 border-slate-300 pl-4 text-sm leading-6 text-slate-700">
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
          </div>
        </div>

        <div className="border-t bg-background/95 p-4 backdrop-blur sm:p-5">
          {isStreaming ? (
            <div className="mb-3 flex items-center gap-2 text-sm text-muted-foreground">
              <Spinner size="sm" className="text-muted-foreground" />
              <span>Generating answer</span>
            </div>
          ) : null}

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
              className="min-h-[110px] resize-none"
            />

            <div className="flex items-center justify-between gap-3">
              <p className="text-xs text-muted-foreground">
                Enter sends. Shift+Enter inserts a new line.
              </p>
              <Button type="submit" disabled={!draft.trim() || isStreaming}>
                Send
              </Button>
            </div>
          </form>
        </div>
      </CardContent>
    </Card>
  );
}

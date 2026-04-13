import { ApiError } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ChatCitation {
  citation_index: number;
  chunk_id: string;
  source_id?: string | null;
  source_title: string;
  chunk_index?: number | null;
  page: string | null;
  quote: string;
  content: string;
  score: number;
}

export interface ChatStatusEvent {
  stage: string;
  message: string;
}

export interface ChatCitationsEvent {
  citations: ChatCitation[];
  citation_indices: number[];
  missing_citation_indices: number[];
}

export interface ChatRetrievalEvent {
  chunk_count: number;
  source_count: number;
  chunks: ChatCitation[];
}

export interface ChatMetricsEvent {
  model?: string | null;
  query_embedding_seconds?: number | null;
  query_embedding_model?: string | null;
  query_embedding_token_count?: number | null;
  query_embedding_estimated_cost_usd?: number | null;
  query_embedding_requests?: number | null;
  retrieval_seconds?: number | null;
  prepare_seconds?: number | null;
  time_to_first_delta_seconds?: number | null;
  llm_stream_seconds?: number | null;
  delta_chunks_received?: number | null;
  stream_delivery?: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  cached_tokens?: number | null;
  usage_source?: string | null;
  estimated_cost_usd?: number | null;
}

export interface ChatQueryRewriteEvent {
  original_query: string;
  standalone_query: string;
  search_queries: string[];
  strategy: string;
  used_llm: boolean;
  rewritten: boolean;
}

export interface ChatAnswerEvent {
  answer: string;
  raw_answer: string;
}

export interface ChatAnswerDeltaEvent {
  delta: string;
}

export interface ChatDoneEvent {
  status: string;
}

export interface ChatErrorEvent {
  error: string;
  message: string;
  title?: string;
  hint?: string | null;
  retryable?: boolean;
}

export interface ChatFailureState {
  code: string;
  title: string;
  message: string;
  hint: string | null;
  retryable: boolean;
}

interface StreamNotebookChatOptions {
  notebookId: string;
  question: string;
  topK?: number;
  signal?: AbortSignal;
  onStatus?: (payload: ChatStatusEvent) => void;
  onMetrics?: (payload: ChatMetricsEvent) => void;
  onQueryRewrite?: (payload: ChatQueryRewriteEvent) => void;
  onRetrieval?: (payload: ChatRetrievalEvent) => void;
  onCitations?: (payload: ChatCitationsEvent) => void;
  onAnswerDelta?: (payload: ChatAnswerDeltaEvent) => void;
  onAnswer?: (payload: ChatAnswerEvent) => void;
  onDone?: (payload: ChatDoneEvent) => void;
}

interface ParsedSseEvent {
  event: string;
  data: unknown;
}

const SSE_EVENT_DELIMITER = /\r?\n\r?\n/;
const DEFAULT_CHAT_FAILURE: ChatFailureState = {
  code: "chat_failed",
  title: "Chat could not complete",
  message: "Failed to generate a grounded answer.",
  hint: "Try again in a moment.",
  retryable: true,
};

function isChatErrorPayload(value: unknown): value is Partial<ChatErrorEvent> {
  if (!value || typeof value !== "object") {
    return false;
  }

  return (
    typeof (value as Record<string, unknown>).message === "string" ||
    typeof (value as Record<string, unknown>).error === "string" ||
    typeof (value as Record<string, unknown>).title === "string"
  );
}

export class ChatStreamError extends Error {
  code: string;
  title: string;
  hint: string | null;
  retryable: boolean;

  constructor(payload: ChatErrorEvent) {
    super(payload.message || DEFAULT_CHAT_FAILURE.message);
    this.name = "ChatStreamError";
    this.code = payload.error || DEFAULT_CHAT_FAILURE.code;
    this.title = payload.title || DEFAULT_CHAT_FAILURE.title;
    this.hint = payload.hint ?? DEFAULT_CHAT_FAILURE.hint;
    this.retryable = payload.retryable ?? DEFAULT_CHAT_FAILURE.retryable;
  }
}

export function normalizeChatFailure(error: unknown): ChatFailureState {
  if (error instanceof ChatStreamError) {
    return {
      code: error.code,
      title: error.title,
      message: error.message,
      hint: error.hint,
      retryable: error.retryable,
    };
  }

  if (isChatErrorPayload(error)) {
    return {
      code:
        typeof error.error === "string" && error.error.trim()
          ? error.error
          : DEFAULT_CHAT_FAILURE.code,
      title:
        typeof error.title === "string" && error.title.trim()
          ? error.title
          : DEFAULT_CHAT_FAILURE.title,
      message:
        typeof error.message === "string" && error.message.trim()
          ? error.message
          : DEFAULT_CHAT_FAILURE.message,
      hint: typeof error.hint === "string" ? error.hint : DEFAULT_CHAT_FAILURE.hint,
      retryable:
        typeof error.retryable === "boolean"
          ? error.retryable
          : DEFAULT_CHAT_FAILURE.retryable,
    };
  }

  if (error instanceof ApiError) {
    if (error.status === 404) {
      return {
        code: "notebook_unavailable",
        title: "Notebook unavailable",
        message: "This notebook is no longer available for chat.",
        hint: "Reload the page or reopen the notebook list.",
        retryable: false,
      };
    }

    if (error.status === 503) {
      return {
        code: "ai_unavailable",
        title: "AI service unavailable",
        message: "This environment is not ready to generate notebook answers right now.",
        hint: "Check the model configuration and try again.",
        retryable: false,
      };
    }
  }

  if (error instanceof Error && error.message.trim()) {
    return {
      ...DEFAULT_CHAT_FAILURE,
      message: error.message,
    };
  }

  return DEFAULT_CHAT_FAILURE;
}

function parseEventBlock(block: string): ParsedSseEvent | null {
  const lines = block.split(/\r?\n/);
  let event = "message";
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
      continue;
    }

    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  if (!dataLines.length) {
    return null;
  }

  const rawPayload = dataLines.join("\n");

  try {
    return {
      event,
      data: JSON.parse(rawPayload),
    };
  } catch {
    return {
      event,
      data: rawPayload,
    };
  }
}

async function buildApiError(response: Response): Promise<ApiError> {
  const payload = await response.json().catch(() => ({}));
  const message =
    payload.message ||
    payload.detail?.message ||
    payload.detail ||
    `HTTP error! status: ${response.status}`;

  return new ApiError(response.status, message);
}

export async function streamNotebookChat({
  notebookId,
  question,
  topK = 5,
  signal,
  onStatus,
  onMetrics,
  onQueryRewrite,
  onRetrieval,
  onCitations,
  onAnswerDelta,
  onAnswer,
  onDone,
}: StreamNotebookChatOptions): Promise<void> {
  const response = await fetch(`${API_URL}/api/notebooks/${notebookId}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      question,
      top_k: topK,
    }),
    signal,
  });

  if (!response.ok) {
    throw await buildApiError(response);
  }

  if (!response.body) {
    throw new Error("Streaming response body is unavailable.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatch = (parsedEvent: ParsedSseEvent | null) => {
    if (!parsedEvent) {
      return;
    }

    switch (parsedEvent.event) {
      case "status":
        onStatus?.(parsedEvent.data as ChatStatusEvent);
        break;
      case "metrics":
        onMetrics?.(parsedEvent.data as ChatMetricsEvent);
        break;
      case "query_rewrite":
        onQueryRewrite?.(parsedEvent.data as ChatQueryRewriteEvent);
        break;
      case "retrieval":
        onRetrieval?.(parsedEvent.data as ChatRetrievalEvent);
        break;
      case "citations":
        onCitations?.(parsedEvent.data as ChatCitationsEvent);
        break;
      case "answer_delta":
        onAnswerDelta?.(parsedEvent.data as ChatAnswerDeltaEvent);
        break;
      case "answer":
        onAnswer?.(parsedEvent.data as ChatAnswerEvent);
        break;
      case "done":
        onDone?.(parsedEvent.data as ChatDoneEvent);
        break;
      case "error": {
        const payload = parsedEvent.data as ChatErrorEvent;
        throw new ChatStreamError(payload);
      }
      default:
        break;
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

    const segments = buffer.split(SSE_EVENT_DELIMITER);
    buffer = segments.pop() || "";

    for (const segment of segments) {
      dispatch(parseEventBlock(segment));
    }

    if (done) {
      break;
    }
  }

  if (buffer.trim()) {
    dispatch(parseEventBlock(buffer.trim()));
  }
}

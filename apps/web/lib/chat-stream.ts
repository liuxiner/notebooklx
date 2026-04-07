import { ApiError } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ChatCitation {
  citation_index: number;
  chunk_id: string;
  source_title: string;
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

interface ChatErrorEvent {
  error: string;
  message: string;
}

interface StreamNotebookChatOptions {
  notebookId: string;
  question: string;
  topK?: number;
  signal?: AbortSignal;
  onStatus?: (payload: ChatStatusEvent) => void;
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
        throw new Error(payload.message || "The chat stream failed.");
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

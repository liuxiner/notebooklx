import { TextDecoder } from "util";

import { streamNotebookChat } from "./chat-stream";

describe("streamNotebookChat", () => {
  beforeAll(() => {
    (
      globalThis as typeof globalThis & { TextDecoder: typeof globalThis.TextDecoder }
    ).TextDecoder = TextDecoder as typeof globalThis.TextDecoder;
  });

  afterEach(() => {
    jest.restoreAllMocks();
    delete (globalThis as typeof globalThis & { fetch?: unknown }).fetch;
  });

  it("dispatches CRLF-delimited SSE frames before the stream completes", async () => {
    const onStatus = jest.fn();
    const onMetrics = jest.fn();
    const onRetrieval = jest.fn();
    let resolvePendingRead:
      | ((result: ReadableStreamReadResult<Uint8Array>) => void)
      | undefined;

    const reader = {
      read: jest
        .fn()
        .mockResolvedValueOnce({
          done: false,
          value: new Uint8Array(
            Buffer.from(
              'event: status\r\ndata: {"stage":"generating","message":"Generating grounded answer"}\r\n\r\n'
            )
          ),
        })
        .mockResolvedValueOnce({
          done: false,
          value: new Uint8Array(
            Buffer.from(
              'event: metrics\r\ndata: {"model":"glm-4.7","query_embedding_seconds":6.41,"retrieval_seconds":0.16,"prepare_seconds":6.57}\r\n\r\n'
            )
          ),
        })
        .mockResolvedValueOnce({
          done: false,
          value: new Uint8Array(
            Buffer.from(
              'event: retrieval\r\ndata: {"chunk_count":2,"source_count":1,"chunks":[{"citation_index":1,"chunk_id":"chunk-1","source_id":"source-1","source_title":"Alpha Guide","chunk_index":0,"page":"12","quote":"Alpha quote","content":"Alpha content","score":0.91},{"citation_index":2,"chunk_id":"chunk-2","source_id":"source-1","source_title":"Alpha Guide","chunk_index":1,"page":"13","quote":"Beta quote","content":"Beta content","score":0.82}]}\r\n\r\n'
            )
          ),
        })
        .mockImplementationOnce(
          () =>
            new Promise<ReadableStreamReadResult<Uint8Array>>((resolve) => {
              resolvePendingRead = resolve;
            })
        ),
    };

    (globalThis as typeof globalThis & { fetch: jest.Mock }).fetch = jest
      .fn()
      .mockResolvedValue({
        ok: true,
        body: {
          getReader: () => reader,
        },
      } as Response);

    const streamPromise = streamNotebookChat({
      notebookId: "notebook-123",
      question: "What is Alpha?",
      onStatus,
      onMetrics,
      onRetrieval,
    });

    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(onStatus).toHaveBeenCalledWith({
      stage: "generating",
      message: "Generating grounded answer",
    });
    expect(onMetrics).toHaveBeenCalledWith({
      model: "glm-4.7",
      query_embedding_seconds: 6.41,
      retrieval_seconds: 0.16,
      prepare_seconds: 6.57,
    });
    expect(onRetrieval).toHaveBeenCalledWith({
      chunk_count: 2,
      source_count: 1,
      chunks: [
        {
          citation_index: 1,
          chunk_id: "chunk-1",
          source_id: "source-1",
          source_title: "Alpha Guide",
          chunk_index: 0,
          page: "12",
          quote: "Alpha quote",
          content: "Alpha content",
          score: 0.91,
        },
        {
          citation_index: 2,
          chunk_id: "chunk-2",
          source_id: "source-1",
          source_title: "Alpha Guide",
          chunk_index: 1,
          page: "13",
          quote: "Beta quote",
          content: "Beta content",
          score: 0.82,
        },
      ],
    });

    resolvePendingRead?.({ done: true, value: undefined });
    await streamPromise;
  });

  it("throws a typed chat error for structured SSE error payloads", async () => {
    const reader = {
      read: jest
        .fn()
        .mockResolvedValueOnce({
          done: false,
          value: new Uint8Array(
            Buffer.from(
              'event: error\r\ndata: {"error":"quota_exhausted","title":"AI credits unavailable","message":"The AI provider account has no available balance or package quota.","hint":"Recharge and try again.","retryable":false}\r\n\r\n'
            )
          ),
        })
        .mockResolvedValueOnce({
          done: true,
          value: undefined,
        }),
    };

    (globalThis as typeof globalThis & { fetch: jest.Mock }).fetch = jest
      .fn()
      .mockResolvedValue({
        ok: true,
        body: {
          getReader: () => reader,
        },
      } as Response);

    await expect(
      streamNotebookChat({
        notebookId: "notebook-123",
        question: "What is Alpha?",
      })
    ).rejects.toMatchObject({
      name: "ChatStreamError",
      code: "quota_exhausted",
      title: "AI credits unavailable",
      message: "The AI provider account has no available balance or package quota.",
      hint: "Recharge and try again.",
      retryable: false,
    });
  });
});

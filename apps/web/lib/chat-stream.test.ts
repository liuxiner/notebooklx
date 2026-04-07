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
    });

    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(onStatus).toHaveBeenCalledWith({
      stage: "generating",
      message: "Generating grounded answer",
    });

    resolvePendingRead?.({ done: true, value: undefined });
    await streamPromise;
  });
});

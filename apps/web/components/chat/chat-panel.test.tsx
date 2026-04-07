import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ChatPanel } from "./chat-panel";
import { streamNotebookChat } from "@/lib/chat-stream";

jest.mock("@/lib/chat-stream", () => {
  const actual = jest.requireActual("@/lib/chat-stream");
  return {
    ...actual,
    streamNotebookChat: jest.fn(),
  };
});

describe("ChatPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders a notebook-friendly empty workflow state", () => {
    render(<ChatPanel notebookId="notebook-123" notebookName="Deep Research Notes" />);

    expect(screen.getByText("Grounded chat")).toBeInTheDocument();
    expect(screen.getByText("Notebook-only answers")).toBeInTheDocument();
    expect(
      screen.getByText(
        "We search this notebook's sources, draft an answer from the evidence, and show citations you can inspect."
      )
    ).toBeInTheDocument();
    expect(screen.getByText("Summarize the main ideas")).toBeInTheDocument();
    expect(screen.getByText("Where do the sources disagree?")).toBeInTheDocument();
    expect(screen.getByText("What evidence supports the key claim?")).toBeInTheDocument();
  });

  it("shows a friendly quota guardrail instead of leaking provider error text", async () => {
    const user = userEvent.setup();

    (streamNotebookChat as jest.Mock).mockRejectedValueOnce(
      Object.assign(
        new Error(
          "openai.RateLimitError: Error code: 429 - {'error': {'code': '1113', 'message': '余额不足或无可用资源包,请充值。'}}"
        ),
        {
          error: "quota_exhausted",
          title: "AI credits unavailable",
          message: "The AI provider account has no available balance or package quota.",
          hint: "Recharge the provider account or switch to another configured model, then try again.",
          retryable: false,
        }
      )
    );

    render(<ChatPanel notebookId="notebook-123" notebookName="Deep Research Notes" />);

    await act(async () => {
      await user.type(
        screen.getByPlaceholderText("Ask a source-grounded question..."),
        "What is the launch risk?"
      );
      await user.click(screen.getByRole("button", { name: "Send" }));
    });

    expect(await screen.findAllByText("AI credits unavailable")).toHaveLength(2);
    expect(
      screen.getAllByText("The AI provider account has no available balance or package quota.")
    ).toHaveLength(2);
    expect(
      screen.getAllByText(
        "Recharge the provider account or switch to another configured model, then try again."
      )
    ).toHaveLength(2);
    expect(screen.queryByText(/RateLimitError/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });

  it("offers a retry action for temporary chat failures", async () => {
    const user = userEvent.setup();

    (streamNotebookChat as jest.Mock)
      .mockRejectedValueOnce(
        Object.assign(new Error("Gateway timeout"), {
          error: "temporary_unavailable",
          title: "Model temporarily unavailable",
          message:
            "The model did not complete this request. Your notebook data is unchanged.",
          hint: "Wait a moment and try again.",
          retryable: true,
        })
      )
      .mockImplementationOnce(async ({ onStatus, onAnswer, onDone }) => {
        onStatus?.({
          stage: "embedding_query",
          message: "Embedding your question for notebook retrieval",
        });
        onAnswer?.({
          answer: "The sources describe a phased launch.",
          raw_answer: "The sources describe a phased launch.",
        });
        onDone?.({ status: "complete" });
      });

    render(<ChatPanel notebookId="notebook-123" notebookName="Deep Research Notes" />);

    await act(async () => {
      await user.type(
        screen.getByPlaceholderText("Ask a source-grounded question..."),
        "What is the launch plan?"
      );
      await user.click(screen.getByRole("button", { name: "Send" }));
    });

    expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Try again" }));
    });

    await waitFor(() => {
      expect(streamNotebookChat).toHaveBeenCalledTimes(2);
    });
    expect(streamNotebookChat).toHaveBeenLastCalledWith(
      expect.objectContaining({
        notebookId: "notebook-123",
        question: "What is the launch plan?",
      })
    );
    expect(await screen.findByText("The sources describe a phased launch.")).toBeInTheDocument();
  });

  it("shows streamed assistant text alongside retrieval diagnostics before the answer finalizes", async () => {
    const user = userEvent.setup();
    let resolveStream: (() => void) | undefined;

    (streamNotebookChat as jest.Mock).mockImplementationOnce(
      async ({
        onStatus,
        onMetrics,
        onRetrieval,
        onAnswerDelta,
        onAnswer,
        onDone,
      }) => {
        onStatus?.({
          stage: "embedding_query",
          message: "Embedding your question for notebook retrieval",
        });
        onMetrics?.({
          model: "glm-4.7",
          query_embedding_seconds: 6.41,
          retrieval_seconds: 0.16,
          prepare_seconds: 6.57,
        });
        onRetrieval?.({
          chunk_count: 2,
          source_count: 2,
          chunks: [
            {
              citation_index: 1,
              chunk_id: "chunk-1",
              source_id: "source-1",
              source_title: "Alpha Guide",
              chunk_index: 0,
              page: "12",
              quote: "Alpha launches in phases.",
              content: "Alpha launches in phases with an initial pilot.",
              score: 0.95,
            },
            {
              citation_index: 2,
              chunk_id: "chunk-2",
              source_id: "source-2",
              source_title: "Risk Memo",
              chunk_index: 4,
              page: "3",
              quote: "Logistics remains the main risk.",
              content: "Logistics remains the main risk until the second wave.",
              score: 0.82,
            },
          ],
        });
        onStatus?.({
          stage: "waiting_model",
          message: "Waiting for the model to send the first answer chunk",
        });
        onAnswerDelta?.({ delta: "Alpha launches in phases" });

        await new Promise<void>((resolve) => {
          resolveStream = () => {
            onMetrics?.({
              time_to_first_delta_seconds: 50.86,
              llm_stream_seconds: 50.86,
              delta_chunks_received: 1,
              stream_delivery: "single_chunk",
            });
            onAnswer?.({
              answer: "Alpha launches in phases [1].",
              raw_answer: "Alpha launches in phases [1].",
            });
            onDone?.({ status: "complete" });
            resolve();
          };
        });
      }
    );

    render(<ChatPanel notebookId="notebook-123" notebookName="Deep Research Notes" />);

    await act(async () => {
      await user.type(
        screen.getByPlaceholderText("Ask a source-grounded question..."),
        "What is the rollout plan?"
      );
      await user.click(screen.getByRole("button", { name: "Send" }));
    });

    expect(
      screen.getAllByText("Waiting for the first answer chunk from the model").length
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Alpha launches in phases")).toBeInTheDocument();
    expect(screen.getByText("Chat timing")).toBeInTheDocument();
    expect(screen.getByText("glm-4.7")).toBeInTheDocument();
    expect(screen.getByText("6.41s")).toBeInTheDocument();
    expect(screen.getByText("0.16s")).toBeInTheDocument();
    expect(screen.getByText("Retrieved evidence")).toBeInTheDocument();
    expect(screen.getByText("2 chunks from 2 sources were selected before answer generation.")).toBeInTheDocument();
    expect(screen.getByText("Alpha Guide")).toBeInTheDocument();
    expect(screen.getByText("Risk Memo")).toBeInTheDocument();
    expect(screen.getByText("Chunk 1")).toBeInTheDocument();
    expect(screen.getByText("Chunk 5")).toBeInTheDocument();

    await act(async () => {
      resolveStream?.();
    });

    expect(
      (
        await screen.findAllByText((_, element) => {
          return element?.textContent === "Alpha launches in phases [1].";
        })
      ).length
    ).toBeGreaterThanOrEqual(1);
    expect((await screen.findAllByText("50.86s")).length).toBeGreaterThanOrEqual(1);
    expect(await screen.findByText("Provider returned a single final stream chunk.")).toBeInTheDocument();
  });
});

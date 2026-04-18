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

  it("defaults retrieval top-k to 5 and passes it into chat streaming", async () => {
    const user = userEvent.setup();

    (streamNotebookChat as jest.Mock).mockResolvedValueOnce(undefined);

    render(<ChatPanel notebookId="notebook-123" notebookName="Deep Research Notes" />);

    expect(screen.getByLabelText("Top-K")).toHaveValue(5);

    await act(async () => {
      await user.type(
        screen.getByPlaceholderText("Ask a source-grounded question..."),
        "What evidence supports the launch?"
      );
      await user.click(screen.getByRole("button", { name: "Send" }));
    });

    expect(streamNotebookChat).toHaveBeenCalledWith(
      expect.objectContaining({
        notebookId: "notebook-123",
        question: "What evidence supports the launch?",
        topK: 5,
      })
    );
  });

  it("lets the user change retrieval top-k before sending a question", async () => {
    const user = userEvent.setup();

    (streamNotebookChat as jest.Mock).mockResolvedValueOnce(undefined);

    render(<ChatPanel notebookId="notebook-123" notebookName="Deep Research Notes" />);

    const topKInput = screen.getByLabelText("Top-K");

    await act(async () => {
      await user.clear(topKInput);
      await user.type(topKInput, "8");
      await user.type(
        screen.getByPlaceholderText("Ask a source-grounded question..."),
        "Which sections matter most?"
      );
      await user.click(screen.getByRole("button", { name: "Send" }));
    });

    expect(streamNotebookChat).toHaveBeenCalledWith(
      expect.objectContaining({
        notebookId: "notebook-123",
        question: "Which sections matter most?",
        topK: 8,
      })
    );
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

    expect((await screen.findAllByText("AI credits unavailable")).length).toBeGreaterThanOrEqual(2);
    expect(
      screen.getAllByText("The AI provider account has no available balance or package quota.")
    ).toHaveLength(3);
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
    expect(
      (await screen.findAllByText("The sources describe a phased launch.")).length
    ).toBeGreaterThanOrEqual(1);
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
          query_embedding_model: "embedding-3",
          query_embedding_token_count: 18,
          query_embedding_estimated_cost_usd: 0.00036,
          query_embedding_requests: 2,
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
              prompt_tokens: 1_245,
              completion_tokens: 218,
              total_tokens: 1_463,
              cached_tokens: 120,
              usage_source: "provider",
              estimated_cost_usd: 0.01234,
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
    expect(screen.getAllByText("Alpha launches in phases").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Chat timing & usage")).toBeInTheDocument();
    expect(screen.getByText("glm-4.7")).toBeInTheDocument();
    expect(screen.getAllByText("6.41s").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("embedding-3")).toBeInTheDocument();
    expect(screen.getByText("18")).toBeInTheDocument();
    expect(screen.getByText("$0.00036")).toBeInTheDocument();
    expect(screen.getAllByText("0.16s").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Event timeline")).toBeInTheDocument();
    expect(screen.getAllByText("Status update").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Metrics update").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Retrieval event")).toBeInTheDocument();
    expect(screen.getByText("Stream delta")).toBeInTheDocument();
    expect(
      screen.getByText(
        (_, element) => element?.textContent?.includes('"stage": "embedding_query"') ?? false,
        { selector: "pre" }
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        (_, element) =>
          element?.textContent?.includes('"query_embedding_model": "embedding-3"') ?? false,
        { selector: "pre" }
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        (_, element) => element?.textContent?.includes('"source_title": "Alpha Guide"') ?? false,
        { selector: "pre" }
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        (_, element) => element?.textContent?.includes('"delta": "Alpha launches in phases"') ?? false,
        { selector: "pre" }
      )
    ).toBeInTheDocument();
    expect(screen.getByText("Retrieved evidence")).toBeInTheDocument();
    expect(screen.getByText("2 chunks from 2 sources were selected before answer generation.")).toBeInTheDocument();
    expect(screen.getByText("Alpha Guide")).toBeInTheDocument();
    expect(screen.getByText("Risk Memo")).toBeInTheDocument();
    expect(screen.getByText("Chunk 1")).toBeInTheDocument();
    expect(screen.getByText("Chunk 5")).toBeInTheDocument();
    expect(
      screen.getByText("Query embedding totals cover 2 retrieval queries.")
    ).toBeInTheDocument();

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
    expect(await screen.findByText("Workflow complete")).toBeInTheDocument();
    expect(await screen.findByText("Provider returned a single final stream chunk.")).toBeInTheDocument();
    expect(
      await screen.findByText(
        (_, element) =>
          element?.textContent?.includes('"stream_delivery": "single_chunk"') ?? false,
        { selector: "pre" }
      )
    ).toBeInTheDocument();
    expect(
      await screen.findByText(
        (_, element) => element?.textContent?.includes('"status": "complete"') ?? false,
        { selector: "pre" }
      )
    ).toBeInTheDocument();
    expect(await screen.findByText("1,245")).toBeInTheDocument();
    expect(await screen.findByText("218")).toBeInTheDocument();
    expect(await screen.findByText("1,463")).toBeInTheDocument();
    expect(await screen.findByText("$0.0123")).toBeInTheDocument();
    expect(
      await screen.findByText("Token usage was reported directly by the model provider.")
    ).toBeInTheDocument();
    expect(
      await screen.findByText("Provider reported 120 cached prompt tokens.")
    ).toBeInTheDocument();
  });

  it("renders scholar workflow first and keeps advanced diagnostics behind settings", async () => {
    const user = userEvent.setup();

    render(
      <ChatPanel
        notebookId="notebook-123"
        notebookName="Deep Research Notes"
        variant="scholar"
      />
    );

    expect(screen.getByText("Scholar Query")).toBeInTheDocument();
    expect(screen.getByText("Curator AI v4.2 active")).toBeInTheDocument();
    expect(screen.getByText("Process workflow")).toBeInTheDocument();
    expect(screen.getByText("Event timeline")).toBeInTheDocument();
    expect(screen.queryByText("Chat timing & usage")).not.toBeInTheDocument();

    await act(async () => {
      await user.click(
        screen.getByRole("button", { name: "Toggle advanced diagnostics" })
      );
    });

    expect(screen.getByText("Chat timing & usage")).toBeInTheDocument();
  });

  it("keeps rewritten-query transparency collapsed until the user expands it", async () => {
    const user = userEvent.setup();

    (streamNotebookChat as jest.Mock).mockImplementationOnce(
      async ({ onStatus, onQueryRewrite, onAnswer, onDone }) => {
        onStatus?.({
          stage: "embedding_query",
          message: "Embedding your question for notebook retrieval",
        });
        onQueryRewrite?.({
          original_query: "What are the risks?",
          standalone_query: "What are the NotebookLX project risks described in the documents?",
          search_queries: ["NotebookLX project risks", "NotebookLX architecture risks"],
          strategy: "keyword_enrichment",
          used_llm: true,
          rewritten: true,
        });
        onAnswer?.({
          answer: "The documents highlight execution and architecture risks.",
          raw_answer: "The documents highlight execution and architecture risks.",
        });
        onDone?.({ status: "complete" });
      }
    );

    render(<ChatPanel notebookId="notebook-123" notebookName="Deep Research Notes" />);

    await act(async () => {
      await user.type(
        screen.getByPlaceholderText("Ask a source-grounded question..."),
        "What are the risks?"
      );
      await user.click(screen.getByRole("button", { name: "Send" }));
    });

    expect((await screen.findAllByText("Query rewrite")).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("button", { name: "Show rewrite details" })).toBeInTheDocument();
    expect(screen.queryByText("Original query")).not.toBeInTheDocument();
    expect(screen.queryByText("Retrieval searches")).not.toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Show rewrite details" }));
    });

    expect(screen.getByText("Original query")).toBeInTheDocument();
    expect(screen.getAllByText("What are the risks?").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Standalone question")).toBeInTheDocument();
    expect(
      screen.getByText("What are the NotebookLX project risks described in the documents?")
    ).toBeInTheDocument();
    expect(screen.getByText("Retrieval searches")).toBeInTheDocument();
    expect(screen.getByText("NotebookLX project risks")).toBeInTheDocument();
    expect(screen.getByText("NotebookLX architecture risks")).toBeInTheDocument();
    expect(screen.getByText("Rewrite strategy")).toBeInTheDocument();
    expect(screen.getAllByText("Keyword enrichment").length).toBeGreaterThanOrEqual(2);
  });

  it("hides rewritten-query transparency when the query did not change", async () => {
    const user = userEvent.setup();

    (streamNotebookChat as jest.Mock).mockImplementationOnce(
      async ({ onStatus, onQueryRewrite, onAnswer, onDone }) => {
        onStatus?.({
          stage: "embedding_query",
          message: "Embedding your question for notebook retrieval",
        });
        onQueryRewrite?.({
          original_query: "Explain semantic chunking in NotebookLX",
          standalone_query: "Explain semantic chunking in NotebookLX",
          search_queries: ["Explain semantic chunking in NotebookLX"],
          strategy: "no_rewrite",
          used_llm: false,
          rewritten: false,
        });
        onAnswer?.({
          answer: "The sources describe semantic chunking as context-preserving splitting.",
          raw_answer: "The sources describe semantic chunking as context-preserving splitting.",
        });
        onDone?.({ status: "complete" });
      }
    );

    render(<ChatPanel notebookId="notebook-123" notebookName="Deep Research Notes" />);

    await act(async () => {
      await user.type(
        screen.getByPlaceholderText("Ask a source-grounded question..."),
        "Explain semantic chunking in NotebookLX"
      );
      await user.click(screen.getByRole("button", { name: "Send" }));
    });

    expect(
      (
        await screen.findAllByText(
          "The sources describe semantic chunking as context-preserving splitting."
        )
      ).length
    ).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("Query rewrite")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show rewrite details" })).not.toBeInTheDocument();
  });
});

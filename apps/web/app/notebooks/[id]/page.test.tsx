import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import NotebookDetailPage from "./page";
import { notebooksApi, type Notebook } from "@/lib/api";
import { sourcesApi } from "@/lib/api";
import { streamNotebookChat } from "@/lib/chat-stream";

jest.mock("next/navigation", () => ({
  useParams: () => ({ id: "notebook-123" }),
  useRouter: () => ({
    push: jest.fn(),
  }),
}));

jest.mock("@/lib/api", () => ({
  notebooksApi: {
    get: jest.fn(),
  },
  sourcesApi: {
    list: jest.fn(),
    getStatus: jest.fn(),
  },
}));

jest.mock("@/lib/chat-stream", () => ({
  streamNotebookChat: jest.fn(),
}));

const mockNotebook: Notebook = {
  id: "notebook-123",
  user_id: "user-1",
  name: "Deep Research Notes",
  description: "Sources for the Alpha launch analysis.",
  created_at: "2026-04-07T12:00:00Z",
  updated_at: "2026-04-07T12:00:00Z",
};

const mockSources = [
  {
    id: "source-1",
    source_type: "pdf",
    title: "Alpha Research Dossier",
    status: "processing",
    file_size: 1024,
    created_at: "2026-04-07T12:00:00Z",
    updated_at: "2026-04-07T12:00:00Z",
  },
  {
    id: "source-2",
    source_type: "url",
    title: "Launch Risks Memo",
    status: "failed",
    file_size: null,
    created_at: "2026-04-06T12:00:00Z",
    updated_at: "2026-04-06T12:00:00Z",
  },
  {
    id: "source-3",
    source_type: "text",
    title: "Queued Interview Notes",
    status: "pending",
    file_size: null,
    created_at: "2026-04-05T12:00:00Z",
    updated_at: "2026-04-05T12:00:00Z",
  },
  {
    id: "source-4",
    source_type: "gdocs",
    title: "Customer Insights Brief",
    status: "ready",
    file_size: null,
    created_at: "2026-04-04T12:00:00Z",
    updated_at: "2026-04-04T12:00:00Z",
  },
];

describe("NotebookDetailPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (notebooksApi.get as jest.Mock).mockResolvedValue(mockNotebook);
    (sourcesApi.list as jest.Mock).mockResolvedValue(mockSources);
    (sourcesApi.getStatus as jest.Mock).mockImplementation((sourceId: string) => {
      if (sourceId === "source-1") {
        return Promise.resolve({
          source_id: sourceId,
          status: "processing",
          progress: {
            current_step: "embedding",
            percentage: 70,
            embedded_chunks: 7,
            total_chunks: 10,
          },
          error_message: null,
        });
      }

      if (sourceId === "source-2") {
        return Promise.resolve({
          source_id: sourceId,
          status: "failed",
          progress: null,
          error_message: "Could not parse the source content.",
        });
      }

      if (sourceId === "source-3") {
        return Promise.resolve({
          source_id: sourceId,
          status: "pending",
          progress: {
            message: "Queued for ingestion",
          },
          error_message: null,
        });
      }

      return Promise.resolve({
        source_id: sourceId,
        status: "ready",
        progress: null,
        error_message: null,
      });
    });
  });

  it("renders the notebook workspace with a dedicated chat panel", async () => {
    render(<NotebookDetailPage />);

    expect(await screen.findByText("Deep Research Notes")).toBeInTheDocument();
    const sourcesHeading = await screen.findByText("Notebook sources");
    const chatHeading = screen.getByText("Grounded chat");
    expect(chatHeading).toBeInTheDocument();
    expect(
      screen.getByText("Ask questions against the sources in this notebook.")
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Ask a source-grounded question...")
    ).toBeInTheDocument();
    expect(chatHeading.compareDocumentPosition(sourcesHeading) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy();
  });

  it("renders notebook sources with status badges, progress details, and reserved sections", async () => {
    render(<NotebookDetailPage />);

    expect(await screen.findByText("Alpha Research Dossier")).toBeInTheDocument();
    expect(screen.getByText("Launch Risks Memo")).toBeInTheDocument();
    expect(screen.getByText("Queued Interview Notes")).toBeInTheDocument();
    expect(screen.getByText("Customer Insights Brief")).toBeInTheDocument();
    expect(screen.getByText("PDF")).toBeInTheDocument();
    expect(screen.getByText("URL")).toBeInTheDocument();
    expect(screen.getByText("TEXT")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(
      screen
        .getAllByText("Pending")
        .some((element) => element.className.includes("bg-slate-100"))
    ).toBe(true);
    expect(screen.getByText("Processing")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Embedding 7 of 10 chunks")).toBeInTheDocument();
    expect(screen.getByText("Queued for ingestion")).toBeInTheDocument();
    expect(screen.getByText("Could not parse the source content.")).toBeInTheDocument();
    expect(screen.getByText("Added Apr 7, 2026")).toBeInTheDocument();
    expect(screen.getByText("Notebook summary")).toBeInTheDocument();
    expect(screen.getByText("Generated assets")).toBeInTheDocument();
  });

  it("shows an empty state when the notebook has no sources", async () => {
    (sourcesApi.list as jest.Mock).mockResolvedValueOnce([]);

    render(<NotebookDetailPage />);

    expect(await screen.findByText("No sources yet")).toBeInTheDocument();
    expect(
      screen.getByText("Add a PDF, pasted text, or URL to start grounding this notebook.")
    ).toBeInTheDocument();
    expect(sourcesApi.getStatus).not.toHaveBeenCalled();
  });

  it("refreshes the notebook source list without leaving the page", async () => {
    const user = userEvent.setup();

    render(<NotebookDetailPage />);

    expect(await screen.findByText("Alpha Research Dossier")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Refresh" }));
    });

    await waitFor(() => {
      expect(sourcesApi.list).toHaveBeenCalledTimes(2);
    });
  });

  it("shows a source loading error and retries in place", async () => {
    const user = userEvent.setup();

    (sourcesApi.list as jest.Mock)
      .mockRejectedValueOnce(new Error("Sources API unavailable"))
      .mockResolvedValueOnce(mockSources);

    render(<NotebookDetailPage />);

    expect(await screen.findByText("Sources API unavailable")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Refresh" }));
    });

    expect(await screen.findByText("Alpha Research Dossier")).toBeInTheDocument();
    expect(sourcesApi.list).toHaveBeenCalledTimes(2);
  });

  it("adds user and assistant messages while the stream is active", async () => {
    const user = userEvent.setup();
    let resolveStream: (() => void) | undefined;

    (streamNotebookChat as jest.Mock).mockImplementation(
      async ({
        onStatus,
        onAnswerDelta,
        onAnswer,
        onDone,
      }: {
        onStatus: (payload: { stage: string; message: string }) => void;
        onAnswerDelta: (payload: { delta: string }) => void;
        onAnswer: (payload: { answer: string; raw_answer: string }) => void;
        onDone: (payload: { status: string }) => void;
      }) => {
        onStatus({
          stage: "embedding_query",
          message: "Embedding your question for notebook retrieval",
        });
        onStatus({
          stage: "waiting_model",
          message: "Waiting for the model to send the first answer chunk",
        });
        onAnswerDelta({ delta: "Alpha launch" });

        await new Promise<void>((resolve) => {
          resolveStream = () => {
            onAnswerDelta({ delta: " preparation is documented in the sources." });
            onAnswer({
              answer: "Alpha launch preparation is documented in the sources.",
              raw_answer: "Alpha launch preparation is documented in the sources.",
            });
            onDone({ status: "complete" });
            resolve();
          };
        });
      }
    );

    render(<NotebookDetailPage />);

    const textarea = await screen.findByPlaceholderText(
      "Ask a source-grounded question..."
    );
    await act(async () => {
      await user.type(textarea, "What do the sources say about Alpha?");
      await user.keyboard("{Enter}");
    });

    expect(
      screen.getByText("What do the sources say about Alpha?")
    ).toBeInTheDocument();
    expect(screen.getByText("Working through notebook sources")).toBeInTheDocument();
    expect(screen.getAllByText("Waiting for the first answer chunk from the model")).toHaveLength(2);
    expect(screen.getByText("Alpha launch")).toBeInTheDocument();

    await act(async () => {
      resolveStream?.();
    });

    await screen.findByText(
      "Alpha launch preparation is documented in the sources."
    );

    expect(streamNotebookChat).toHaveBeenCalledWith(
      expect.objectContaining({
        notebookId: "notebook-123",
        question: "What do the sources say about Alpha?",
      })
    );

    await waitFor(() => {
      expect(screen.getByText("Grounded answer ready")).toBeInTheDocument();
    });
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it("renders clickable citation markers and updates the citation panel", async () => {
    const user = userEvent.setup();

    (streamNotebookChat as jest.Mock).mockImplementation(
      async ({
        onStatus,
        onCitations,
        onAnswer,
        onDone,
      }: {
        onStatus: (payload: { stage: string; message: string }) => void;
        onCitations: (payload: {
          citations: Array<{
            citation_index: number;
            chunk_id: string;
            source_title: string;
            page: string | null;
            quote: string;
            content: string;
            score: number;
          }>;
          citation_indices: number[];
          missing_citation_indices: number[];
        }) => void;
        onAnswer: (payload: { answer: string; raw_answer: string }) => void;
        onDone: (payload: { status: string }) => void;
      }) => {
        onStatus({
          stage: "embedding_query",
          message: "Embedding your question for notebook retrieval",
        });
        onCitations({
          citations: [
            {
              citation_index: 1,
              chunk_id: "chunk-1",
              source_title: "Alpha Guide",
              page: "12",
              quote: "Alpha launch planning starts in Q2.",
              content: "Alpha launch planning starts in Q2 with a research review.",
              score: 0.95,
            },
            {
              citation_index: 2,
              chunk_id: "chunk-2",
              source_title: "Beta Brief",
              page: "4",
              quote: "Beta mitigates the logistics risk.",
              content: "Beta mitigates the logistics risk with phased rollout support.",
              score: 0.82,
            },
          ],
          citation_indices: [1, 2],
          missing_citation_indices: [],
        });
        onAnswer({
          answer:
            "Alpha launch planning starts in Q2 [1] and Beta reduces the logistics risk [2].",
          raw_answer:
            "Alpha launch planning starts in Q2 [1] and Beta reduces the logistics risk [2].",
        });
        onDone({ status: "complete" });
      }
    );

    render(<NotebookDetailPage />);

    const textarea = await screen.findByPlaceholderText(
      "Ask a source-grounded question..."
    );
    await act(async () => {
      await user.type(textarea, "What is the launch plan?");
      await user.click(screen.getByRole("button", { name: "Send" }));
    });

    expect(
      await screen.findByRole("heading", { name: "Sources used in this answer" })
    ).toBeInTheDocument();

    const firstMarker = screen.getByRole("button", { name: "Open citation 1" });
    const secondMarker = screen.getByRole("button", { name: "Open citation 2" });

    expect(firstMarker).toBeInTheDocument();
    expect(secondMarker).toBeInTheDocument();

    expect(screen.getAllByText("Alpha Guide")).toHaveLength(2);
    expect(screen.getAllByText("Beta Brief")).toHaveLength(1);
    expect(screen.getAllByText("Alpha launch planning starts in Q2.")).toHaveLength(2);
    expect(screen.getAllByText("Page 12")).toHaveLength(2);
    expect(screen.getAllByText("Score 0.95")).toHaveLength(2);
    expect(
      screen.getByRole("button", { name: "View citation 1 from Alpha Guide" })
    ).toHaveAttribute("aria-pressed", "true");

    await act(async () => {
      await user.click(secondMarker);
    });

    expect(screen.getAllByText("Beta mitigates the logistics risk.")).toHaveLength(2);
    expect(screen.getAllByText("Page 4")).toHaveLength(2);
    expect(screen.getAllByText("Score 0.82")).toHaveLength(2);
    expect(
      screen.getByRole("button", { name: "View citation 2 from Beta Brief" })
    ).toHaveAttribute("aria-pressed", "true");
  });
});

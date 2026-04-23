import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
    bulkStatus: jest.fn(),
    ingest: jest.fn(),
    bulkIngest: jest.fn(),
    upload: jest.fn(),
    uploadMany: jest.fn(),
    createText: jest.fn(),
    createUrl: jest.fn(),
    delete: jest.fn(),
  },
}));

jest.mock("@/lib/chat-stream", () => ({
  streamNotebookChat: jest.fn(),
}));

function setViewportWidth(width: number) {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    writable: true,
    value: width,
  });
  window.dispatchEvent(new Event("resize"));
}

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

function mockBulkStatuses() {
  (sourcesApi.bulkStatus as jest.Mock).mockImplementation((sourceIds: string[]) => {
    const statuses = sourceIds.map((sourceId) => {
      if (sourceId === "source-1") {
        return {
          source_id: sourceId,
          status: "processing",
          progress: {
            current_step: "embedding",
            percentage: 70,
            embedded_chunks: 7,
            total_chunks: 10,
          },
          error_message: null,
          job_id: "job-source-1",
          job_status: "running",
          task_id: "task-source-1",
          started_at: null,
          completed_at: null,
        };
      }

      if (sourceId === "source-2") {
        return {
          source_id: sourceId,
          status: "failed",
          progress: null,
          error_message: "Could not parse the source content.",
          job_id: "job-source-2",
          job_status: "failed",
          task_id: "task-source-2",
          started_at: null,
          completed_at: "2026-04-08T12:00:00Z",
        };
      }

      if (sourceId === "source-3") {
        return {
          source_id: sourceId,
          status: "pending",
          progress: {
            message: "Queued for ingestion",
          },
          error_message: null,
          job_id: "job-source-3",
          job_status: "queued",
          task_id: "task-source-3",
          started_at: null,
          completed_at: null,
        };
      }

      return {
        source_id: sourceId,
        status: "ready",
        progress: null,
        error_message: null,
        job_id: `job-${sourceId}`,
        job_status: "completed",
        task_id: `task-${sourceId}`,
        started_at: null,
        completed_at: "2026-04-08T12:00:00Z",
      };
    });

    return Promise.resolve({
      statuses,
      has_pending_sources: statuses.some(
        (status) => status.status === "pending" || status.status === "processing"
      ),
    });
  });
}

describe("NotebookDetailPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setViewportWidth(1440);
    (notebooksApi.get as jest.Mock).mockResolvedValue(mockNotebook);
    (sourcesApi.list as jest.Mock).mockResolvedValue(mockSources);
    mockBulkStatuses();
  });

  it("renders the notebook workspace with a dedicated chat panel", async () => {
    render(<NotebookDetailPage />);

    expect(await screen.findByText("Deep Research Notes")).toBeInTheDocument();
    const addSourceButtons = await screen.findAllByRole("button", { name: "ADD SOURCE" });
    expect(addSourceButtons.length).toBeGreaterThan(0);
    const chatHeading = screen.getByRole("heading", { name: "Start Query" });
    expect(chatHeading).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Ask your scholarship...")
    ).toBeInTheDocument();
  });

  it("renders notebook sources with status badges, progress details, and reserved sections", async () => {
    render(<NotebookDetailPage />);

    expect(await screen.findByText("Alpha Research Dossier")).toBeInTheDocument();
    expect(screen.getByText("Launch Risks Memo")).toBeInTheDocument();
    expect(screen.getByText("Queued Interview Notes")).toBeInTheDocument();
    expect(screen.getByText("Customer Insights Brief")).toBeInTheDocument();
    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getByText("4 total")).toBeInTheDocument();
    expect(screen.getByText("1 ready")).toBeInTheDocument();
    expect(screen.getByText("PDF")).toBeInTheDocument();
    expect(screen.getByText("URL")).toBeInTheDocument();
    expect(screen.getByText("TEXT")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getAllByText("Pending").length).toBeGreaterThan(0);
    expect(screen.getByText("Processing")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Notebook Summary")).toBeInTheDocument();
    expect(screen.getByText("Key insights and overview")).toBeInTheDocument();
    expect(screen.getByText("Generated Assets")).toBeInTheDocument();
    expect(screen.getByText("Derived content")).toBeInTheDocument();
  });

  it("shows an empty state when the notebook has no sources", async () => {
    (sourcesApi.list as jest.Mock).mockResolvedValueOnce([]);

    render(<NotebookDetailPage />);

    expect(await screen.findByText(/No sources yet/i)).toBeInTheDocument();
    expect(
      screen.getByText("Add a PDF, pasted text, or URL to start grounding this notebook.")
    ).toBeInTheDocument();
    expect(sourcesApi.bulkStatus).not.toHaveBeenCalled();
  });

  it("shows a source loading error and retries in place", async () => {
    const user = userEvent.setup();

    (sourcesApi.list as jest.Mock)
      .mockRejectedValueOnce(new Error("Sources API unavailable"))
      .mockResolvedValueOnce(mockSources);

    render(<NotebookDetailPage />);

    expect(await screen.findByText("Sources API unavailable")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Refresh sources" }));
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

    const textarea = await screen.findByPlaceholderText("Ask your scholarship...");
    await act(async () => {
      await user.type(textarea, "What do the sources say about Alpha?");
      await user.keyboard("{Enter}");
    });

    expect(
      screen.getAllByText("What do the sources say about Alpha?").length
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Process workflow")).toBeInTheDocument();
    expect(
      screen.getAllByText("Waiting for the first answer chunk from the model").length
    ).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Alpha launch").length).toBeGreaterThanOrEqual(1);

    await act(async () => {
      resolveStream?.();
    });

    expect(
      (
        await screen.findAllByText(
          "Alpha launch preparation is documented in the sources."
        )
      ).length
    ).toBeGreaterThanOrEqual(1);

    expect(streamNotebookChat).toHaveBeenCalledWith(
      expect.objectContaining({
        notebookId: "notebook-123",
        question: "What do the sources say about Alpha?",
      })
    );

    await waitFor(() => {
      expect(
        screen.getAllByText("Alpha launch preparation is documented in the sources.").length
      ).toBeGreaterThanOrEqual(1);
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

    const textarea = await screen.findByPlaceholderText("Ask your scholarship...");
    await act(async () => {
      await user.type(textarea, "What is the launch plan?");
      await user.click(screen.getByRole("button", { name: "Send" }));
    });

    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: "Sources used in this answer" })).not.toBeInTheDocument();
    });

    const firstMarker = screen.getByRole("button", { name: "Open citation 1" });
    const secondMarker = screen.getByRole("button", { name: "Open citation 2" });

    expect(firstMarker).toBeInTheDocument();
    expect(secondMarker).toBeInTheDocument();

    await act(async () => {
      await user.click(firstMarker);
    });

    const firstPreview = await screen.findByRole("dialog", { name: "Citation 1 preview" });
    expect(within(firstPreview).getByText("Alpha Guide")).toBeInTheDocument();
    expect(within(firstPreview).getByText("Alpha launch planning starts in Q2.")).toBeInTheDocument();
    expect(within(firstPreview).getAllByText("Page 12").length).toBeGreaterThanOrEqual(1);
    expect(within(firstPreview).getAllByText("Score 0.95").length).toBeGreaterThanOrEqual(1);
    expect(document.body.style.overflow).toBe("hidden");
    expect(screen.getByRole("button", { name: "Close citation preview overlay" })).toBeInTheDocument();

    // Close the first preview via Escape key
    await act(async () => {
      fireEvent.keyDown(document, { key: "Escape" });
    });

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Citation 1 preview" })).not.toBeInTheDocument();
    });

    // Re-query markers after re-render (they may have been recreated)
    const freshSecondMarker = screen.getByRole("button", { name: "Open citation 2" });

    await act(async () => {
      fireEvent.click(freshSecondMarker);
    });

    const secondPreview = await screen.findByRole("dialog", { name: "Citation 2 preview" });
    expect(within(secondPreview).getByText("Beta Brief")).toBeInTheDocument();
    expect(within(secondPreview).getByText("Beta mitigates the logistics risk.")).toBeInTheDocument();
    expect(within(secondPreview).getAllByText("Page 4").length).toBeGreaterThanOrEqual(1);
    expect(within(secondPreview).getAllByText("Score 0.82").length).toBeGreaterThanOrEqual(1);

    await act(async () => {
      fireEvent.keyDown(document, { key: "Escape" });
    });

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Citation 2 preview" })).not.toBeInTheDocument();
    });
    expect(document.body.style.overflow).toBe("");
  });
});

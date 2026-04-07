import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import NotebookDetailPage from "./page";
import { notebooksApi, type Notebook } from "@/lib/api";
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

describe("NotebookDetailPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (notebooksApi.get as jest.Mock).mockResolvedValue(mockNotebook);
  });

  it("renders the notebook workspace with a dedicated chat panel", async () => {
    render(<NotebookDetailPage />);

    expect(await screen.findByText("Deep Research Notes")).toBeInTheDocument();
    expect(screen.getByText("Grounded chat")).toBeInTheDocument();
    expect(
      screen.getByText("Ask questions against the sources in this notebook.")
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Ask a source-grounded question...")
    ).toBeInTheDocument();
  });

  it("adds user and assistant messages while the stream is active", async () => {
    const user = userEvent.setup();
    let resolveStream: (() => void) | undefined;

    (streamNotebookChat as jest.Mock).mockImplementation(
      async ({
        onStatus,
        onAnswer,
        onDone,
      }: {
        onStatus: (payload: { stage: string; message: string }) => void;
        onAnswer: (payload: { answer: string; raw_answer: string }) => void;
        onDone: (payload: { status: string }) => void;
      }) => {
        onStatus({
          stage: "retrieving",
          message: "Searching sources in notebook notebook-123",
        });

        await new Promise<void>((resolve) => {
          resolveStream = () => {
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
    expect(screen.getByText(/Searching sources/)).toBeInTheDocument();
    expect(screen.getByText("Generating answer")).toBeInTheDocument();

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
      expect(screen.queryByText("Generating answer")).not.toBeInTheDocument();
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
          stage: "retrieving",
          message: "Searching sources in notebook notebook-123",
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
    expect(screen.getByText("Alpha launch planning starts in Q2.")).toBeInTheDocument();
    expect(screen.getAllByText("Page 12")).toHaveLength(2);
    expect(screen.getAllByText("Score 0.95")).toHaveLength(2);
    expect(
      screen.getByRole("button", { name: "View citation 1 from Alpha Guide" })
    ).toHaveAttribute("aria-pressed", "true");

    await act(async () => {
      await user.click(secondMarker);
    });

    expect(screen.getByText("Beta mitigates the logistics risk.")).toBeInTheDocument();
    expect(screen.getAllByText("Page 4")).toHaveLength(2);
    expect(screen.getAllByText("Score 0.82")).toHaveLength(2);
    expect(
      screen.getByRole("button", { name: "View citation 2 from Beta Brief" })
    ).toHaveAttribute("aria-pressed", "true");
  });
});

import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import ChunkSelector from "./chunk-selector";
import { evaluationApi } from "@/lib/evaluation-api";

jest.mock("@/lib/evaluation-api", () => ({
  evaluationApi: {
    getNotebookChunks: jest.fn(),
  },
}));

function ChunkSelectorHarness() {
  const [selectedChunkIds, setSelectedChunkIds] = useState<string[]>([]);

  return (
    <form>
      <ChunkSelector
        notebookId="notebook-1"
        selectedChunkIds={selectedChunkIds}
        onSelectionChange={setSelectedChunkIds}
      />
      <output aria-label="Selected chunk count">{selectedChunkIds.length}</output>
    </form>
  );
}

describe("ChunkSelector", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    (evaluationApi.getNotebookChunks as jest.Mock).mockResolvedValue({
      chunks: [
        {
          id: "chunk-alpha-1",
          source_id: "source-1",
          source_title: "Alpha Source",
          chunk_index: 0,
          content: "Alpha chunk one",
          preview: "Alpha preview one",
          token_count: 42,
          metadata: { page: 3 },
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
    });
  });

  it("selects a chunk from inside a form without entering an update loop", async () => {
    const user = userEvent.setup();

    render(<ChunkSelectorHarness />);

    expect(await screen.findByText("Alpha Source")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByText("Alpha preview one"));
    });

    await waitFor(() => {
      expect(screen.getByLabelText("Selected chunk count")).toHaveTextContent("1");
    });
  });
});

import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import NotebooksPage from "./page";
import { ToastProvider } from "@/lib/toast";
import { notebooksApi, sourcesApi } from "@/lib/api";

const push = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push,
  }),
}));

jest.mock("@/lib/api", () => ({
  notebooksApi: {
    list: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
  },
  sourcesApi: {
    list: jest.fn(),
  },
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      message: string
    ) {
      super(message);
      this.name = "ApiError";
    }
  },
}));

jest.mock("@/components/notebooks/notebook-form-dialog", () => ({
  NotebookFormDialog: () => null,
}));

jest.mock("@/components/notebooks/delete-dialog", () => ({
  DeleteDialog: () => null,
}));

const notebooks = [
  {
    id: "notebook-1",
    user_id: "user-1",
    name: "Quantum Physics Research",
    description: "Exploration of entanglement theory.",
    created_at: "2026-04-08T12:00:00Z",
    updated_at: "2026-04-08T14:00:00Z",
  },
  {
    id: "notebook-2",
    user_id: "user-1",
    name: "Product Strategy 2024",
    description: "Quarterly roadmap planning.",
    created_at: "2026-04-07T12:00:00Z",
    updated_at: "2026-04-09T10:00:00Z",
  },
];

describe("NotebooksPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    (notebooksApi.list as jest.Mock).mockResolvedValue(notebooks);
    (sourcesApi.list as jest.Mock).mockImplementation((notebookId: string) => {
      if (notebookId === "notebook-1") {
        return Promise.resolve([{}, {}]);
      }
      if (notebookId === "notebook-2") {
        return Promise.resolve([{}]);
      }
      return Promise.resolve([]);
    });
  });

  it("renders notebooks and supports search filtering", async () => {
    const user = userEvent.setup();

    render(
      <ToastProvider>
        <NotebooksPage />
      </ToastProvider>
    );

    expect(await screen.findByRole("heading", { name: "Notebooks" })).toBeInTheDocument();
    expect(await screen.findByText("Product Strategy 2024")).toBeInTheDocument();
    expect(screen.getByText("Quantum Physics Research")).toBeInTheDocument();

    const searchInput =
      screen.queryByLabelText("Search knowledge") ??
      screen.getByLabelText("Search your research");

    await act(async () => {
      await user.clear(searchInput);
      await user.type(searchInput, "product");
    });

    await waitFor(() => {
      expect(screen.getByText("Product Strategy 2024")).toBeInTheDocument();
      expect(screen.queryByText("Quantum Physics Research")).not.toBeInTheDocument();
    });
  });
});

import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import EvaluationDashboard from "./page";
import { evaluationApi } from "@/lib/evaluation-api";
import { notebooksApi } from "@/lib/api";

const push = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push,
  }),
}));

jest.mock("@/lib/evaluation-api", () => ({
  evaluationApi: {
    list: jest.fn(),
    create: jest.fn(),
    start: jest.fn(),
    exportCsv: jest.fn(),
    getNotebookChunks: jest.fn(),
  },
}));

jest.mock("@/lib/api", () => ({
  notebooksApi: {
    list: jest.fn(),
  },
}));

jest.mock("@/components/ui/dialog", () => {
  const React = require("react");

  const DialogContext = React.createContext({
    open: false,
    onOpenChange: (_open: boolean) => undefined,
  });

  return {
    Dialog: ({ open, onOpenChange, children }) => (
      <DialogContext.Provider value={{ open, onOpenChange }}>
        {children}
      </DialogContext.Provider>
    ),
    DialogTrigger: ({ asChild, children }) => {
      const { onOpenChange } = React.useContext(DialogContext);

      if (asChild && React.isValidElement(children)) {
        return React.cloneElement(children, {
          onClick: (event) => {
            children.props.onClick?.(event);
            onOpenChange(true);
          },
        });
      }

      return <button onClick={() => onOpenChange(true)}>{children}</button>;
    },
    DialogContent: ({ children, className }) => {
      const { open } = React.useContext(DialogContext);
      return open ? <div role="dialog" className={className}>{children}</div> : null;
    },
    DialogHeader: ({ children }) => <div>{children}</div>,
    DialogTitle: ({ children }) => <h2>{children}</h2>,
    DialogDescription: ({ children }) => <p>{children}</p>,
    DialogFooter: ({ children }) => <div>{children}</div>,
  };
});

jest.mock("@/components/ui/checkbox", () => ({
  Checkbox: ({
    checked,
    id,
    onCheckedChange,
  }: {
    checked?: boolean;
    id?: string;
    onCheckedChange?: (checked: boolean) => void;
  }) => (
    <input
      id={id}
      type="checkbox"
      checked={Boolean(checked)}
      onChange={(event) => onCheckedChange?.(event.target.checked)}
    />
  ),
}));

const notebooks = [
  {
    id: "notebook-1",
    user_id: "user-1",
    name: "Alpha Notebook",
    description: "Alpha research",
    created_at: "2026-04-08T12:00:00Z",
    updated_at: "2026-04-08T12:00:00Z",
  },
  {
    id: "notebook-2",
    user_id: "user-1",
    name: "Beta Notebook",
    description: "Beta interviews",
    created_at: "2026-04-07T12:00:00Z",
    updated_at: "2026-04-07T12:00:00Z",
  },
];

const baseRuns = [
  {
    id: "run-pending",
    notebook_id: "notebook-1",
    query: "Pending query",
    status: "pending" as const,
    error_message: null,
    created_at: "2026-04-08T12:00:00Z",
    started_at: null,
    completed_at: null,
    metrics: [],
  },
  {
    id: "run-failed",
    notebook_id: "notebook-2",
    query: "Failed query",
    status: "failed" as const,
    error_message: "Temporary model failure",
    created_at: "2026-04-08T13:00:00Z",
    started_at: "2026-04-08T13:01:00Z",
    completed_at: "2026-04-08T13:02:00Z",
    metrics: [],
  },
  {
    id: "run-completed",
    notebook_id: "notebook-1",
    query: "Completed query",
    status: "completed" as const,
    error_message: null,
    created_at: "2026-04-08T14:00:00Z",
    started_at: "2026-04-08T14:01:00Z",
    completed_at: "2026-04-08T14:02:00Z",
    metrics: [
      {
        metric_type: "groundedness",
        metric_value: 0.82,
        metadata: null,
      },
    ],
  },
];

const summary = {
  groundedness: 0.82,
};

describe("EvaluationDashboard", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    (notebooksApi.list as jest.Mock).mockResolvedValue(notebooks);
    (evaluationApi.list as jest.Mock).mockResolvedValue({
      evaluation_runs: baseRuns,
      summary,
    });
    (evaluationApi.create as jest.Mock).mockResolvedValue({
      id: "run-new",
      notebook_id: "notebook-1",
      query: "What does Alpha say?",
      status: "pending",
      error_message: null,
      created_at: "2026-04-09T09:00:00Z",
      started_at: null,
      completed_at: null,
      metrics: [],
    });
    (evaluationApi.start as jest.Mock).mockResolvedValue({
      id: "run-new",
      notebook_id: "notebook-1",
      query: "What does Alpha say?",
      status: "completed",
      error_message: null,
      created_at: "2026-04-09T09:00:00Z",
      started_at: "2026-04-09T09:01:00Z",
      completed_at: "2026-04-09T09:02:00Z",
      metrics: [],
    });
    (evaluationApi.getNotebookChunks as jest.Mock).mockImplementation((notebookId: string) => {
      if (notebookId === "notebook-1") {
        return Promise.resolve({
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
      }

      return Promise.resolve({
        chunks: [
          {
            id: "chunk-beta-1",
            source_id: "source-2",
            source_title: "Beta Source",
            chunk_index: 0,
            content: "Beta chunk one",
            preview: "Beta preview one",
            token_count: 24,
            metadata: { page: 1 },
          },
        ],
        total: 1,
        limit: 100,
        offset: 0,
      });
    });
  });

  it("filters evaluation runs with a notebook picker instead of raw notebook id input", async () => {
    const user = userEvent.setup();

    render(<EvaluationDashboard />);

    const filterSelect = await screen.findByLabelText("Notebook filter");

    expect(within(filterSelect).getByRole("option", { name: "All notebooks" })).toBeInTheDocument();
    expect(within(filterSelect).getByRole("option", { name: "Alpha Notebook" })).toBeInTheDocument();
    expect(within(filterSelect).getByRole("option", { name: "Beta Notebook" })).toBeInTheDocument();

    await act(async () => {
      await user.selectOptions(filterSelect, "notebook-2");
    });

    await waitFor(() => {
      expect(evaluationApi.list).toHaveBeenLastCalledWith({ notebook_id: "notebook-2" });
    });
  });

  it("creates and starts an evaluation with a notebook-scoped chunk selection", async () => {
    const user = userEvent.setup();

    render(<EvaluationDashboard />);

    expect(await screen.findByText("Pending query")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Create Test" }));
    });

    const dialog = await screen.findByRole("dialog");
    const notebookSelect = within(dialog).getByLabelText("Notebook");
    const queryInput = within(dialog).getByLabelText("Test Query *");

    await act(async () => {
      await user.selectOptions(notebookSelect, "notebook-1");
    });

    await waitFor(() => {
      expect(evaluationApi.getNotebookChunks).toHaveBeenCalledWith("notebook-1", 100, 0);
    });

    expect(await within(dialog).findByText("Alpha Source")).toBeInTheDocument();

    await act(async () => {
      await user.type(queryInput, "What does Alpha say?");
      await user.click(within(dialog).getByText("Alpha preview one"));
    });

    expect(within(dialog).getByText(/1 selected/i)).toBeInTheDocument();

    await act(async () => {
      await user.click(within(dialog).getByRole("button", { name: "Create & Run Test" }));
    });

    expect(evaluationApi.create).toHaveBeenCalledWith({
      notebook_id: "notebook-1",
      query: "What does Alpha say?",
      ground_truth_chunk_ids: ["chunk-alpha-1"],
    });
    expect(evaluationApi.start).toHaveBeenCalledWith("run-new");
  });

  it("clears stale chunk selections when the dialog notebook changes", async () => {
    const user = userEvent.setup();

    render(<EvaluationDashboard />);

    await screen.findByText("Pending query");

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Create Test" }));
    });

    const dialog = await screen.findByRole("dialog");
    const notebookSelect = within(dialog).getByLabelText("Notebook");
    const queryInput = within(dialog).getByLabelText("Test Query *");

    await act(async () => {
      await user.type(queryInput, "Switch notebooks");
      await user.selectOptions(notebookSelect, "notebook-1");
    });

    expect(await within(dialog).findByText("Alpha Source")).toBeInTheDocument();

    await act(async () => {
      await user.click(within(dialog).getByText("Alpha preview one"));
    });

    expect(within(dialog).getByText(/1 selected/i)).toBeInTheDocument();

    await act(async () => {
      await user.selectOptions(notebookSelect, "notebook-2");
    });

    await waitFor(() => {
      expect(evaluationApi.getNotebookChunks).toHaveBeenCalledWith("notebook-2", 100, 0);
    });

    expect(await within(dialog).findByText("Beta Source")).toBeInTheDocument();
    expect(within(dialog).queryByText("Alpha Source")).not.toBeInTheDocument();
    expect(within(dialog).getByText(/0 selected/i)).toBeInTheDocument();

    await act(async () => {
      await user.click(within(dialog).getByRole("button", { name: "Create & Run Test" }));
    });

    expect(evaluationApi.create).toHaveBeenLastCalledWith({
      notebook_id: "notebook-2",
      query: "Switch notebooks",
      ground_truth_chunk_ids: undefined,
    });
  });

  it("shows a notebook empty state when no notebooks are available", async () => {
    const user = userEvent.setup();

    (notebooksApi.list as jest.Mock).mockResolvedValueOnce([]);

    render(<EvaluationDashboard />);

    const filterSelect = await screen.findByLabelText("Notebook filter");
    expect(filterSelect).toBeDisabled();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Create Test" }));
    });

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("No notebooks available yet. Create a notebook first.")).toBeInTheDocument();
    expect(within(dialog).getByLabelText("Notebook")).toBeDisabled();
  });

  it("shows start and retry actions for evaluation runs", async () => {
    const user = userEvent.setup();

    render(<EvaluationDashboard />);

    expect(await screen.findByText("Pending query")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Start Pending query" }));
    });

    await waitFor(() => {
      expect(evaluationApi.start).toHaveBeenCalledWith("run-pending");
    });

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Retry Failed query" }));
    });

    await waitFor(() => {
      expect(evaluationApi.start).toHaveBeenCalledWith("run-failed");
    });
  });
});

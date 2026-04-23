import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { NotebookWorkspace } from "./notebook-workspace";
import { notebooksApi, sourcesApi } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  notebooksApi: {
    get: jest.fn(),
  },
  sourcesApi: {
    list: jest.fn(),
    getSnapshotSummary: jest.fn(),
    getStatus: jest.fn(),
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

const existingSources = [
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
    status: "ready",
    file_size: null,
    created_at: "2026-04-06T12:00:00Z",
    updated_at: "2026-04-06T12:00:00Z",
  },
];

const uploadedPdfSource = {
  id: "source-3",
  source_type: "pdf",
  title: "Quarterly Brief",
  status: "pending",
  file_size: 2048,
  created_at: "2026-04-08T12:00:00Z",
  updated_at: "2026-04-08T12:00:00Z",
};

const pastedTextSource = {
  id: "source-4",
  source_type: "text",
  title: "Interview transcript",
  status: "pending",
  file_size: 512,
  created_at: "2026-04-08T12:10:00Z",
  updated_at: "2026-04-08T12:10:00Z",
};

const urlSource = {
  id: "source-5",
  source_type: "url",
  title: "https://example.com/research",
  status: "pending",
  file_size: null,
  created_at: "2026-04-08T12:20:00Z",
  updated_at: "2026-04-08T12:20:00Z",
};

const batchUploadSources = [
  {
    id: "source-6",
    source_type: "pdf",
    title: "brief.pdf",
    status: "pending",
    file_size: 2048,
    created_at: "2026-04-08T12:40:00Z",
    updated_at: "2026-04-08T12:40:00Z",
  },
  {
    id: "source-7",
    source_type: "text",
    title: "notes.txt",
    status: "pending",
    file_size: 256,
    created_at: "2026-04-08T12:41:00Z",
    updated_at: "2026-04-08T12:41:00Z",
  },
];

const readySourceSnapshot = {
  overview:
    "Launch Risks Memo summarizes the operational blockers, ownership gaps, and mitigation paths for the release.",
  covered_themes: ["Operational risks", "Mitigation planning", "Ownership"],
  top_keywords: ["launch readiness", "dependencies", "owners"],
};

function deferredPromise<T>() {
  let resolve: (value: T | PromiseLike<T>) => void = () => undefined;
  let reject: (reason?: unknown) => void = () => undefined;

  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });

  return { promise, resolve, reject };
}

function createFileList(files: File[]) {
  return Object.assign(files, {
    item: (index: number) => files[index] ?? null,
  });
}

function mockBulkStatuses() {
  (sourcesApi.bulkStatus as jest.Mock).mockImplementation((sourceIds: string[]) => {
    const statuses = sourceIds.map((sourceId) => {
      if (sourceId === "source-1") {
        return {
          source_id: sourceId,
          status: "processing",
          progress: {
            current_step: "embedding",
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
          status: "ready",
          progress: null,
          error_message: null,
          job_id: "job-source-2",
          job_status: "completed",
          task_id: "task-source-2",
          started_at: null,
          completed_at: "2026-04-08T12:00:00Z",
        };
      }

      return {
        source_id: sourceId,
        status: "pending",
        progress: null,
        error_message: null,
        job_id: `job-${sourceId}`,
        job_status: "queued",
        task_id: `task-${sourceId}`,
        started_at: null,
        completed_at: null,
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

describe("NotebookWorkspace", () => {
  afterEach(() => {
    jest.useRealTimers();
  });

  beforeEach(() => {
    jest.resetAllMocks();
    (notebooksApi.get as jest.Mock).mockResolvedValue({
      id: "notebook-123",
      user_id: "user-1",
      name: "Quantum Physics Research",
      description: "Non-local interactions and observer-effect dynamics in relativistic particles.",
      created_at: "2026-04-01T12:00:00Z",
      updated_at: "2026-04-01T12:00:00Z",
    });
    (sourcesApi.list as jest.Mock).mockResolvedValue(existingSources);
    (sourcesApi.getSnapshotSummary as jest.Mock).mockResolvedValue(readySourceSnapshot);
    (sourcesApi.ingest as jest.Mock).mockResolvedValue({
      source_id: "source-default",
      status: "pending",
      job_id: "job-default",
      job_status: "queued",
      task_id: "task-default",
      progress: null,
      error_message: null,
      started_at: null,
      completed_at: null,
    });
    (sourcesApi.bulkIngest as jest.Mock).mockResolvedValue([]);
    mockBulkStatuses();
  });

  it("renders an add-source entry point and opens the source dialog", async () => {
    const user = userEvent.setup();

    render(<NotebookWorkspace notebookId="notebook-123" />);

    expect(await screen.findByText("Alpha Research Dossier")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "ADD SOURCE" }));
    });

    const dialog = await screen.findByRole("dialog");

    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByRole("heading", { name: "Add source" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Upload" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Text" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "URL" })).toBeInTheDocument();
    expect(sourcesApi.bulkStatus).toHaveBeenCalledWith(["source-1", "source-2"]);
    expect(sourcesApi.getStatus).not.toHaveBeenCalled();
  });

  it("opens a source snapshot preview card on hover for ready sources and closes it on blur", async () => {
    const user = userEvent.setup();
    const request = deferredPromise<typeof readySourceSnapshot>();
    (sourcesApi.getSnapshotSummary as jest.Mock).mockReturnValueOnce(request.promise);

    render(<NotebookWorkspace notebookId="notebook-123" />);

    expect(await screen.findByText("Launch Risks Memo")).toBeInTheDocument();

    await act(async () => {
      await user.hover(screen.getByTestId("source-row-source-2"));
    });

    expect(await screen.findByText("Loading snapshot preview...")).toBeInTheDocument();
    expect(sourcesApi.getSnapshotSummary).toHaveBeenCalledWith(
      "notebook-123",
      "source-2"
    );

    await act(async () => {
      request.resolve(readySourceSnapshot);
    });

    expect(await screen.findByText("Snapshot preview")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Launch Risks Memo summarizes the operational blockers, ownership gaps, and mitigation paths for the release."
      )
    ).toBeInTheDocument();
    expect(screen.getByText("Operational risks")).toBeInTheDocument();
    expect(screen.getByText("launch readiness")).toBeInTheDocument();

    await act(async () => {
      await user.unhover(screen.getByTestId("source-row-source-2"));
    });

    await waitFor(() => {
      expect(screen.queryByText("Snapshot preview")).not.toBeInTheDocument();
    });
  });

  it("shows an unavailable state for sources that are not ready yet", async () => {
    const user = userEvent.setup();

    render(<NotebookWorkspace notebookId="notebook-123" />);

    expect(await screen.findByText("Alpha Research Dossier")).toBeInTheDocument();

    await act(async () => {
      await user.hover(screen.getByTestId("source-row-source-1"));
    });

    expect(await screen.findByText("Snapshot preview")).toBeInTheDocument();
    expect(
      screen.getByText("Snapshot preview becomes available after ingestion finishes.")
    ).toBeInTheDocument();
    expect(sourcesApi.getSnapshotSummary).not.toHaveBeenCalled();
  });

  it("does not open another row snapshot while a source menu is open", async () => {
    const user = userEvent.setup();

    render(<NotebookWorkspace notebookId="notebook-123" />);

    expect(await screen.findByText("Alpha Research Dossier")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "More actions for Alpha Research Dossier" }));
    });

    expect(screen.getByRole("button", { name: "Preview snapshot" })).toBeInTheDocument();

    await act(async () => {
      fireEvent.mouseEnter(screen.getByTestId("source-row-source-2"));
    });

    expect(sourcesApi.getSnapshotSummary).not.toHaveBeenCalled();
    expect(screen.queryByText("Loading snapshot preview...")).not.toBeInTheDocument();
  });

  it("keeps source actions accessible when the snapshot preview is already open", async () => {
    const user = userEvent.setup();

    render(<NotebookWorkspace notebookId="notebook-123" />);

    expect(await screen.findByText("Launch Risks Memo")).toBeInTheDocument();

    await act(async () => {
      await user.hover(screen.getByTestId("source-row-source-2"));
    });

    expect(await screen.findByText("Snapshot preview")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "More actions for Launch Risks Memo" }));
    });

    expect(screen.getByRole("button", { name: "Preview snapshot" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete source" })).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Delete source" }));
    });

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("closes the source action menu when clicking outside the portal", async () => {
    const user = userEvent.setup();

    render(<NotebookWorkspace notebookId="notebook-123" />);

    expect(await screen.findByText("Alpha Research Dossier")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "More actions for Alpha Research Dossier" }));
    });

    expect(screen.getByRole("button", { name: "Preview snapshot" })).toBeInTheDocument();

    act(() => {
      fireEvent.pointerDown(document.body);
    });

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Preview snapshot" })).not.toBeInTheDocument();
    });
  });

  it("creates a URL source and refreshes the source list in place", async () => {
    const user = userEvent.setup();

    (sourcesApi.createUrl as jest.Mock).mockResolvedValue(urlSource);
    (sourcesApi.list as jest.Mock)
      .mockResolvedValueOnce(existingSources)
      .mockResolvedValueOnce([urlSource, ...existingSources]);

    render(<NotebookWorkspace notebookId="notebook-123" />);

    expect(await screen.findByText("Alpha Research Dossier")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "ADD SOURCE" }));
    });

    const dialog = await screen.findByRole("dialog");

    await act(async () => {
      await user.click(within(dialog).getByRole("button", { name: "URL" }));
    });

    const urlInput = await screen.findByLabelText("Source URL");

    await act(async () => {
      await user.type(urlInput, "https://example.com/research");
      await user.click(within(dialog).getByRole("button", { name: "Add URL" }));
    });

    expect(sourcesApi.createUrl).toHaveBeenCalledWith("notebook-123", {
      title: "",
      url: "https://example.com/research",
    });
    expect(await screen.findByText("https://example.com/research")).toBeInTheDocument();
    expect(sourcesApi.list).toHaveBeenCalledTimes(2);
  });

  it("creates a text source from pasted content and refreshes the workspace", async () => {
    const user = userEvent.setup();

    (sourcesApi.createText as jest.Mock).mockResolvedValue(pastedTextSource);
    (sourcesApi.list as jest.Mock)
      .mockResolvedValueOnce(existingSources)
      .mockResolvedValueOnce([pastedTextSource, ...existingSources]);

    render(<NotebookWorkspace notebookId="notebook-123" />);

    expect(await screen.findByText("Alpha Research Dossier")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "ADD SOURCE" }));
    });

    const dialog = await screen.findByRole("dialog");

    await act(async () => {
      await user.click(within(dialog).getByRole("button", { name: "Text" }));
    });

    const titleInput = await screen.findByLabelText("Title");
    const textInput = await screen.findByLabelText("Pasted text");

    await act(async () => {
      await user.type(titleInput, "Interview transcript");
      await user.type(textInput, "Key launch notes");
      await user.click(within(dialog).getByRole("button", { name: "Add text" }));
    });

    expect(sourcesApi.createText).toHaveBeenCalledWith("notebook-123", {
      title: "Interview transcript",
      content: "Key launch notes",
    });
    expect(await screen.findByText("Interview transcript")).toBeInTheDocument();
  });

  it("uploads a PDF source and rejects unsupported file types", async () => {
    const user = userEvent.setup();

    (sourcesApi.upload as jest.Mock).mockResolvedValue(uploadedPdfSource);
    (sourcesApi.list as jest.Mock)
      .mockResolvedValueOnce(existingSources)
      .mockResolvedValueOnce([uploadedPdfSource, ...existingSources]);

    render(<NotebookWorkspace notebookId="notebook-123" />);

    expect(await screen.findByText("Alpha Research Dossier")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "ADD SOURCE" }));
    });

    const dialog = await screen.findByRole("dialog");
    const fileInput = within(dialog).getByLabelText("Choose file") as HTMLInputElement;
    const invalidFile = new File(["png"], "diagram.png", { type: "image/png" });

    await act(async () => {
      fireEvent.change(fileInput, {
        target: { files: createFileList([invalidFile]) },
      });
      await user.click(within(dialog).getByRole("button", { name: "Upload source" }));
    });

    expect(within(dialog).getByText("Only PDF and TXT files are supported.")).toBeInTheDocument();
    expect(sourcesApi.upload).not.toHaveBeenCalled();

    const pdfFile = new File(["%PDF"], "brief.pdf", { type: "application/pdf" });

    await act(async () => {
      fireEvent.change(fileInput, {
        target: { files: createFileList([pdfFile]) },
      });
      await user.clear(within(dialog).getByLabelText("Title"));
      await user.type(within(dialog).getByLabelText("Title"), "Quarterly Brief");
      await user.click(within(dialog).getByRole("button", { name: "Upload source" }));
    });

    expect(sourcesApi.upload).toHaveBeenCalledWith("notebook-123", {
      file: pdfFile,
      title: "Quarterly Brief",
    });
    expect(await screen.findByText("Quarterly Brief")).toBeInTheDocument();
  });

  it("auto-fills the upload title from filename, starts ingestion, and polls until the source resolves", async () => {
    jest.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });

    const pendingUploadSource = {
      ...uploadedPdfSource,
      title: "brief",
    };

    (sourcesApi.list as jest.Mock)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([pendingUploadSource]);
    (sourcesApi.upload as jest.Mock).mockResolvedValue(pendingUploadSource);
    (sourcesApi.ingest as jest.Mock).mockResolvedValue({
      source_id: pendingUploadSource.id,
      status: "pending",
      job_id: "job-123",
      job_status: "queued",
      task_id: "task-123",
      progress: {
        message: "Queued for ingestion",
      },
      error_message: null,
      started_at: null,
      completed_at: null,
    });

    let uploadStatusCallCount = 0;
    (sourcesApi.bulkStatus as jest.Mock).mockImplementation((sourceIds: string[]) => {
      const statuses = sourceIds.map((sourceId) => {
        if (sourceId !== pendingUploadSource.id) {
          return {
            source_id: sourceId,
            status: "ready",
            job_id: null,
            job_status: null,
            task_id: null,
            progress: null,
            error_message: null,
            started_at: null,
            completed_at: null,
          };
        }

        uploadStatusCallCount += 1;

        if (uploadStatusCallCount === 1) {
          return {
            source_id: sourceId,
            status: "pending",
            job_id: "job-123",
            job_status: "queued",
            task_id: "task-123",
            progress: {
              message: "Queued for ingestion",
            },
            error_message: null,
            started_at: null,
            completed_at: null,
          };
        }

        if (uploadStatusCallCount === 2) {
          return {
            source_id: sourceId,
            status: "processing",
            job_id: "job-123",
            job_status: "running",
            task_id: "task-123",
            progress: {
              current_step: "embedding",
              embedded_chunks: 1,
              total_chunks: 2,
            },
            error_message: null,
            started_at: null,
            completed_at: null,
          };
        }

        return {
          source_id: sourceId,
          status: "ready",
          job_id: "job-123",
          job_status: "completed",
          task_id: "task-123",
          progress: null,
          error_message: null,
          started_at: null,
          completed_at: "2026-04-08T12:30:00Z",
        };
      });

      return Promise.resolve({
        statuses,
        has_pending_sources: statuses.some(
          (status) => status.status === "pending" || status.status === "processing"
        ),
      });
    });

    render(<NotebookWorkspace notebookId="notebook-123" />);

    expect(await screen.findByText("No sources yet")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "ADD SOURCE" }));
    });

    const dialog = await screen.findByRole("dialog");
    const fileInput = within(dialog).getByLabelText("Choose file") as HTMLInputElement;
    const pdfFile = new File(["%PDF"], "brief.pdf", { type: "application/pdf" });

    await act(async () => {
      fireEvent.change(fileInput, {
        target: { files: createFileList([pdfFile]) },
      });
    });

    expect(within(dialog).getByLabelText("Title")).toHaveValue("brief");

    await act(async () => {
      await user.click(within(dialog).getByRole("button", { name: "Upload source" }));
    });

    await waitFor(() => {
      expect(sourcesApi.upload).toHaveBeenCalledWith("notebook-123", {
        file: pdfFile,
        title: "brief",
      });
    });
    expect(sourcesApi.ingest).toHaveBeenCalledWith("source-3");
    expect(sourcesApi.bulkIngest).not.toHaveBeenCalled();
    expect(await screen.findByText("Queued for ingestion")).toBeInTheDocument();

    await act(async () => {
      jest.advanceTimersByTime(1500);
    });

    expect(await screen.findByText("Embedding 1 of 2 chunks")).toBeInTheDocument();

    await act(async () => {
      jest.advanceTimersByTime(1500);
    });

    await waitFor(() => {
      expect(screen.getByText("Ready")).toBeInTheDocument();
    });
    const resolvedBulkStatusCallCount = (sourcesApi.bulkStatus as jest.Mock).mock.calls.length;

    await act(async () => {
      jest.advanceTimersByTime(1500);
    });

    expect((sourcesApi.bulkStatus as jest.Mock).mock.calls).toHaveLength(
      resolvedBulkStatusCallCount
    );
    expect(sourcesApi.list).toHaveBeenCalledTimes(2);
    expect(sourcesApi.bulkStatus).toHaveBeenLastCalledWith(["source-3"]);
    expect(sourcesApi.getStatus).not.toHaveBeenCalled();
  });

  it("uploads multiple files, enqueues ingestion for each source, and tracks the batch", async () => {
    jest.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });

    (sourcesApi.list as jest.Mock)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce(batchUploadSources);
    (sourcesApi.uploadMany as jest.Mock).mockResolvedValue(batchUploadSources);
    (sourcesApi.bulkIngest as jest.Mock).mockResolvedValue([
      {
        source_id: "source-6",
        status: "pending",
        job_id: "job-source-6",
        job_status: "queued",
        task_id: "task-source-6",
        progress: {
          message: "Queued for ingestion",
        },
        error_message: null,
        started_at: null,
        completed_at: null,
      },
      {
        source_id: "source-7",
        status: "pending",
        job_id: "job-source-7",
        job_status: "queued",
        task_id: "task-source-7",
        progress: {
          message: "Queued for ingestion",
        },
        error_message: null,
        started_at: null,
        completed_at: null,
      },
    ]);

    const statusCalls = new Map<string, number>();
    (sourcesApi.bulkStatus as jest.Mock).mockImplementation((sourceIds: string[]) => {
      const statuses = sourceIds.map((sourceId) => {
        const nextCount = (statusCalls.get(sourceId) ?? 0) + 1;
        statusCalls.set(sourceId, nextCount);

        return {
          source_id: sourceId,
          status: nextCount === 1 ? "pending" : "ready",
          job_id: `job-${sourceId}`,
          job_status: nextCount === 1 ? "queued" : "completed",
          task_id: `task-${sourceId}`,
          progress:
            nextCount === 1
              ? {
                  message: "Queued for ingestion",
                }
              : null,
          error_message: null,
          started_at: null,
          completed_at: nextCount === 1 ? null : "2026-04-08T12:45:00Z",
        };
      });

      return Promise.resolve({
        statuses,
        has_pending_sources: statuses.some((status) => status.status === "pending"),
      });
    });

    render(<NotebookWorkspace notebookId="notebook-123" />);

    expect(await screen.findByText("No sources yet")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "ADD SOURCE" }));
    });

    const dialog = await screen.findByRole("dialog");
    const fileInput = within(dialog).getByLabelText("Choose file") as HTMLInputElement;
    const pdfFile = new File(["%PDF"], "brief.pdf", { type: "application/pdf" });
    const txtFile = new File(["notes"], "notes.txt", { type: "text/plain" });

    await act(async () => {
      fireEvent.change(fileInput, {
        target: { files: createFileList([pdfFile, txtFile]) },
      });
    });

    expect(within(dialog).getByText("2 files selected")).toBeInTheDocument();
    expect(within(dialog).getByText("brief.pdf")).toBeInTheDocument();
    expect(within(dialog).getByText("notes.txt")).toBeInTheDocument();

    await act(async () => {
      await user.click(within(dialog).getByRole("button", { name: "Upload 2 sources" }));
    });

    await waitFor(() => {
      expect(sourcesApi.uploadMany).toHaveBeenCalledWith("notebook-123", {
        files: [pdfFile, txtFile],
      });
    });
    expect(sourcesApi.bulkIngest).toHaveBeenCalledWith(["source-6", "source-7"]);
    expect(sourcesApi.ingest).not.toHaveBeenCalled();
    expect(await screen.findByText("brief.pdf")).toBeInTheDocument();
    expect(await screen.findByText("notes.txt")).toBeInTheDocument();

    await act(async () => {
      jest.advanceTimersByTime(1500);
    });

    await waitFor(() => {
      expect(statusCalls.get("source-6")).toBeGreaterThanOrEqual(2);
      expect(statusCalls.get("source-7")).toBeGreaterThanOrEqual(2);
    });
    expect(sourcesApi.getStatus).not.toHaveBeenCalled();
  });

  it("retries pending and failed sources in bulk", async () => {
    const user = userEvent.setup();
    const retryCandidates = [
      {
        id: "source-pending",
        source_type: "pdf",
        title: "Pending Source",
        status: "pending",
        file_size: 1024,
        created_at: "2026-04-08T10:00:00Z",
        updated_at: "2026-04-08T10:00:00Z",
      },
      {
        id: "source-failed",
        source_type: "url",
        title: "Failed Source",
        status: "failed",
        file_size: null,
        created_at: "2026-04-08T10:05:00Z",
        updated_at: "2026-04-08T10:05:00Z",
      },
      {
        id: "source-ready",
        source_type: "text",
        title: "Ready Source",
        status: "ready",
        file_size: 256,
        created_at: "2026-04-08T10:10:00Z",
        updated_at: "2026-04-08T10:10:00Z",
      },
    ];

    (sourcesApi.list as jest.Mock)
      .mockResolvedValueOnce(retryCandidates)
      .mockResolvedValueOnce(retryCandidates.map((source) => ({ ...source, status: "pending" })));
    (sourcesApi.bulkStatus as jest.Mock).mockResolvedValue({
      statuses: retryCandidates.map((source) => ({
        source_id: source.id,
        status: source.status,
        job_id: source.status === "ready" ? "job-ready" : null,
        job_status: source.status === "ready" ? "completed" : null,
        task_id: source.status === "ready" ? "task-ready" : null,
        progress: null,
        error_message: source.status === "failed" ? "Ingestion failed." : null,
        started_at: null,
        completed_at: null,
      })),
      has_pending_sources: true,
    });
    (sourcesApi.bulkIngest as jest.Mock).mockResolvedValue([
      {
        source_id: "source-pending",
        status: "pending",
        job_id: "job-pending",
        job_status: "queued",
        task_id: "task-pending",
        progress: {
          message: "Queued for ingestion",
        },
        error_message: null,
        started_at: null,
        completed_at: null,
      },
      {
        source_id: "source-failed",
        status: "pending",
        job_id: "job-failed",
        job_status: "queued",
        task_id: "task-failed",
        progress: {
          message: "Queued for ingestion",
        },
        error_message: null,
        started_at: null,
        completed_at: null,
      },
    ]);

    render(<NotebookWorkspace notebookId="notebook-123" />);

    expect(await screen.findByText("Pending Source")).toBeInTheDocument();
    const retryButton = screen.getByRole("button", { name: "Retry pending/failed" });
    expect(retryButton).toBeEnabled();

    await act(async () => {
      await user.click(retryButton);
    });

    expect(sourcesApi.bulkIngest).toHaveBeenCalledWith([
      "source-pending",
      "source-failed",
    ]);
    expect(sourcesApi.ingest).not.toHaveBeenCalled();
    expect(sourcesApi.list).toHaveBeenCalledTimes(2);
  });

  it("validates URL input and surfaces loading and API errors", async () => {
    const user = userEvent.setup();
    const request = deferredPromise<void>();

    (sourcesApi.createUrl as jest.Mock).mockReturnValue(request.promise);

    render(<NotebookWorkspace notebookId="notebook-123" />);

    expect(await screen.findByText("Alpha Research Dossier")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "ADD SOURCE" }));
    });

    const dialog = await screen.findByRole("dialog");

    await act(async () => {
      await user.click(within(dialog).getByRole("button", { name: "URL" }));
    });

    const urlInput = await screen.findByLabelText("Source URL");

    await act(async () => {
      await user.type(urlInput, "not-a-valid-url");
      await user.click(within(dialog).getByRole("button", { name: "Add URL" }));
    });

    expect(within(dialog).getByText("Enter a valid URL.")).toBeInTheDocument();
    expect(sourcesApi.createUrl).not.toHaveBeenCalled();

    await act(async () => {
      await user.clear(urlInput);
      await user.type(urlInput, "https://example.com/research");
      await user.click(within(dialog).getByRole("button", { name: "Add URL" }));
    });

    expect(within(dialog).getByRole("button", { name: "Adding URL..." })).toBeDisabled();

    await act(async () => {
      request.reject(new Error("URL ingestion unavailable"));
    });

    await waitFor(() => {
      expect(within(dialog).getByText("URL ingestion unavailable")).toBeInTheDocument();
    });
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("requires confirmation before deleting a source", async () => {
    const user = userEvent.setup();

    render(<NotebookWorkspace notebookId="notebook-123" />);

    expect(await screen.findByText("Launch Risks Memo")).toBeInTheDocument();

    const sourceCard = screen.getByText("Launch Risks Memo").closest("article");
    expect(sourceCard).not.toBeNull();

    await act(async () => {
      await user.click(
        within(sourceCard as HTMLElement).getByRole("button", {
          name: "More actions for Launch Risks Memo",
        })
      );
    });

    await act(async () => {
      await user.click(
        screen.getByRole("button", {
          name: "Delete source",
        })
      );
    });

    const dialog = await screen.findByRole("dialog");

    expect(within(dialog).getByRole("heading", { name: "Delete source?" })).toBeInTheDocument();
    expect(within(dialog).getByText("Launch Risks Memo")).toBeInTheDocument();
    expect(sourcesApi.delete).not.toHaveBeenCalled();
  });

  it("deletes a source in place after confirmation without reloading the page", async () => {
    const user = userEvent.setup();

    (sourcesApi.delete as jest.Mock).mockResolvedValue(undefined);

    render(<NotebookWorkspace notebookId="notebook-123" />);

    expect(await screen.findByText("Launch Risks Memo")).toBeInTheDocument();

    const sourceCard = screen.getByText("Launch Risks Memo").closest("article");
    expect(sourceCard).not.toBeNull();

    await act(async () => {
      await user.click(
        within(sourceCard as HTMLElement).getByRole("button", {
          name: "More actions for Launch Risks Memo",
        })
      );
    });

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Delete source" }));
    });

    const dialog = await screen.findByRole("dialog");

    await act(async () => {
      await user.click(within(dialog).getByRole("button", { name: "Delete source" }));
    });

    expect(sourcesApi.delete).toHaveBeenCalledWith("notebook-123", "source-2");
    await waitFor(() => {
      expect(screen.queryByText("Launch Risks Memo")).not.toBeInTheDocument();
    });
    expect(sourcesApi.list).toHaveBeenCalledTimes(1);
  });

  it("shows a delete error and preserves the source row when deletion fails", async () => {
    const user = userEvent.setup();

    (sourcesApi.delete as jest.Mock).mockRejectedValue(
      new Error("Could not delete this source.")
    );

    render(<NotebookWorkspace notebookId="notebook-123" />);

    expect(await screen.findByText("Launch Risks Memo")).toBeInTheDocument();

    const sourceCard = screen.getByText("Launch Risks Memo").closest("article");
    expect(sourceCard).not.toBeNull();

    await act(async () => {
      await user.click(
        within(sourceCard as HTMLElement).getByRole("button", {
          name: "More actions for Launch Risks Memo",
        })
      );
    });

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Delete source" }));
    });

    const dialog = await screen.findByRole("dialog");

    await act(async () => {
      await user.click(within(dialog).getByRole("button", { name: "Delete source" }));
    });

    expect(await within(dialog).findByText("Could not delete this source.")).toBeInTheDocument();
    expect(screen.getAllByText("Launch Risks Memo")).toHaveLength(2);
  });
});

import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { NotebookWorkspace } from "./notebook-workspace";
import { sourcesApi } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  sourcesApi: {
    list: jest.fn(),
    getStatus: jest.fn(),
    ingest: jest.fn(),
    upload: jest.fn(),
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

function mockStatuses() {
  (sourcesApi.getStatus as jest.Mock).mockImplementation((sourceId: string) => {
    if (sourceId === "source-1") {
      return Promise.resolve({
        source_id: sourceId,
        status: "processing",
        progress: {
          current_step: "embedding",
          embedded_chunks: 7,
          total_chunks: 10,
        },
        error_message: null,
      });
    }

    return Promise.resolve({
      source_id: sourceId,
      status: "pending",
      progress: null,
      error_message: null,
    });
  });
}

describe("NotebookWorkspace", () => {
  afterEach(() => {
    jest.useRealTimers();
  });

  beforeEach(() => {
    jest.clearAllMocks();
    (sourcesApi.list as jest.Mock).mockResolvedValue(existingSources);
    mockStatuses();
  });

  it("renders an add-source entry point and opens the source dialog", async () => {
    const user = userEvent.setup();

    render(<NotebookWorkspace notebookId="notebook-123" />);

    expect(await screen.findByText("Alpha Research Dossier")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Add source" }));
    });

    const dialog = await screen.findByRole("dialog");

    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByRole("heading", { name: "Add source" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Upload" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Text" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "URL" })).toBeInTheDocument();
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
      await user.click(screen.getByRole("button", { name: "Add source" }));
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
      await user.click(screen.getByRole("button", { name: "Add source" }));
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
      await user.click(screen.getByRole("button", { name: "Add source" }));
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
      title: "brief.pdf",
    };

    const readyUploadSource = {
      ...pendingUploadSource,
      status: "ready",
    };

    (sourcesApi.list as jest.Mock)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([pendingUploadSource])
      .mockResolvedValueOnce([pendingUploadSource])
      .mockResolvedValueOnce([readyUploadSource]);
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
    (sourcesApi.getStatus as jest.Mock).mockImplementation((sourceId: string) => {
      if (sourceId !== pendingUploadSource.id) {
        return Promise.resolve({
          source_id: sourceId,
          status: "ready",
          job_id: null,
          job_status: null,
          task_id: null,
          progress: null,
          error_message: null,
          started_at: null,
          completed_at: null,
        });
      }

      uploadStatusCallCount += 1;

      if (uploadStatusCallCount === 1) {
        return Promise.resolve({
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
        });
      }

      if (uploadStatusCallCount === 2) {
        return Promise.resolve({
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
        });
      }

      return Promise.resolve({
        source_id: sourceId,
        status: "ready",
        job_id: "job-123",
        job_status: "completed",
        task_id: "task-123",
        progress: null,
        error_message: null,
        started_at: null,
        completed_at: "2026-04-08T12:30:00Z",
      });
    });

    render(<NotebookWorkspace notebookId="notebook-123" />);

    expect(await screen.findByText("No sources yet")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Add source" }));
    });

    const dialog = await screen.findByRole("dialog");
    const fileInput = within(dialog).getByLabelText("Choose file") as HTMLInputElement;
    const pdfFile = new File(["%PDF"], "brief.pdf", { type: "application/pdf" });

    await act(async () => {
      fireEvent.change(fileInput, {
        target: { files: createFileList([pdfFile]) },
      });
    });

    expect(within(dialog).getByLabelText("Title")).toHaveValue("brief.pdf");

    await act(async () => {
      await user.click(within(dialog).getByRole("button", { name: "Upload source" }));
    });

    await waitFor(() => {
      expect(sourcesApi.upload).toHaveBeenCalledWith("notebook-123", {
        file: pdfFile,
        title: "brief.pdf",
      });
    });
    expect(sourcesApi.ingest).toHaveBeenCalledWith("source-3");
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
    expect(sourcesApi.list).toHaveBeenCalledTimes(4);
    expect(sourcesApi.getStatus).toHaveBeenCalledWith("source-3");
  });

  it("validates URL input and surfaces loading and API errors", async () => {
    const user = userEvent.setup();
    const request = deferredPromise<void>();

    (sourcesApi.createUrl as jest.Mock).mockReturnValue(request.promise);

    render(<NotebookWorkspace notebookId="notebook-123" />);

    expect(await screen.findByText("Alpha Research Dossier")).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Add source" }));
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
          name: "Delete source",
        })
      );
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
          name: "Delete source",
        })
      );
    });

    const dialog = await screen.findByRole("dialog");

    await act(async () => {
      await user.click(within(dialog).getByRole("button", { name: "Delete source" }));
    });

    expect(await within(dialog).findByText("Could not delete this source.")).toBeInTheDocument();
    expect(screen.getAllByText("Launch Risks Memo")).toHaveLength(2);
  });
});

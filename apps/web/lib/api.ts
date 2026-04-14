/**
 * API client for NotebookLX backend
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Notebook {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateNotebookData {
  name: string;
  description?: string;
}

export interface UpdateNotebookData {
  name?: string;
  description?: string;
}

export type SourceType = "pdf" | "url" | "text" | "youtube" | "audio" | "gdocs";
export type SourceStatus = "pending" | "processing" | "ready" | "failed";
export type IngestionJobStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "retrying";

export interface NotebookSource {
  id: string;
  source_type: SourceType;
  title: string;
  status: SourceStatus;
  file_size: number | null;
  created_at: string;
  updated_at: string;
}

export interface SourceSnapshotSummary {
  overview: string;
  covered_themes: string[];
  top_keywords: string[];
}

export interface SourceIngestionStatus {
  source_id: string;
  status: SourceStatus;
  job_id: string | null;
  job_status: IngestionJobStatus | null;
  task_id: string | null;
  progress: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface BulkSourceIngestionStatusResponse {
  statuses: SourceIngestionStatus[];
  has_pending_sources: boolean;
}

export interface CreateTextSourceData {
  title?: string;
  content: string;
}

export interface CreateUrlSourceData {
  title?: string;
  url: string;
}

export interface UploadSourceData {
  title?: string;
  file: File;
}

export interface UploadManySourcesData {
  files: File[];
}

class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function extractErrorMessage(errorData: unknown): string {
  if (typeof errorData === "string") return errorData;
  if (errorData && typeof errorData === "object") {
    const obj = errorData as Record<string, unknown>;
    if (typeof obj.message === "string") return obj.message;
    if (typeof obj.detail === "string") return obj.detail;
    if (obj.detail && typeof obj.detail === "object") {
      const detail = obj.detail as Record<string, unknown>;
      if (typeof detail.message === "string") return detail.message;
    }
  }
  return "";
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message =
      extractErrorMessage(errorData) ||
      `HTTP error! status: ${response.status}`;
    throw new ApiError(response.status, message);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export const notebooksApi = {
  /**
   * List all notebooks
   */
  async list(): Promise<Notebook[]> {
    const response = await fetch(`${API_URL}/api/notebooks`);
    return handleResponse<Notebook[]>(response);
  },

  /**
   * Get a single notebook by ID
   */
  async get(id: string): Promise<Notebook> {
    const response = await fetch(`${API_URL}/api/notebooks/${id}`);
    return handleResponse<Notebook>(response);
  },

  /**
   * Create a new notebook
   */
  async create(data: CreateNotebookData): Promise<Notebook> {
    const response = await fetch(`${API_URL}/api/notebooks`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });
    return handleResponse<Notebook>(response);
  },

  /**
   * Update an existing notebook
   */
  async update(id: string, data: UpdateNotebookData): Promise<Notebook> {
    const response = await fetch(`${API_URL}/api/notebooks/${id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });
    return handleResponse<Notebook>(response);
  },

  /**
   * Delete a notebook
   */
  async delete(id: string): Promise<void> {
    const response = await fetch(`${API_URL}/api/notebooks/${id}`, {
      method: "DELETE",
    });
    return handleResponse<void>(response);
  },
};

export const sourcesApi = {
  /**
   * List sources for a notebook.
   */
  async list(notebookId: string): Promise<NotebookSource[]> {
    const response = await fetch(`${API_URL}/api/notebooks/${notebookId}/sources`);
    return handleResponse<NotebookSource[]>(response);
  },

  /**
   * Get the compact snapshot summary for a source.
   */
  async getSnapshotSummary(
    notebookId: string,
    sourceId: string
  ): Promise<SourceSnapshotSummary> {
    const response = await fetch(
      `${API_URL}/api/notebooks/${notebookId}/sources/${sourceId}/snapshot`
    );
    return handleResponse<SourceSnapshotSummary>(response);
  },

  /**
   * Get the latest ingestion status for a source.
   */
  async getStatus(sourceId: string): Promise<SourceIngestionStatus> {
    const response = await fetch(`${API_URL}/api/sources/${sourceId}/status`);
    return handleResponse<SourceIngestionStatus>(response);
  },

  /**
   * Enqueue ingestion for a source.
   */
  async ingest(sourceId: string): Promise<SourceIngestionStatus> {
    const response = await fetch(`${API_URL}/api/sources/${sourceId}/ingest`, {
      method: "POST",
    });
    return handleResponse<SourceIngestionStatus>(response);
  },

  /**
   * Enqueue ingestion for multiple sources in one request.
   */
  async bulkIngest(sourceIds: string[]): Promise<SourceIngestionStatus[]> {
    const response = await fetch(`${API_URL}/api/sources/ingest/batch`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        source_ids: sourceIds,
      }),
    });
    const data = await handleResponse<{ jobs: SourceIngestionStatus[] }>(response);
    return data.jobs;
  },

  /**
   * Get ingestion status for multiple sources in one request.
   */
  async bulkStatus(sourceIds: string[]): Promise<BulkSourceIngestionStatusResponse> {
    const response = await fetch(`${API_URL}/api/sources/status/batch`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        source_ids: sourceIds,
      }),
    });
    return handleResponse<BulkSourceIngestionStatusResponse>(response);
  },

  /**
   * Create a pasted text source for a notebook.
   */
  async createText(
    notebookId: string,
    data: CreateTextSourceData
  ): Promise<NotebookSource> {
    const response = await fetch(`${API_URL}/api/notebooks/${notebookId}/sources/text`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });
    return handleResponse<NotebookSource>(response);
  },

  /**
   * Create a URL source for a notebook.
   */
  async createUrl(
    notebookId: string,
    data: CreateUrlSourceData
  ): Promise<NotebookSource> {
    const response = await fetch(`${API_URL}/api/notebooks/${notebookId}/sources/url`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });
    return handleResponse<NotebookSource>(response);
  },

  /**
   * Upload a file-backed source for a notebook.
   */
  async upload(
    notebookId: string,
    data: UploadSourceData
  ): Promise<NotebookSource> {
    const formData = new FormData();
    formData.append("file", data.file);

    if (data.title?.trim()) {
      formData.append("title", data.title.trim());
    }

    const response = await fetch(`${API_URL}/api/notebooks/${notebookId}/sources/upload`, {
      method: "POST",
      body: formData,
    });
    return handleResponse<NotebookSource>(response);
  },

  /**
   * Upload multiple file-backed sources for a notebook.
   */
  async uploadMany(
    notebookId: string,
    data: UploadManySourcesData
  ): Promise<NotebookSource[]> {
    const formData = new FormData();
    data.files.forEach((file) => {
      formData.append("files", file);
    });

    const response = await fetch(`${API_URL}/api/notebooks/${notebookId}/sources/upload/batch`, {
      method: "POST",
      body: formData,
    });
    return handleResponse<NotebookSource[]>(response);
  },

  /**
   * Delete a source from a notebook.
   */
  async delete(notebookId: string, sourceId: string): Promise<void> {
    const response = await fetch(`${API_URL}/api/notebooks/${notebookId}/sources/${sourceId}`, {
      method: "DELETE",
    });
    return handleResponse<void>(response);
  },
};

export { ApiError };

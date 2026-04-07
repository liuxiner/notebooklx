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

class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.message || errorData.detail || `HTTP error! status: ${response.status}`;
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
   * Get the latest ingestion status for a source.
   */
  async getStatus(sourceId: string): Promise<SourceIngestionStatus> {
    const response = await fetch(`${API_URL}/api/sources/${sourceId}/status`);
    return handleResponse<SourceIngestionStatus>(response);
  },
};

export { ApiError };

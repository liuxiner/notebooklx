/**
 * Evaluation API client for metrics and evaluation dashboard.
 *
 * Feature 6.3: Evaluation Dashboard
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface MetricValue {
  metric_type: string;
  metric_value: number;
  metadata: Record<string, unknown> | null;
}

export interface EvaluationDetail {
  id: string;
  notebook_id: string;
  query: string;
  status: "pending" | "running" | "completed" | "failed";
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  metrics: MetricValue[];
}

export interface MetricsListResponse {
  evaluation_runs: EvaluationDetail[];
  summary: Record<string, number>;
}

export interface EvaluationFilters {
  notebook_id?: string;
  start_date?: string;
  end_date?: string;
  metric_types?: string[];
}

export interface EvaluationCreate {
  notebook_id: string;
  query: string;
  ground_truth_chunk_ids?: string[];
}

class ApiError extends Error {
  constructor(
    public status: number,
    public message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: "Unknown error" }));
    throw new ApiError(response.status, error.detail?.message || error.message || "Request failed");
  }
  return response.json();
}

export interface ChunkItem {
  id: string;
  source_id: string;
  source_title: string;
  chunk_index: number;
  content: string;
  preview: string;
  token_count: number;
  metadata: Record<string, unknown>;
}

export interface ChunksListResponse {
  chunks: ChunkItem[];
  total: number;
  limit: number;
  offset: number;
}

export const evaluationApi = {
  /**
   * List evaluation runs with optional filters
   * AC: Dashboard shows trends over time
   * AC: Filterable by notebook, time range
   */
  async list(filters?: EvaluationFilters): Promise<MetricsListResponse> {
    const params = new URLSearchParams();
    if (filters?.notebook_id) {
      params.set("notebook_id", filters.notebook_id);
    }
    if (filters?.start_date) {
      params.set("start_date", filters.start_date);
    }
    if (filters?.end_date) {
      params.set("end_date", filters.end_date);
    }
    if (filters?.metric_types) {
      filters.metric_types.forEach((type) => params.append("metric_types", type));
    }

    const query = params.toString();
    const url = `${API_URL}/api/evaluation/runs${query ? `?${query}` : ""}`;

    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
      },
    });

    return handleResponse<MetricsListResponse>(response);
  },

  /**
   * Get a single evaluation run by ID with metrics
   * AC: Get single evaluation by ID with all metadata
   */
  async get(runId: string): Promise<EvaluationDetail> {
    const response = await fetch(`${API_URL}/api/evaluation/runs/${runId}`, {
      headers: {
        "Content-Type": "application/json",
      },
    });

    return handleResponse<EvaluationDetail>(response);
  },

  /**
   * Create a new evaluation run
   */
  async create(data: EvaluationCreate): Promise<EvaluationDetail> {
    const response = await fetch(`${API_URL}/api/evaluation/runs`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });

    return handleResponse<EvaluationDetail>(response);
  },

  /**
   * Start an evaluation run
   */
  async start(runId: string): Promise<EvaluationDetail> {
    const response = await fetch(`${API_URL}/api/evaluation/runs/${runId}/start`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });

    return handleResponse<EvaluationDetail>(response);
  },

  /**
   * Export metrics as CSV
   * AC: Export metrics as CSV
   */
  async exportCsv(filters?: EvaluationFilters): Promise<Blob> {
    const params = new URLSearchParams();
    if (filters?.notebook_id) {
      params.set("notebook_id", filters.notebook_id);
    }
    if (filters?.start_date) {
      params.set("start_date", filters.start_date);
    }
    if (filters?.end_date) {
      params.set("end_date", filters.end_date);
    }
    if (filters?.metric_types) {
      filters.metric_types.forEach((type) => params.append("metric_types", type));
    }

    const query = params.toString();
    const url = `${API_URL}/api/evaluation/metrics/export${query ? `?${query}` : ""}`;

    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: "Unknown error" }));
      throw new ApiError(response.status, error.detail?.message || error.message || "Export failed");
    }

    return response.blob();
  },

  /**
   * Get chunks for a notebook (for ground truth selection)
   */
  async getNotebookChunks(notebookId: string, limit = 100, offset = 0): Promise<ChunksListResponse> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });

    const response = await fetch(`${API_URL}/api/notebooks/${notebookId}/chunks?${params}`, {
      headers: {
        "Content-Type": "application/json",
      },
    });

    return handleResponse<ChunksListResponse>(response);
  },
};

/**
 * Evaluation Dashboard page.
 *
 * Feature 6.3: Evaluation Dashboard
 *
 * AC: Dashboard shows trends over time
 * AC: Filterable by notebook, time range
 * AC: Export metrics as CSV
 */
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { evaluationApi, type MetricsListResponse } from "@/lib/evaluation-api";
import type { EvaluationFilters as FilterType } from "@/lib/evaluation-api";
import { notebooksApi, type Notebook } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import MetricsOverview from "@/components/evaluation/metrics-overview";
import EvaluationFilterControls from "@/components/evaluation/evaluation-filters";
import EvaluationRunsTable from "@/components/evaluation/evaluation-runs-table";
import CreateEvaluationDialog from "@/components/evaluation/create-evaluation-dialog";
import { Download, ArrowLeft } from "lucide-react";

export default function EvaluationDashboard() {
  const router = useRouter();
  const [data, setData] = useState<MetricsListResponse | null>(null);
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [notebooksLoading, setNotebooksLoading] = useState(true);
  const [notebooksError, setNotebooksError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterType>({});
  const [exporting, setExporting] = useState(false);
  const [actionRunId, setActionRunId] = useState<string | null>(null);

  const fetchMetrics = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await evaluationApi.list(filters);
      setData(result);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to load evaluation metrics");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, [filters]);

  useEffect(() => {
    const fetchNotebooks = async () => {
      setNotebooksLoading(true);
      setNotebooksError(null);
      try {
        const result = await notebooksApi.list();
        setNotebooks(result);
      } catch (err) {
        if (err instanceof Error) {
          setNotebooksError(err.message);
        } else {
          setNotebooksError("Failed to load notebooks");
        }
      } finally {
        setNotebooksLoading(false);
      }
    };

    fetchNotebooks();
  }, []);

  const handleRunAction = async (runId: string) => {
    setActionRunId(runId);
    setError(null);
    try {
      await evaluationApi.start(runId);
      await fetchMetrics();
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to run evaluation");
      }
    } finally {
      setActionRunId(null);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await evaluationApi.exportCsv(filters);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `evaluation_metrics_${new Date().toISOString().split("T")[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to export metrics");
      }
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => router.push("/notebooks")}
              >
                <ArrowLeft className="h-5 w-5" />
              </Button>
              <div>
                <h1 className="text-2xl font-semibold text-slate-900">
                  Evaluation Dashboard
                </h1>
                <p className="text-sm text-slate-500">
                  Track retrieval, citation, and answer quality metrics over time
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <CreateEvaluationDialog
                initialNotebookId={filters.notebook_id}
                notebooks={notebooks}
                notebooksLoading={notebooksLoading}
                notebooksError={notebooksError}
                onSuccess={fetchMetrics}
              />
              <Button
                variant="outline"
                onClick={handleExport}
                disabled={exporting || loading || !data || data.evaluation_runs.length === 0}
              >
                <Download className="h-4 w-4 mr-2" />
                {exporting ? "Exporting..." : "Export CSV"}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Filters */}
        <EvaluationFilterControls
          filters={filters}
          notebooks={notebooks}
          notebooksLoading={notebooksLoading}
          notebooksError={notebooksError}
          onChange={setFilters}
        />

        {/* Error State */}
        {error && (
          <Card className="mb-6 border-destructive/50 bg-destructive/5">
            <CardContent className="pt-6">
              <p className="text-sm text-destructive">{error}</p>
            </CardContent>
          </Card>
        )}

        {/* Loading State */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <Spinner />
          </div>
        )}

        {/* Empty State */}
        {!loading && data && data.evaluation_runs.length === 0 && (
          <Card className="text-center py-12">
            <CardContent>
              <p className="text-slate-500 mb-4">
                No evaluation runs found. Adjust your filters or run some evaluations to see metrics.
              </p>
              <Button
                variant="outline"
                onClick={() => router.push("/notebooks")}
              >
                Go to Notebooks
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Metrics Overview */}
        {!loading && data && data.evaluation_runs.length > 0 && (
          <>
            <MetricsOverview summary={data.summary} />

            {/* Evaluation Runs Table */}
            <div className="mt-6">
              <EvaluationRunsTable
                runs={data.evaluation_runs}
                actionRunId={actionRunId}
                onRunAction={handleRunAction}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

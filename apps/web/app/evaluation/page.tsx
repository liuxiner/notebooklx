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
import { evaluationApi, type MetricsListResponse } from "@/lib/evaluation-api";
import type { EvaluationFilters as FilterType } from "@/lib/evaluation-api";
import { notebooksApi, type Notebook } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import MetricsOverview from "@/components/evaluation/metrics-overview";
import EvaluationFilterControls from "@/components/evaluation/evaluation-filters";
import EvaluationRunsTable from "@/components/evaluation/evaluation-runs-table";
import CreateEvaluationDialog from "@/components/evaluation/create-evaluation-dialog";
import { AppShell, MobileBrandHeader } from "@/components/layout/app-shell";
import { Download, Search, Sparkles } from "lucide-react";

export default function EvaluationDashboard() {
  const [data, setData] = useState<MetricsListResponse | null>(null);
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [notebooksLoading, setNotebooksLoading] = useState(true);
  const [notebooksError, setNotebooksError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterType>({});
  const [exporting, setExporting] = useState(false);
  const [actionRunId, setActionRunId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

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

  const desktopSearchBar = (
    <div className="relative w-[280px]">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
      <input
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        placeholder="Search evaluations..."
        aria-label="Search evaluations"
        className="h-10 w-full rounded-full border border-slate-200 bg-slate-50/70 pl-9 pr-3 text-sm text-slate-900 shadow-sm outline-none focus:border-primary/40 focus:ring-4 focus:ring-primary/10"
      />
    </div>
  );

  const desktopTopBarActions = (
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
        size="sm"
        onClick={handleExport}
        disabled={exporting || loading || !data || data.evaluation_runs.length === 0}
        className="text-xs"
      >
        <Download className="h-3.5 w-3.5 mr-1.5" />
        {exporting ? "Exporting..." : "Export CSV"}
      </Button>
    </div>
  );

  return (
    <AppShell
      activeNav="evaluation"
      searchBar={desktopSearchBar}
      topBarActions={desktopTopBarActions}
    >
      <MobileBrandHeader />

      {/* Page header */}
      <div className="flex flex-col gap-4 tablet:flex-row tablet:items-end tablet:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950 tablet:text-4xl">
            Evaluation Dashboard
          </h1>
          <p className="mt-1 text-sm italic text-slate-500">
            Track retrieval, citation, and answer quality metrics over time.
          </p>
        </div>

        {/* Mobile action buttons */}
        <div className="flex items-center gap-2 tablet:hidden">
          <CreateEvaluationDialog
            initialNotebookId={filters.notebook_id}
            notebooks={notebooks}
            notebooksLoading={notebooksLoading}
            notebooksError={notebooksError}
            onSuccess={fetchMetrics}
          />
          <Button
            variant="outline"
            size="sm"
            onClick={handleExport}
            disabled={exporting || loading || !data || data.evaluation_runs.length === 0}
            className="text-xs"
          >
            <Download className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Inline filters */}
      <div className="mt-5">
        <EvaluationFilterControls
          filters={filters}
          notebooks={notebooks}
          notebooksLoading={notebooksLoading}
          notebooksError={notebooksError}
          onChange={setFilters}
        />
      </div>

      {/* Error State */}
      {error && (
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="mt-8 flex items-center justify-center py-16">
          <Spinner />
        </div>
      )}

      {/* Empty State */}
      {!loading && data && data.evaluation_runs.length === 0 && (
        <div className="mt-8 rounded-2xl border border-slate-200 bg-white py-16 text-center shadow-sm">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
            <Sparkles className="h-6 w-6" />
          </div>
          <p className="mt-4 text-sm text-slate-500">
            No evaluation runs found. Adjust your filters or run some evaluations to see metrics.
          </p>
          <p className="mt-1 text-xs text-slate-400">
            Use the &ldquo;Create Test&rdquo; button to start evaluating your notebooks.
          </p>
        </div>
      )}

      {/* Metrics + Table */}
      {!loading && data && data.evaluation_runs.length > 0 && (
        <>
          <MetricsOverview summary={data.summary} />

          <EvaluationRunsTable
            runs={data.evaluation_runs}
            notebooks={notebooks}
            actionRunId={actionRunId}
            onRunAction={handleRunAction}
          />

          {/* Curator AI Insights */}
          <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Sparkles className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-semibold text-slate-900">
                  Curator AI Insights
                </h3>
                <p className="mt-1.5 text-sm leading-relaxed text-slate-600">
                  {data.evaluation_runs.length > 0 ? (
                    <>
                      Based on {data.evaluation_runs.length} evaluation run{data.evaluation_runs.length !== 1 ? "s" : ""},
                      your retrieval pipeline shows{" "}
                      <span className="font-medium text-slate-900">
                        {data.summary.faithfulness !== undefined
                          ? `${(data.summary.faithfulness * 100).toFixed(0)}% faithfulness`
                          : "stable performance"}
                      </span>
                      {data.summary.recall_at_10 !== undefined && (
                        <>
                          {" "}and{" "}
                          <span className="font-medium text-slate-900">
                            {(data.summary.recall_at_10 * 100).toFixed(0)}% recall@10
                          </span>
                        </>
                      )}
                      . Consider reviewing chunk overlap settings to further improve retrieval accuracy.
                    </>
                  ) : (
                    "Run evaluations to get AI-powered insights about your retrieval and generation quality."
                  )}
                </p>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Mobile spacing for bottom nav */}
      <div className="h-20 desktop:hidden" />
    </AppShell>
  );
}

/**
 * Evaluation Runs Table component.
 *
 * Displays a table of evaluation runs matching the design with columns:
 * Notebook Name, Execution Date, Score, Status, Actions
 *
 * Feature 6.3: Evaluation Dashboard
 */
import { Button } from "@/components/ui/button";
import { Clock, CheckCircle2, XCircle, Loader2, MoreHorizontal } from "lucide-react";
import type { EvaluationDetail } from "@/lib/evaluation-api";
import type { Notebook } from "@/lib/api";
import { cn } from "@/lib/utils";

interface EvaluationRunsTableProps {
  runs: EvaluationDetail[];
  notebooks: Notebook[];
  actionRunId?: string | null;
  onRunAction?: (runId: string) => void | Promise<void>;
}

const STATUS_CONFIG = {
  pending: {
    label: "Pending",
    icon: Clock,
    color: "text-slate-600",
    bgColor: "bg-slate-100",
    dotColor: "bg-slate-400",
  },
  running: {
    label: "Running",
    icon: Loader2,
    color: "text-blue-600",
    bgColor: "bg-blue-100",
    dotColor: "bg-blue-500",
  },
  completed: {
    label: "Completed",
    icon: CheckCircle2,
    color: "text-green-600",
    bgColor: "bg-green-100",
    dotColor: "bg-green-500",
  },
  failed: {
    label: "Alert",
    icon: XCircle,
    color: "text-red-600",
    bgColor: "bg-red-100",
    dotColor: "bg-red-500",
  },
} as const;

function getScoreInfo(metrics: EvaluationDetail["metrics"]): { value: string; color: string } {
  if (metrics.length === 0) return { value: "--", color: "text-slate-400" };

  // Use the average of percentage-based metrics as the score
  const percentMetrics = metrics.filter(
    (m) =>
      m.metric_type.includes("faithfulness") ||
      m.metric_type.includes("groundedness") ||
      m.metric_type.includes("completeness") ||
      m.metric_type.includes("support")
  );

  if (percentMetrics.length === 0) {
    // Fallback to first metric
    const first = metrics[0];
    const val = first.metric_type === "mrr" ? first.metric_value.toFixed(3) : `${(first.metric_value * 100).toFixed(1)}%`;
    return { value: val, color: "text-slate-700" };
  }

  const avg = percentMetrics.reduce((sum, m) => sum + m.metric_value, 0) / percentMetrics.length;
  const pct = avg * 100;
  let color = "text-green-600";
  if (pct < 60) color = "text-red-600";
  else if (pct < 80) color = "text-amber-600";

  return { value: `${pct.toFixed(1)}%`, color };
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function EvaluationRunsTable({
  runs,
  notebooks,
  actionRunId = null,
  onRunAction,
}: EvaluationRunsTableProps) {
  if (runs.length === 0) {
    return null;
  }

  // Build a notebook name lookup
  const notebookMap = new Map(notebooks.map((nb) => [nb.id, nb.name]));

  return (
    <div className="mt-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-900">
          Recent Evaluation Runs
        </h2>
        <span className="text-xs text-slate-500">{runs.length} runs</span>
      </div>

      {/* Desktop table */}
      <div className="hidden tablet:block rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50/50">
              <th className="text-left py-3 px-5 text-xs font-semibold uppercase tracking-wider text-slate-500">
                Notebook Name
              </th>
              <th className="text-left py-3 px-5 text-xs font-semibold uppercase tracking-wider text-slate-500">
                Execution Date
              </th>
              <th className="text-left py-3 px-5 text-xs font-semibold uppercase tracking-wider text-slate-500">
                Score
              </th>
              <th className="text-left py-3 px-5 text-xs font-semibold uppercase tracking-wider text-slate-500">
                Status
              </th>
              <th className="text-right py-3 px-5 text-xs font-semibold uppercase tracking-wider text-slate-500">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => {
              const statusConfig = STATUS_CONFIG[run.status];
              const StatusIcon = statusConfig.icon;
              const score = getScoreInfo(run.metrics);
              const notebookName = notebookMap.get(run.notebook_id) || "Unknown Notebook";

              return (
                <tr
                  key={run.id}
                  className="border-b border-slate-50 hover:bg-slate-50/50 transition-colors"
                >
                  <td className="py-4 px-5">
                    <div>
                      <p className="text-sm font-medium text-slate-900 truncate max-w-[200px]" title={notebookName}>
                        {notebookName}
                      </p>
                      <p className="text-xs text-slate-500 truncate max-w-[200px]" title={run.query}>
                        {run.query}
                      </p>
                    </div>
                  </td>
                  <td className="py-4 px-5">
                    <p className="text-sm text-slate-600">{formatDate(run.created_at)}</p>
                  </td>
                  <td className="py-4 px-5">
                    <span className={cn("text-sm font-bold", score.color)}>
                      {score.value}
                    </span>
                  </td>
                  <td className="py-4 px-5">
                    <span
                      className={cn(
                        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium",
                        statusConfig.bgColor,
                        statusConfig.color
                      )}
                    >
                      <span className={cn("h-1.5 w-1.5 rounded-full", statusConfig.dotColor)} />
                      {statusConfig.label}
                    </span>
                  </td>
                  <td className="py-4 px-5 text-right">
                    {run.status === "pending" || run.status === "failed" ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => onRunAction?.(run.id)}
                        disabled={actionRunId !== null}
                        aria-label={`${run.status === "pending" ? "Start" : "Retry"} evaluation`}
                        className="text-xs"
                      >
                        {actionRunId === run.id
                          ? run.status === "pending"
                            ? "Starting..."
                            : "Retrying..."
                          : run.status === "pending"
                            ? "Start"
                            : "Retry"}
                      </Button>
                    ) : (
                      <button
                        type="button"
                        className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100"
                        aria-label="More actions"
                      >
                        <MoreHorizontal className="h-4 w-4" />
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile card layout */}
      <div className="tablet:hidden space-y-3">
        {runs.map((run) => {
          const statusConfig = STATUS_CONFIG[run.status];
          const score = getScoreInfo(run.metrics);
          const notebookName = notebookMap.get(run.notebook_id) || "Unknown Notebook";

          return (
            <div
              key={run.id}
              className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-slate-900 truncate">
                    {notebookName}
                  </p>
                  <p className="text-xs text-slate-500 truncate mt-0.5">
                    {run.query}
                  </p>
                </div>
                <span
                  className={cn(
                    "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium shrink-0",
                    statusConfig.bgColor,
                    statusConfig.color
                  )}
                >
                  <span className={cn("h-1.5 w-1.5 rounded-full", statusConfig.dotColor)} />
                  {statusConfig.label}
                </span>
              </div>

              <div className="mt-3 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div>
                    <p className="text-xs text-slate-500">Score</p>
                    <p className={cn("text-sm font-bold", score.color)}>{score.value}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Date</p>
                    <p className="text-sm text-slate-700">{formatDate(run.created_at)}</p>
                  </div>
                </div>

                {(run.status === "pending" || run.status === "failed") && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => onRunAction?.(run.id)}
                    disabled={actionRunId !== null}
                    className="text-xs"
                  >
                    {actionRunId === run.id
                      ? "..."
                      : run.status === "pending"
                        ? "Start"
                        : "Retry"}
                  </Button>
                )}
              </div>

              {run.error_message && (
                <p className="mt-2 text-xs text-red-600 bg-red-50 rounded-lg px-3 py-1.5">
                  {run.error_message}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

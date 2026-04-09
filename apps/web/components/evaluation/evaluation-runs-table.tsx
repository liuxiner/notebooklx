/**
 * Evaluation Runs Table component.
 *
 * Displays a table of evaluation runs with their metrics.
 *
 * Feature 6.3: Evaluation Dashboard
 */
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { EvaluationDetail } from "@/lib/evaluation-api";
import { Clock, CheckCircle2, XCircle, Loader2 } from "lucide-react";

interface EvaluationRunsTableProps {
  runs: EvaluationDetail[];
  actionRunId?: string | null;
  onRunAction?: (runId: string) => void | Promise<void>;
}

const STATUS_CONFIG = {
  pending: {
    label: "Pending",
    icon: Clock,
    color: "text-slate-600",
    bgColor: "bg-slate-100",
  },
  running: {
    label: "Running",
    icon: Loader2,
    color: "text-blue-600",
    bgColor: "bg-blue-100",
  },
  completed: {
    label: "Completed",
    icon: CheckCircle2,
    color: "text-green-600",
    bgColor: "bg-green-100",
  },
  failed: {
    label: "Failed",
    icon: XCircle,
    color: "text-red-600",
    bgColor: "bg-red-100",
  },
} as const;

const METRIC_LABELS: Record<string, string> = {
  recall_at_5: "Recall@5",
  recall_at_10: "Recall@10",
  recall_at_k: "Recall@K",
  mrr: "MRR",
  citation_support_rate: "Citation Support",
  wrong_citation_rate: "Wrong Citations",
  groundedness: "Groundedness",
  completeness: "Completeness",
  faithfulness: "Faithfulness",
};

function formatMetricValue(metricType: string, value: number): string {
  if (metricType.includes("recall") ||
      metricType.includes("support") ||
      metricType.includes("wrong") ||
      metricType.includes("groundedness") ||
      metricType.includes("completeness") ||
      metricType.includes("faithfulness")) {
    return `${(value * 100).toFixed(1)}%`;
  }
  if (metricType === "mrr") {
    return value.toFixed(3);
  }
  return value.toString();
}

export default function EvaluationRunsTable({
  runs,
  actionRunId = null,
  onRunAction,
}: EvaluationRunsTableProps) {
  if (runs.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-semibold text-slate-900">
          Evaluation Runs ({runs.length})
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-3 px-4 text-sm font-semibold text-slate-700">
                  Query
                </th>
                <th className="text-left py-3 px-4 text-sm font-semibold text-slate-700">
                  Status
                </th>
                <th className="text-left py-3 px-4 text-sm font-semibold text-slate-700">
                  Created
                </th>
                <th className="text-left py-3 px-4 text-sm font-semibold text-slate-700">
                  Metrics
                </th>
                <th className="text-left py-3 px-4 text-sm font-semibold text-slate-700">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => {
                const statusConfig = STATUS_CONFIG[run.status];
                const StatusIcon = statusConfig.icon;

                return (
                  <tr
                    key={run.id}
                    className="border-b border-slate-100 hover:bg-slate-50 transition-colors"
                  >
                    <td className="py-3 px-4">
                      <div className="max-w-md">
                        <p className="text-sm text-slate-900 truncate" title={run.query}>
                          {run.query}
                        </p>
                        {run.error_message && (
                          <p className="text-xs text-red-600 mt-1">
                            {run.error_message}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusConfig.bgColor} ${statusConfig.color}`}
                        >
                          <StatusIcon className="h-3 w-3 mr-1" />
                          {statusConfig.label}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <p className="text-sm text-slate-600">
                        {new Date(run.created_at).toLocaleString()}
                      </p>
                    </td>
                    <td className="py-3 px-4">
                      {run.metrics.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {run.metrics.map((metric, idx) => (
                            <span
                              key={idx}
                              className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-slate-100 text-slate-700"
                            >
                              <span className="font-medium">
                                {METRIC_LABELS[metric.metric_type] || metric.metric_type}:
                              </span>
                              <span className="ml-1 text-slate-600">
                                {formatMetricValue(metric.metric_type, metric.metric_value)}
                              </span>
                            </span>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-slate-400">No metrics</p>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {run.status === "pending" || run.status === "failed" ? (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => onRunAction?.(run.id)}
                          disabled={actionRunId !== null}
                          aria-label={`${run.status === "pending" ? "Start" : "Retry"} ${run.query}`}
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
                        <p className="text-xs text-slate-400">No action</p>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

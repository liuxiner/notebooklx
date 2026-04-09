/**
 * Metrics Overview component.
 *
 * Displays summary cards for key evaluation metrics.
 *
 * Feature 6.3: Evaluation Dashboard
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity, Target, CheckCircle, AlertCircle } from "lucide-react";

interface MetricsOverviewProps {
  summary: Record<string, number>;
}

const METRIC_CONFIG = {
  recall_at_5: {
    label: "Recall@5",
    description: "Relevant chunks in top 5",
    icon: Target,
    color: "text-blue-600",
    bgColor: "bg-blue-50",
    format: (v: number) => `${(v * 100).toFixed(1)}%`,
  },
  recall_at_10: {
    label: "Recall@10",
    description: "Relevant chunks in top 10",
    icon: Target,
    color: "text-blue-600",
    bgColor: "bg-blue-50",
    format: (v: number) => `${(v * 100).toFixed(1)}%`,
  },
  mrr: {
    label: "MRR",
    description: "Mean Reciprocal Rank",
    icon: Activity,
    color: "text-purple-600",
    bgColor: "bg-purple-50",
    format: (v: number) => v.toFixed(3),
  },
  citation_support_rate: {
    label: "Citation Support",
    description: "Supported citations",
    icon: CheckCircle,
    color: "text-green-600",
    bgColor: "bg-green-50",
    format: (v: number) => `${(v * 100).toFixed(1)}%`,
  },
  wrong_citation_rate: {
    label: "Wrong Citations",
    description: "Incorrect citations",
    icon: AlertCircle,
    color: "text-red-600",
    bgColor: "bg-red-50",
    format: (v: number) => `${(v * 100).toFixed(1)}%`,
  },
  groundedness: {
    label: "Groundedness",
    description: "Answer from sources",
    icon: CheckCircle,
    color: "text-emerald-600",
    bgColor: "bg-emerald-50",
    format: (v: number) => `${(v * 100).toFixed(1)}%`,
  },
  completeness: {
    label: "Completeness",
    description: "Answer coverage",
    icon: Activity,
    color: "text-indigo-600",
    bgColor: "bg-indigo-50",
    format: (v: number) => `${(v * 100).toFixed(1)}%`,
  },
  faithfulness: {
    label: "Faithfulness",
    description: "No contradictions",
    icon: CheckCircle,
    color: "text-teal-600",
    bgColor: "bg-teal-50",
    format: (v: number) => `${(v * 100).toFixed(1)}%`,
  },
};

export default function MetricsOverview({ summary }: MetricsOverviewProps) {
  const availableMetrics = Object.keys(METRIC_CONFIG).filter(
    (key) => summary[key] !== undefined
  );

  if (availableMetrics.length === 0) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-center text-slate-500">
            No metrics available yet. Run evaluations to see metric summaries.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {availableMetrics.map((metricKey) => {
        const config = METRIC_CONFIG[metricKey as keyof typeof METRIC_CONFIG];
        const value = summary[metricKey];
        const Icon = config.icon;

        return (
          <Card key={metricKey} className="hover:shadow-md transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-600">
                {config.label}
              </CardTitle>
              <div className={`p-2 rounded-lg ${config.bgColor}`}>
                <Icon className={`h-4 w-4 ${config.color}`} />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-slate-900">
                {config.format(value)}
              </div>
              <p className="text-xs text-slate-500 mt-1">
                {config.description}
              </p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

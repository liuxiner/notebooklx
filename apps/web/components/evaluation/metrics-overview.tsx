/**
 * Metrics Overview component.
 *
 * Displays prominent metric cards for the evaluation dashboard.
 * Shows 3 primary metrics matching the design:
 * - Accuracy (faithfulness)
 * - Retrieval (recall@10)
 * - Citation Quality (citation support rate)
 *
 * Feature 6.3: Evaluation Dashboard
 */
import {
  BarChart3,
  Target,
  ShieldCheck,
} from "lucide-react";

interface MetricsOverviewProps {
  summary: Record<string, number>;
}

interface MetricCard {
  label: string;
  value: string;
  sublabel: string;
  color: string;
  bgColor: string;
  icon: typeof BarChart3;
}

function formatPercent(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

export default function MetricsOverview({ summary }: MetricsOverviewProps) {
  const faithfulness = summary.faithfulness;
  const recall10 = summary.recall_at_10;
  const citationSupport = summary.citation_support_rate;

  const cards: MetricCard[] = [
    {
      label: "Accuracy",
      value: faithfulness !== undefined ? formatPercent(faithfulness) : "--",
      sublabel: "Faithfulness score",
      color: "text-emerald-600",
      bgColor: "bg-emerald-50",
      icon: ShieldCheck,
    },
    {
      label: "Retrieval",
      value: recall10 !== undefined ? formatPercent(recall10) : "--",
      sublabel: "Recall@10 rate",
      color: "text-blue-600",
      bgColor: "bg-blue-50",
      icon: Target,
    },
    {
      label: "Citation Quality",
      value: citationSupport !== undefined ? formatPercent(citationSupport) : "--",
      sublabel: "Support rate",
      color: "text-violet-600",
      bgColor: "bg-violet-50",
      icon: BarChart3,
    },
  ];

  return (
    <div className="grid grid-cols-1 tablet:grid-cols-3 gap-4">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <div
            key={card.label}
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  {card.label}
                </p>
                <p className={`mt-2 text-3xl font-bold ${card.color}`}>
                  {card.value}
                </p>
                <p className="mt-1 text-xs text-slate-500">{card.sublabel}</p>
              </div>
              <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${card.bgColor}`}>
                <Icon className={`h-5 w-5 ${card.color}`} />
              </div>
            </div>

            {/* Mini bar chart placeholder */}
            <div className="mt-4 flex h-8 items-end gap-[3px]">
              {[40, 65, 50, 80, 55, 70, 90, 60, 75, 85, 65, 70].map((h, i) => (
                <div
                  key={i}
                  className={`flex-1 rounded-sm ${card.bgColor} opacity-60`}
                  style={{ height: `${h}%` }}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

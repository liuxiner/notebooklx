/**
 * Evaluation Filter Controls component.
 *
 * Inline filter bar matching the design: date range + notebook dropdown.
 *
 * Feature 6.3: Evaluation Dashboard
 * AC: Filterable by notebook, time range
 */
"use client";

import { X, Calendar } from "lucide-react";
import type { EvaluationFilters as FilterType } from "@/lib/evaluation-api";
import type { Notebook } from "@/lib/api";

interface EvaluationFilterControlsProps {
  filters: FilterType;
  notebooks: Notebook[];
  notebooksLoading: boolean;
  notebooksError: string | null;
  onChange: (filters: FilterType) => void;
}

export default function EvaluationFilterControls({
  filters,
  notebooks,
  notebooksLoading,
  notebooksError,
  onChange,
}: EvaluationFilterControlsProps) {
  const updateFilter = (key: keyof FilterType, value: string | Date | undefined) => {
    const updated = { ...filters };

    if (value === undefined || value === "") {
      delete updated[key];
    } else {
      if (key === "metric_types") return;
      if (value instanceof Date) {
        (updated as Record<string, unknown>)[key] = value.toISOString();
      } else {
        (updated as Record<string, unknown>)[key] = value;
      }
    }

    onChange(updated);
  };

  const clearFilters = () => {
    onChange({});
  };

  const hasActiveFilters = Object.keys(filters).length > 0;

  return (
    <div className="flex flex-col gap-3 mb-4 tablet:flex-row tablet:items-center tablet:flex-wrap">
      {/* Date range filters */}
      <div className="flex items-center gap-2">
        <div className="relative flex items-center">
          <Calendar className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-slate-400" />
          <input
            type="date"
            value={
              filters.start_date
                ? new Date(filters.start_date).toISOString().split("T")[0]
                : ""
            }
            onChange={(e) =>
              updateFilter("start_date", e.target.value ? new Date(e.target.value) : undefined)
            }
            aria-label="Start date"
            className="h-9 rounded-lg border border-slate-200 bg-white pl-8 pr-3 text-xs text-slate-700 outline-none focus:border-primary/40 focus:ring-2 focus:ring-primary/10"
            placeholder="From"
          />
        </div>
        <span className="text-xs text-slate-400">-</span>
        <div className="relative flex items-center">
          <Calendar className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-slate-400" />
          <input
            type="date"
            value={
              filters.end_date
                ? new Date(filters.end_date).toISOString().split("T")[0]
                : ""
            }
            onChange={(e) =>
              updateFilter("end_date", e.target.value ? new Date(e.target.value) : undefined)
            }
            aria-label="End date"
            className="h-9 rounded-lg border border-slate-200 bg-white pl-8 pr-3 text-xs text-slate-700 outline-none focus:border-primary/40 focus:ring-2 focus:ring-primary/10"
            placeholder="To"
          />
        </div>
      </div>

      {/* Notebook filter */}
      <select
        aria-label="Notebook filter"
        value={filters.notebook_id || ""}
        onChange={(e) => updateFilter("notebook_id", e.target.value || undefined)}
        disabled={notebooksLoading || Boolean(notebooksError) || notebooks.length === 0}
        className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-xs text-slate-700 shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <option value="">
          {notebooksLoading
            ? "Loading..."
            : notebooks.length === 0
              ? "No notebooks"
              : "All Research Notebooks"}
        </option>
        {notebooks.map((notebook) => (
          <option key={notebook.id} value={notebook.id}>
            {notebook.name}
          </option>
        ))}
      </select>

      {/* Clear button */}
      {hasActiveFilters && (
        <button
          type="button"
          onClick={clearFilters}
          className="inline-flex items-center gap-1 h-9 rounded-lg px-3 text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
        >
          <X className="h-3 w-3" />
          Clear
        </button>
      )}

      {notebooksError && (
        <p className="text-xs text-red-600">{notebooksError}</p>
      )}
    </div>
  );
}

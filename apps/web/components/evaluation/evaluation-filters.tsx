/**
 * Evaluation Filter Controls component.
 *
 * Provides filter controls for the evaluation dashboard.
 *
 * Feature 6.3: Evaluation Dashboard
 * AC: Filterable by notebook, time range
 */
"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";
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
      if (key === "metric_types") {
        // Skip metric_types for now - not implemented in UI
        return;
      }
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
    <Card className="mb-6">
      <CardContent className="pt-6">
        <div className="flex flex-col sm:flex-row gap-4 items-start">
          {/* Notebook Filter */}
          <div className="flex-1 w-full">
            <Label htmlFor="notebook-filter" className="text-sm font-medium text-slate-700 mb-2">
              Notebook Filter
            </Label>
            <select
              id="notebook-filter"
              aria-label="Notebook filter"
              value={filters.notebook_id || ""}
              onChange={(e) => updateFilter("notebook_id", e.target.value || undefined)}
              disabled={notebooksLoading || Boolean(notebooksError) || notebooks.length === 0}
              className="flex h-10 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <option value="">
                {notebooksLoading
                  ? "Loading notebooks..."
                  : notebooks.length === 0
                    ? "No notebooks available"
                    : "All notebooks"}
              </option>
              {notebooks.map((notebook) => (
                <option key={notebook.id} value={notebook.id}>
                  {notebook.name}
                </option>
              ))}
            </select>
            <p className="mt-1.5 text-xs text-slate-500">
              {notebooksError
                ? notebooksError
                : notebooks.length === 0
                  ? "Create a notebook before filtering evaluation runs."
                  : "Scope dashboard metrics to one notebook or keep all notebooks selected."}
            </p>
          </div>

          {/* Start Date Filter */}
          <div className="flex-1 w-full">
            <Label htmlFor="start-date-filter" className="text-sm font-medium text-slate-700 mb-1.5">
              Start Date
            </Label>
            <Input
              id="start-date-filter"
              type="date"
              value={
                filters.start_date
                  ? new Date(filters.start_date).toISOString().split("T")[0]
                  : ""
              }
              onChange={(e) =>
                updateFilter(
                  "start_date",
                  e.target.value ? new Date(e.target.value) : undefined
                )
              }
              className="w-full"
            />
          </div>

          {/* End Date Filter */}
          <div className="flex-1 w-full">
            <Label htmlFor="end-date-filter" className="text-sm font-medium text-slate-700 mb-1.5">
              End Date
            </Label>
            <Input
              id="end-date-filter"
              type="date"
              value={
                filters.end_date
                  ? new Date(filters.end_date).toISOString().split("T")[0]
                  : ""
              }
              onChange={(e) =>
                updateFilter(
                  "end_date",
                  e.target.value ? new Date(e.target.value) : undefined
                )
              }
              className="w-full"
            />
          </div>

          {/* Clear Button */}
          {hasActiveFilters && (
            <Button
              variant="outline"
              onClick={clearFilters}
              className="w-full sm:w-auto"
            >
              <X className="h-4 w-4 mr-2" />
              Clear Filters
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

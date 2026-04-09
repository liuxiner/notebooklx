# Evaluation Dashboard Components

Frontend components for the NotebookLX evaluation dashboard.

## Overview

The evaluation dashboard provides a visual interface for tracking and analyzing retrieval, citation, and answer quality metrics across your notebooks.

## Components

### EvaluationDashboard (`app/evaluation/page.tsx`)

Main page component that:
- Fetches and displays evaluation metrics
- Provides filter controls for notebook and date range
- Shows metrics overview cards and evaluation runs table
- Handles CSV export

**Usage:**
```tsx
import EvaluationDashboard from "@/app/evaluation/page";

// Access at /evaluation route
```

### MetricsOverview (`components/evaluation/metrics-overview.tsx`)

Displays summary cards for key metrics:
- Recall@5 and Recall@10
- Mean Reciprocal Rank (MRR)
- Citation Support Rate
- Wrong Citation Rate
- Groundedness, Completeness, Faithfulness

**Props:**
```tsx
interface MetricsOverviewProps {
  summary: Record<string, number>; // Summary metrics from API
}
```

**Example:**
```tsx
<MetricsOverview
  summary={{
    recall_at_5: 0.8,
    mrr: 0.75,
    citation_support_rate: 0.95
  }}
/>
```

### EvaluationFilterControls (`components/evaluation/evaluation-filters.tsx`)

Filter controls for the evaluation dashboard:
- Filter by notebook ID
- Filter by date range (start/end dates)
- Clear filters button

**Props:**
```tsx
interface EvaluationFilterControlsProps {
  filters: EvaluationFilters;
  onChange: (filters: EvaluationFilters) => void;
}
```

**Example:**
```tsx
const [filters, setFilters] = useState<EvaluationFilters>({});

<EvaluationFilterControls
  filters={filters}
  onChange={setFilters}
/>
```

### EvaluationRunsTable (`components/evaluation/evaluation-runs-table.tsx`)

Table displaying evaluation runs with:
- Query text
- Status indicator (pending, running, completed, failed)
- Creation timestamp
- Associated metrics

**Props:**
```tsx
interface EvaluationRunsTableProps {
  runs: EvaluationDetail[];
}
```

**Example:**
```tsx
<EvaluationRunsTable
  runs={evaluationRuns}
/>
```

## API Client (`lib/evaluation-api.ts`)

TypeScript API client for evaluation endpoints.

### Methods

#### `list(filters?: EvaluationFilters)`
List evaluation runs with optional filters.

```tsx
const data = await evaluationApi.list({
  notebook_id: "uuid",
  start_date: "2024-01-01T00:00:00Z",
  end_date: "2024-12-31T23:59:59Z"
});
```

#### `get(runId: string)`
Get a single evaluation run with metrics.

```tsx
const evaluation = await evaluationApi.get("run-uuid");
```

#### `create(data: EvaluationCreate)`
Create a new evaluation run.

```tsx
const newRun = await evaluationApi.create({
  notebook_id: "notebook-uuid",
  query: "What is machine learning?",
  ground_truth_chunk_ids: ["chunk-uuid-1", "chunk-uuid-2"]
});
```

#### `start(runId: string)`
Start an evaluation run.

```tsx
const started = await evaluationApi.start("run-uuid");
```

#### `exportCsv(filters?: EvaluationFilters)`
Export metrics as CSV file.

```tsx
const blob = await evaluationApi.exportCsv({
  notebook_id: "notebook-uuid"
});
// Browser will download the file
```

## Type Definitions

```tsx
interface MetricValue {
  metric_type: string;
  metric_value: number;
  metadata: Record<string, unknown> | null;
}

interface EvaluationDetail {
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

interface MetricsListResponse {
  evaluation_runs: EvaluationDetail[];
  summary: Record<string, number>;
}

interface EvaluationFilters {
  notebook_id?: string;
  start_date?: string;
  end_date?: string;
  metric_types?: string[];
}
```

## Usage Example

Complete example of using the evaluation dashboard:

```tsx
"use client";

import { useState, useEffect } from "react";
import { evaluationApi, type MetricsListResponse } from "@/lib/evaluation-api";
import MetricsOverview from "@/components/evaluation/metrics-overview";
import EvaluationFilterControls from "@/components/evaluation/evaluation-filters";
import EvaluationRunsTable from "@/components/evaluation/evaluation-runs-table";

export default function MyEvaluationPage() {
  const [data, setData] = useState<MetricsListResponse | null>(null);
  const [filters, setFilters] = useState({});

  useEffect(() => {
    evaluationApi.list(filters).then(setData);
  }, [filters]);

  if (!data) return <div>Loading...</div>;

  return (
    <div>
      <EvaluationFilterControls
        filters={filters}
        onChange={setFilters}
      />
      <MetricsOverview summary={data.summary} />
      <EvaluationRunsTable runs={data.evaluation_runs} />
    </div>
  );
}
```

## Styling

Components follow the design system:
- Uses shadcn/ui components (Card, Button, Input, Label)
- Tailwind CSS for styling
- Lucide React icons
- Responsive design with mobile/tablet breakpoints
- Color-coded status indicators

## Metric Display Formats

| Metric Type | Format | Color |
|------------|--------|-------|
| Recall@K | Percentage (80.0%) | Blue |
| MRR | Decimal (0.750) | Purple |
| Citation Support | Percentage (95.0%) | Green |
| Wrong Citations | Percentage (5.0%) | Red |
| Groundedness | Percentage (90.0%) | Emerald |
| Completeness | Percentage (85.0%) | Indigo |
| Faithfulness | Percentage (95.0%) | Teal |

## Status Indicators

| Status | Icon | Color |
|--------|------|-------|
| Pending | Clock | Slate |
| Running | Loader2 (spinning) | Blue |
| Completed | CheckCircle2 | Green |
| Failed | XCircle | Red |

## Error Handling

Components handle errors gracefully:
- API errors display in error banner
- Empty states show helpful messages
- Loading states prevent interaction
- Failed evaluations show error messages

## Accessibility

- All interactive elements are keyboard accessible
- Proper ARIA labels on icons
- Color contrast meets WCAG AA standards
- Status indicators use both color and icons
- Table headers are properly labeled

## Future Enhancements

Potential improvements:
- **Charts**: Add line charts for metric trends over time
- **Comparison view**: Compare metrics across notebooks
- **Real-time updates**: Stream evaluation progress
- **Drill-down**: Click to view individual evaluation details
- **Annotations**: Add notes to evaluation runs
- **Export formats**: Support JSON and Excel exports

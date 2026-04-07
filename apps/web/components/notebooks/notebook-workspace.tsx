"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import {
  sourcesApi,
  type NotebookSource,
  type SourceIngestionStatus,
  type SourceStatus,
  type SourceType,
} from "@/lib/api";

interface NotebookWorkspaceProps {
  notebookId: string;
}

interface WorkspaceSource extends NotebookSource {
  ingestion: SourceIngestionStatus | null;
}

const statusStyles: Record<SourceStatus, string> = {
  pending: "border-slate-200 bg-slate-100 text-slate-900",
  processing: "border-sky-200 bg-sky-50 text-sky-900",
  ready: "border-emerald-200 bg-emerald-50 text-emerald-900",
  failed: "border-rose-200 bg-rose-50 text-rose-900",
};

const sourceTypeLabels: Record<SourceType, string> = {
  pdf: "PDF",
  text: "TEXT",
  url: "URL",
  youtube: "YOUTUBE",
  audio: "AUDIO",
  gdocs: "GDOCS",
};

function formatDate(dateString: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(dateString));
}

function formatStatusLabel(status: SourceStatus): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function formatProgressMessage(source: WorkspaceSource): string | null {
  const progress = source.ingestion?.progress;
  if (!progress || typeof progress !== "object") {
    return null;
  }

  const currentStep =
    typeof progress.current_step === "string" ? progress.current_step : null;
  const message = typeof progress.message === "string" ? progress.message : null;
  const embeddedChunks =
    typeof progress.embedded_chunks === "number" ? progress.embedded_chunks : null;
  const totalChunks =
    typeof progress.total_chunks === "number" ? progress.total_chunks : null;
  const percentage =
    typeof progress.percentage === "number" ? progress.percentage : null;

  if (
    currentStep === "embedding" &&
    embeddedChunks !== null &&
    totalChunks !== null
  ) {
    return `Embedding ${embeddedChunks} of ${totalChunks} chunks`;
  }

  if (message) {
    return message;
  }

  if (currentStep && percentage !== null) {
    const label = currentStep.charAt(0).toUpperCase() + currentStep.slice(1);
    return `${label} ${percentage}%`;
  }

  if (currentStep) {
    return `Current step: ${currentStep}`;
  }

  return null;
}

function getEffectiveStatus(source: WorkspaceSource): SourceStatus {
  return source.ingestion?.status ?? source.status;
}

function getFailureMessage(source: WorkspaceSource): string | null {
  return source.ingestion?.error_message ?? null;
}

async function buildWorkspaceSources(
  notebookId: string
): Promise<WorkspaceSource[]> {
  const sources = await sourcesApi.list(notebookId);

  const statuses = await Promise.all(
    sources.map(async (source) => {
      try {
        const status = await sourcesApi.getStatus(source.id);
        return [source.id, status] as const;
      } catch {
        return [source.id, null] as const;
      }
    })
  );

  const statusMap = new Map(statuses);

  return sources.map((source) => ({
    ...source,
    ingestion: statusMap.get(source.id) ?? null,
  }));
}

export function NotebookWorkspace({ notebookId }: NotebookWorkspaceProps) {
  const [sources, setSources] = useState<WorkspaceSource[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    async function loadSources() {
      try {
        setIsLoading(true);
        setErrorMessage(null);

        const nextSources = await buildWorkspaceSources(notebookId);

        if (isActive) {
          setSources(nextSources);
        }
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "Failed to load notebook sources.";

        if (isActive) {
          setSources([]);
          setErrorMessage(message);
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    }

    void loadSources();

    return () => {
      isActive = false;
    };
  }, [notebookId]);

  async function refreshSources() {
    try {
      setIsRefreshing(true);
      setErrorMessage(null);
      setSources(await buildWorkspaceSources(notebookId));
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Failed to refresh notebook sources.";
      setErrorMessage(message);
    } finally {
      setIsRefreshing(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card className="border-slate-200 bg-white/90 shadow-sm">
        <CardHeader className="gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle className="text-xl">Notebook sources</CardTitle>
            <CardDescription className="mt-2 max-w-2xl text-sm leading-6">
              Track ingestion status for every source attached to this notebook.
            </CardDescription>
          </div>
          <Button
            variant="outline"
            onClick={() => void refreshSources()}
            disabled={isLoading || isRefreshing}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex min-h-40 items-center justify-center rounded-2xl border border-dashed border-border bg-slate-50/70">
              <Spinner size="lg" />
            </div>
          ) : errorMessage ? (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
              {errorMessage}
            </div>
          ) : sources.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border bg-slate-50/80 p-6">
              <p className="text-base font-semibold text-slate-900">No sources yet</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Add a PDF, pasted text, or URL to start grounding this notebook.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {sources.map((source) => {
                const status = getEffectiveStatus(source);
                const failureMessage = status === "failed" ? getFailureMessage(source) : null;
                const progressMessage =
                  status === "failed" ? null : formatProgressMessage(source);

                return (
                  <article
                    key={source.id}
                    className="rounded-2xl border border-border bg-slate-50/80 p-4"
                  >
                    <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                      <div className="min-w-0">
                        <h3 className="truncate text-base font-semibold text-slate-950">
                          {source.title}
                        </h3>
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs uppercase tracking-[0.16em] text-slate-500">
                          <span>{sourceTypeLabels[source.source_type] ?? source.source_type}</span>
                          <span aria-hidden="true">•</span>
                          <span>{`Added ${formatDate(source.created_at)}`}</span>
                        </div>
                      </div>
                      <span
                        className={`inline-flex w-fit rounded-full border px-3 py-1 text-xs font-semibold ${statusStyles[status]}`}
                      >
                        {formatStatusLabel(status)}
                      </span>
                    </div>

                    {progressMessage ? (
                      <p className="mt-3 text-sm text-slate-700">{progressMessage}</p>
                    ) : null}

                    {failureMessage ? (
                      <p className="mt-3 text-sm text-rose-800">{failureMessage}</p>
                    ) : null}
                  </article>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="border-slate-200 bg-white/90 shadow-sm">
          <CardHeader>
            <CardTitle className="text-xl">Notebook summary</CardTitle>
            <CardDescription>
              Reserved for Feature 4.1 once summaries are generated from ready sources.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-2xl border border-dashed border-border bg-slate-50/80 p-4 text-sm text-muted-foreground">
              Summary generation has not been enabled for this notebook yet.
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200 bg-white/90 shadow-sm">
          <CardHeader>
            <CardTitle className="text-xl">Generated assets</CardTitle>
            <CardDescription>
              Reserved for Phase 5 outputs such as briefings, FAQs, and study guides.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-2xl border border-dashed border-border bg-slate-50/80 p-4 text-sm text-muted-foreground">
              Derived content will appear here after asset generation ships.
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

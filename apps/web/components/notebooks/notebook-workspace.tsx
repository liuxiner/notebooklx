"use client";

import { useEffect, useState } from "react";
import { Plus, RefreshCw, Trash2 } from "lucide-react";

import { SourceDeleteDialog } from "@/components/notebooks/source-delete-dialog";
import { SourceManagementDialog } from "@/components/notebooks/source-management-dialog";
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

const INGESTION_POLL_INTERVAL_MS = 1500;

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

function isResolvedStatus(status: SourceStatus): boolean {
  return status === "ready" || status === "failed";
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
  const [isSourceDialogOpen, setIsSourceDialogOpen] = useState(false);
  const [isSubmittingSource, setIsSubmittingSource] = useState(false);
  const [trackedIngestionIds, setTrackedIngestionIds] = useState<string[]>([]);
  const [sourcePendingDelete, setSourcePendingDelete] = useState<WorkspaceSource | null>(
    null
  );
  const [isDeletingSource, setIsDeletingSource] = useState(false);
  const [deleteErrorMessage, setDeleteErrorMessage] = useState<string | null>(null);
  const sourceCounts = sources.reduce(
    (counts, source) => {
      counts.total += 1;
      counts[getEffectiveStatus(source)] += 1;
      return counts;
    },
    {
      total: 0,
      pending: 0,
      processing: 0,
      ready: 0,
      failed: 0,
    }
  );

  function reconcileTrackedIngestions(nextSources: WorkspaceSource[]) {
    setTrackedIngestionIds((currentIds) =>
      currentIds.filter((sourceId) => {
        const source = nextSources.find((candidate) => candidate.id === sourceId);
        return source ? !isResolvedStatus(getEffectiveStatus(source)) : false;
      })
    );
  }

  async function loadSources(options: { initial: boolean; silent?: boolean }) {
    const { initial, silent = false } = options;

    try {
      if (initial) {
        setIsLoading(true);
      } else {
        setIsRefreshing(true);
      }

      if (!silent) {
        setErrorMessage(null);
      }

      const nextSources = await buildWorkspaceSources(notebookId);
      setErrorMessage(null);
      setSources(nextSources);
      reconcileTrackedIngestions(nextSources);

      return nextSources;
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : initial
            ? "Failed to load notebook sources."
            : "Failed to refresh notebook sources.";

      if (initial) {
        setSources([]);
      }

      if (!silent) {
        setErrorMessage(message);
      }
      throw error;
    } finally {
      if (initial) {
        setIsLoading(false);
      } else {
        setIsRefreshing(false);
      }
    }
  }

  useEffect(() => {
    let isActive = true;

    async function hydrateSources() {
      try {
        const nextSources = await buildWorkspaceSources(notebookId);

        if (!isActive) {
          return;
        }

        setErrorMessage(null);
        setSources(nextSources);
        setTrackedIngestionIds([]);
      } catch (error) {
        if (!isActive) {
          return;
        }

        const message =
          error instanceof Error
            ? error.message
            : "Failed to load notebook sources.";

        setSources([]);
        setErrorMessage(message);
      } finally {
        if (!isActive) {
          return;
        }

        setIsLoading(false);
      }
    }

    setIsLoading(true);
    setTrackedIngestionIds([]);
    void hydrateSources();

    return () => {
      isActive = false;
    };
  }, [notebookId]);

  useEffect(() => {
    if (trackedIngestionIds.length === 0 || isLoading || isRefreshing) {
      return;
    }

    const hasPendingTrackedIngestions = trackedIngestionIds.some((sourceId) => {
      const source = sources.find((candidate) => candidate.id === sourceId);
      return !source || !isResolvedStatus(getEffectiveStatus(source));
    });

    if (!hasPendingTrackedIngestions) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      void loadSources({ initial: false, silent: true }).catch(() => undefined);
    }, INGESTION_POLL_INTERVAL_MS);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [isLoading, isRefreshing, notebookId, sources, trackedIngestionIds]);

  async function refreshSources() {
    try {
      await loadSources({ initial: false });
    } catch {}
  }

  async function handleSourceMutation(action: () => Promise<unknown>) {
    try {
      setIsSubmittingSource(true);
      await action();
      await loadSources({ initial: false });
      setIsSourceDialogOpen(false);
    } finally {
      setIsSubmittingSource(false);
    }
  }

  function handleDeleteDialogChange(open: boolean) {
    if (!open) {
      setSourcePendingDelete(null);
      setDeleteErrorMessage(null);
      return;
    }
  }

  async function handleDeleteSource() {
    if (!sourcePendingDelete) {
      return;
    }

    try {
      setIsDeletingSource(true);
      setDeleteErrorMessage(null);
      await sourcesApi.delete(notebookId, sourcePendingDelete.id);
      setSources((currentSources) =>
        currentSources.filter((source) => source.id !== sourcePendingDelete.id)
      );
      setSourcePendingDelete(null);
    } catch (error) {
      setDeleteErrorMessage(
        error instanceof Error ? error.message : "Failed to delete this source."
      );
    } finally {
      setIsDeletingSource(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card className="overflow-hidden border-slate-200 bg-white/92 shadow-[0_18px_45px_rgba(15,23,42,0.06)]">
        <CardHeader className="gap-5 border-b border-slate-200/80 bg-[linear-gradient(180deg,rgba(248,250,252,0.92),rgba(255,255,255,0.98))] sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
              Sources first
            </p>
            <CardTitle className="mt-3 text-2xl">Notebook sources</CardTitle>
            <CardDescription className="mt-2 max-w-2xl text-sm leading-6">
              Track ingestion status for every source attached to this notebook.
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() => setIsSourceDialogOpen(true)}
              disabled={isLoading || isRefreshing || isSubmittingSource}
            >
              <Plus className="mr-2 h-4 w-4" />
              Add source
            </Button>
            <Button
              variant="outline"
              onClick={() => void refreshSources()}
              disabled={isLoading || isRefreshing || isSubmittingSource}
            >
              <RefreshCw
                className={`mr-2 h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`}
              />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-6 pt-6">
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-600">
              {sourceCounts.total} total
            </span>
            <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-amber-800">
              {sourceCounts.processing} processing
            </span>
            <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-800">
              {sourceCounts.ready} ready
            </span>
            <span className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-rose-800">
              {sourceCounts.failed} failed
            </span>
          </div>

          {isLoading ? (
            <div className="flex min-h-40 items-center justify-center rounded-[1.5rem] border border-dashed border-border bg-slate-50/70">
              <Spinner size="lg" />
            </div>
          ) : errorMessage ? (
            <div className="rounded-[1.5rem] border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
              {errorMessage}
            </div>
          ) : sources.length === 0 ? (
            <div className="rounded-[1.5rem] border border-dashed border-border bg-slate-50/80 p-6">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                Truth boundary
              </p>
              <p className="mt-3 text-base font-semibold text-slate-900">No sources yet</p>
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
                    className="rounded-[1.5rem] border border-slate-200 bg-slate-50/80 p-5 shadow-[0_1px_3px_rgba(15,23,42,0.04)]"
                  >
                    <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                      <div className="min-w-0">
                        <h3 className="truncate text-lg font-semibold tracking-tight text-slate-950">
                          {source.title}
                        </h3>
                        <div className="mt-3 flex flex-wrap items-center gap-2 font-mono text-[11px] uppercase tracking-[0.16em] text-slate-500">
                          <span>{sourceTypeLabels[source.source_type] ?? source.source_type}</span>
                          <span aria-hidden="true">•</span>
                          <span>{`Added ${formatDate(source.created_at)}`}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 self-start">
                        <span
                          className={`inline-flex w-fit rounded-full border px-3 py-1 text-xs font-semibold ${statusStyles[status]}`}
                        >
                          {formatStatusLabel(status)}
                        </span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="text-slate-600 hover:bg-rose-50 hover:text-rose-700"
                          onClick={() => {
                            setDeleteErrorMessage(null);
                            setSourcePendingDelete(source);
                          }}
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Delete source
                        </Button>
                      </div>
                    </div>

                    {progressMessage ? (
                      <div className="mt-4 rounded-2xl border border-slate-200 bg-white/80 px-4 py-3 text-sm text-slate-700">
                        {progressMessage}
                      </div>
                    ) : null}

                    {failureMessage ? (
                      <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
                        {failureMessage}
                      </div>
                    ) : null}
                  </article>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <SourceManagementDialog
        open={isSourceDialogOpen}
        onOpenChange={setIsSourceDialogOpen}
        isSubmitting={isSubmittingSource}
        onUpload={({ file, title }) =>
          handleSourceMutation(async () => {
            const source = await sourcesApi.upload(notebookId, { file, title });

            try {
              await sourcesApi.ingest(source.id);
              setTrackedIngestionIds((currentIds) =>
                currentIds.includes(source.id)
                  ? currentIds
                  : [...currentIds, source.id]
              );
            } catch (error) {
              await loadSources({ initial: false }).catch(() => undefined);
              throw error;
            }
          })
        }
        onCreateText={({ title, content }) =>
          handleSourceMutation(() =>
            sourcesApi.createText(notebookId, {
              title,
              content,
            })
          )
        }
        onCreateUrl={({ title, url }) =>
          handleSourceMutation(() =>
            sourcesApi.createUrl(notebookId, {
              title,
              url,
            })
          )
        }
      />

      <SourceDeleteDialog
        open={sourcePendingDelete !== null}
        onOpenChange={handleDeleteDialogChange}
        sourceTitle={sourcePendingDelete?.title ?? null}
        onConfirm={handleDeleteSource}
        isDeleting={isDeletingSource}
        errorMessage={deleteErrorMessage}
      />

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="border-slate-200 bg-white/90 shadow-sm">
          <CardHeader>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              Reserved
            </p>
            <CardTitle className="text-xl">Notebook summary</CardTitle>
            <CardDescription>
              Reserved for Feature 4.1 once summaries are generated from ready sources.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-[1.5rem] border border-dashed border-border bg-slate-50/80 p-4 text-sm text-muted-foreground">
              Summary generation has not been enabled for this notebook yet.
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200 bg-white/90 shadow-sm">
          <CardHeader>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              Reserved
            </p>
            <CardTitle className="text-xl">Generated assets</CardTitle>
            <CardDescription>
              Reserved for Phase 5 outputs such as briefings, FAQs, and study guides.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-[1.5rem] border border-dashed border-border bg-slate-50/80 p-4 text-sm text-muted-foreground">
              Derived content will appear here after asset generation ships.
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

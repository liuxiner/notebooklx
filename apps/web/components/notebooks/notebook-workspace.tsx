"use client";

import { useEffect, useRef, useState } from "react";
import { Eye, Plus, RefreshCw, Trash2 } from "lucide-react";

import { SourceDeleteDialog } from "@/components/notebooks/source-delete-dialog";
import { SourceManagementDialog } from "@/components/notebooks/source-management-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import {
  sourcesApi,
  type NotebookSource,
  type SourceSnapshotSummary,
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

function getSnapshotUnavailableMessage(source: WorkspaceSource): string {
  const status = getEffectiveStatus(source);

  if (status === "failed") {
    return "Snapshot preview is unavailable because ingestion failed.";
  }

  if (status === "processing" || status === "pending") {
    return "Snapshot preview becomes available after ingestion finishes.";
  }

  return "Snapshot preview is not available for this source yet.";
}

async function buildWorkspaceSources(
  notebookId: string
): Promise<WorkspaceSource[]> {
  const sources = await sourcesApi.list(notebookId);

  if (sources.length === 0) {
    return [];
  }

  const { statuses } = await sourcesApi.bulkStatus(sources.map((source) => source.id));
  const statusMap = new Map(statuses.map((status) => [status.source_id, status] as const));

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
  const [activeSnapshotSourceId, setActiveSnapshotSourceId] = useState<string | null>(null);
  const [snapshotLoadingSourceId, setSnapshotLoadingSourceId] = useState<string | null>(null);
  const [snapshotSummaries, setSnapshotSummaries] = useState<
    Record<string, SourceSnapshotSummary>
  >({});
  const [snapshotErrorMessages, setSnapshotErrorMessages] = useState<
    Record<string, string>
  >({});
  const snapshotPreviewRefs = useRef<Record<string, HTMLDivElement | null>>({});
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
    setActiveSnapshotSourceId(null);
    setSnapshotLoadingSourceId(null);
    setSnapshotSummaries({});
    setSnapshotErrorMessages({});
    void hydrateSources();

    return () => {
      isActive = false;
    };
  }, [notebookId]);

  useEffect(() => {
    if (!activeSnapshotSourceId) {
      return;
    }

    function handlePointerDown(event: PointerEvent) {
      const previewContainer = snapshotPreviewRefs.current[activeSnapshotSourceId];
      if (
        previewContainer &&
        event.target instanceof Node &&
        !previewContainer.contains(event.target)
      ) {
        setActiveSnapshotSourceId(null);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setActiveSnapshotSourceId(null);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [activeSnapshotSourceId]);

  useEffect(() => {
    if (
      activeSnapshotSourceId &&
      !sources.some((source) => source.id === activeSnapshotSourceId)
    ) {
      setActiveSnapshotSourceId(null);
    }
  }, [activeSnapshotSourceId, sources]);

  useEffect(() => {
    if (trackedIngestionIds.length === 0 || isLoading || isRefreshing) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      void refreshTrackedIngestionStatuses().catch(() => undefined);
    }, INGESTION_POLL_INTERVAL_MS);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [isLoading, isRefreshing, trackedIngestionIds]);

  async function refreshSources() {
    try {
      await loadSources({ initial: false });
    } catch {}
  }

  async function refreshTrackedIngestionStatuses() {
    if (trackedIngestionIds.length === 0) {
      return;
    }

    const { statuses, has_pending_sources } = await sourcesApi.bulkStatus(trackedIngestionIds);
    const statusMap = new Map(statuses.map((status) => [status.source_id, status] as const));

    setSources((currentSources) =>
      currentSources.map((source) =>
        statusMap.has(source.id)
          ? {
              ...source,
              ingestion: statusMap.get(source.id) ?? source.ingestion,
            }
          : source
      )
    );
    setTrackedIngestionIds(
      has_pending_sources
        ? statuses
            .filter((status) => !isResolvedStatus(status.status))
            .map((status) => status.source_id)
        : []
    );
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

  function handleSnapshotPreviewBlur(
    sourceId: string,
    event: React.FocusEvent<HTMLDivElement>
  ) {
    const previewContainer = snapshotPreviewRefs.current[sourceId];
    if (!previewContainer) {
      return;
    }

    const nextFocusedElement = event.relatedTarget;
    if (nextFocusedElement instanceof Node && previewContainer.contains(nextFocusedElement)) {
      return;
    }

    setActiveSnapshotSourceId((currentSourceId) =>
      currentSourceId === sourceId ? null : currentSourceId
    );
  }

  async function handleSourceSnapshotToggle(source: WorkspaceSource) {
    const nextIsClosing = activeSnapshotSourceId === source.id;
    setActiveSnapshotSourceId(nextIsClosing ? null : source.id);

    if (nextIsClosing || getEffectiveStatus(source) !== "ready") {
      return;
    }

    if (snapshotSummaries[source.id]) {
      return;
    }

    setSnapshotLoadingSourceId(source.id);
    setSnapshotErrorMessages((currentMessages) => {
      const nextMessages = { ...currentMessages };
      delete nextMessages[source.id];
      return nextMessages;
    });

    try {
      const summary = await sourcesApi.getSnapshotSummary(notebookId, source.id);
      setSnapshotSummaries((currentSummaries) => ({
        ...currentSummaries,
        [source.id]: summary,
      }));
    } catch (error) {
      setSnapshotErrorMessages((currentMessages) => ({
        ...currentMessages,
        [source.id]:
          error instanceof Error
            ? error.message
            : "Snapshot preview is not available for this source yet.",
      }));
    } finally {
      setSnapshotLoadingSourceId((currentLoadingSourceId) =>
        currentLoadingSourceId === source.id ? null : currentLoadingSourceId
      );
    }
  }

  async function enqueueIngestionForSources(nextSources: NotebookSource[]) {
    if (nextSources.length === 0) {
      return;
    }

    const statuses =
      nextSources.length === 1
        ? [await sourcesApi.ingest(nextSources[0].id)]
        : await sourcesApi.bulkIngest(nextSources.map((source) => source.id));

    const trackedIds = statuses
      .filter((status) => status.job_status !== "failed")
      .map((status) => status.source_id);

    if (trackedIds.length > 0) {
      setTrackedIngestionIds((currentIds) => [
        ...currentIds,
        ...trackedIds.filter((sourceId) => !currentIds.includes(sourceId)),
      ]);
    }

    const failedStatus = statuses.find((status) => status.job_status === "failed");

    if (failedStatus) {
      await loadSources({ initial: false }).catch(() => undefined);
      throw new Error(failedStatus.error_message ?? "Failed to enqueue ingestion task.");
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
    <div className="space-y-5 tablet:space-y-6">
      <Card className="overflow-hidden border-slate-200 bg-white/92 shadow-[0_18px_45px_rgba(15,23,42,0.06)]">
        <CardHeader className="gap-4 border-b border-slate-200/80 bg-[linear-gradient(180deg,rgba(248,250,252,0.92),rgba(255,255,255,0.98))] tablet:flex-row tablet:items-start tablet:justify-between tablet:gap-5">
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
              className="w-full xs:w-auto"
            >
              <Plus className="mr-2 h-4 w-4" />
              Add source
            </Button>
            <Button
              variant="outline"
              onClick={() => void refreshSources()}
              disabled={isLoading || isRefreshing || isSubmittingSource}
              className="w-full xs:w-auto"
            >
              <RefreshCw
                className={`mr-2 h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`}
              />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-6 pt-6">
          <div className="grid grid-cols-2 gap-2 xs:flex xs:flex-wrap">
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
                    className="rounded-[1.5rem] border border-slate-200 bg-slate-50/80 p-4 shadow-[0_1px_3px_rgba(15,23,42,0.04)] tablet:p-5"
                  >
                    <div className="flex flex-col gap-4 tablet:flex-row tablet:items-start tablet:justify-between">
                      <div className="min-w-0">
                        <h3 className="truncate text-base font-semibold tracking-tight text-slate-950 xs:text-lg">
                          {source.title}
                        </h3>
                        <div className="mt-3 flex flex-wrap items-center gap-2 font-mono text-[11px] uppercase tracking-[0.16em] text-slate-500">
                          <span>{sourceTypeLabels[source.source_type] ?? source.source_type}</span>
                          <span aria-hidden="true">•</span>
                          <span>{`Added ${formatDate(source.created_at)}`}</span>
                        </div>
                      </div>
                      <div className="flex w-full flex-wrap items-center gap-2 self-start tablet:w-auto tablet:justify-end">
                        <span
                          className={`inline-flex w-fit rounded-full border px-3 py-1 text-xs font-semibold ${statusStyles[status]}`}
                        >
                          {formatStatusLabel(status)}
                        </span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="text-slate-600 hover:bg-slate-100"
                          onClick={() => void handleSourceSnapshotToggle(source)}
                          aria-label={`View source snapshot for ${source.title}`}
                        >
                          <Eye className="mr-2 h-4 w-4" />
                          Snapshot
                        </Button>
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

                    {activeSnapshotSourceId === source.id ? (
                      <div
                        ref={(element) => {
                          snapshotPreviewRefs.current[source.id] = element;
                        }}
                        className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-[0_2px_8px_rgba(15,23,42,0.06)]"
                        onBlur={(event) => handleSnapshotPreviewBlur(source.id, event)}
                      >
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                          Snapshot preview
                        </p>

                        {snapshotLoadingSourceId === source.id ? (
                          <p className="mt-2 text-sm text-muted-foreground">
                            Loading snapshot preview...
                          </p>
                        ) : snapshotErrorMessages[source.id] ? (
                          <p className="mt-2 text-sm text-rose-700">
                            {snapshotErrorMessages[source.id]}
                          </p>
                        ) : snapshotSummaries[source.id] ? (
                          <div className="mt-3 space-y-3">
                            <p className="text-sm leading-6 text-slate-700">
                              {snapshotSummaries[source.id].overview}
                            </p>
                            {snapshotSummaries[source.id].covered_themes.length > 0 ? (
                              <div>
                                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                                  Themes
                                </p>
                                <div className="mt-1 flex flex-wrap gap-1.5">
                                  {snapshotSummaries[source.id].covered_themes.map((theme) => (
                                    <span
                                      key={theme}
                                      className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-xs text-slate-700"
                                    >
                                      {theme}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            ) : null}
                            {snapshotSummaries[source.id].top_keywords.length > 0 ? (
                              <div>
                                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                                  Keywords
                                </p>
                                <div className="mt-1 flex flex-wrap gap-1.5">
                                  {snapshotSummaries[source.id].top_keywords.map((keyword) => (
                                    <span
                                      key={keyword}
                                      className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-0.5 text-xs text-sky-800"
                                    >
                                      {keyword}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            ) : null}
                          </div>
                        ) : (
                          <p className="mt-2 text-sm text-muted-foreground">
                            {getSnapshotUnavailableMessage(source)}
                          </p>
                        )}
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
            await enqueueIngestionForSources([source]);
          })
        }
        onUploadMany={({ files }) =>
          handleSourceMutation(async () => {
            const createdSources = await sourcesApi.uploadMany(notebookId, { files });
            await enqueueIngestionForSources(createdSources);
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

      <div className="grid gap-4 tablet:grid-cols-2">
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

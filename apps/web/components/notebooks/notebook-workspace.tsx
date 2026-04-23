"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  FileSpreadsheet,
  FileText,
  Globe,
  Mic,
  MoreVertical,
  Plus,
  RefreshCw,
  Trash2,
  Type,
  Youtube,
  Eye,
} from "lucide-react";

import { SourceDeleteDialog } from "@/components/notebooks/source-delete-dialog";
import { SourceManagementDialog } from "@/components/notebooks/source-management-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import {
  sourcesApi,
  notebooksApi,
  type Notebook,
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
const MAX_BULK_INGESTION_SOURCES = 50;
const SOURCE_MENU_WIDTH_PX = 176;
const SOURCE_MENU_MARGIN_PX = 8;
const SOURCE_MENU_OFFSET_PX = 8;

const sourceTypeLabels: Record<SourceType, string> = {
  pdf: "PDF",
  text: "TEXT",
  url: "URL",
  youtube: "YOUTUBE",
  audio: "AUDIO",
  gdocs: "GDOCS",
};

const sourceTypeIconStyles: Record<SourceType, { icon: typeof FileText; className: string }> = {
  pdf: { icon: FileText, className: "bg-rose-50 text-rose-600" },
  url: { icon: Globe, className: "bg-sky-50 text-sky-700" },
  text: { icon: Type, className: "bg-slate-50 text-slate-700" },
  youtube: { icon: Youtube, className: "bg-red-50 text-red-600" },
  audio: { icon: Mic, className: "bg-violet-50 text-violet-700" },
  gdocs: { icon: FileSpreadsheet, className: "bg-emerald-50 text-emerald-700" },
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

  const currentStep = typeof progress.current_step === "string" ? progress.current_step : null;
  const message = typeof progress.message === "string" ? progress.message : null;
  const embeddedChunks = typeof progress.embedded_chunks === "number" ? progress.embedded_chunks : null;
  const totalChunks = typeof progress.total_chunks === "number" ? progress.total_chunks : null;
  const percentage = typeof progress.percentage === "number" ? progress.percentage : null;

  if (currentStep === "embedding" && embeddedChunks !== null && totalChunks !== null) {
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

async function buildWorkspaceSources(notebookId: string): Promise<WorkspaceSource[]> {
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
  const [notebook, setNotebook] = useState<Notebook | null>(null);
  const [sources, setSources] = useState<WorkspaceSource[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSourceDialogOpen, setIsSourceDialogOpen] = useState(false);
  const [isSubmittingSource, setIsSubmittingSource] = useState(false);
  const [isRetryingIngestion, setIsRetryingIngestion] = useState(false);
  const [retryingSourceId, setRetryingSourceId] = useState<string | null>(null);
  const [trackedIngestionIds, setTrackedIngestionIds] = useState<string[]>([]);
  const [sourcePendingDelete, setSourcePendingDelete] = useState<WorkspaceSource | null>(null);
  const [isDeletingSource, setIsDeletingSource] = useState(false);
  const [deleteErrorMessage, setDeleteErrorMessage] = useState<string | null>(null);
  const [activeSnapshotSourceId, setActiveSnapshotSourceId] = useState<string | null>(null);
  const [pinnedSnapshotSourceId, setPinnedSnapshotSourceId] = useState<string | null>(null);
  const [snapshotLoadingSourceId, setSnapshotLoadingSourceId] = useState<string | null>(null);
  const [snapshotSummaries, setSnapshotSummaries] = useState<Record<string, SourceSnapshotSummary>>({});
  const [snapshotErrorMessages, setSnapshotErrorMessages] = useState<Record<string, string>>({});
  const snapshotModalRef = useRef<HTMLDivElement | null>(null);
  const snapshotCloseTimeoutRef = useRef<number | null>(null);
  const [snapshotPosition, setSnapshotPosition] = useState<{ top: number; left: number } | null>(null);
  const sourcesListRef = useRef<HTMLDivElement | null>(null);
  const sourceMenuButtonRefs = useRef(new Map<string, HTMLButtonElement>());
  const sourceMenuRef = useRef<HTMLDivElement | null>(null);
  const [openMenuSourceId, setOpenMenuSourceId] = useState<string | null>(null);
  const [sourceMenuPosition, setSourceMenuPosition] = useState<{
    top: number;
    left: number;
    width: number;
  } | null>(null);
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
    },
  );
  const retryableSources = sources.filter((source) => {
    const status = getEffectiveStatus(source);
    return status === "pending" || status === "failed";
  });

  function chunkSourceIds(sourceIds: string[]): string[][] {
    if (sourceIds.length <= MAX_BULK_INGESTION_SOURCES) {
      return [sourceIds];
    }

    const chunks: string[][] = [];

    for (let index = 0; index < sourceIds.length; index += MAX_BULK_INGESTION_SOURCES) {
      chunks.push(sourceIds.slice(index, index + MAX_BULK_INGESTION_SOURCES));
    }

    return chunks;
  }

  async function enqueueIngestionForSourceIds(sourceIds: string[]) {
    if (sourceIds.length === 0) {
      return [] as SourceIngestionStatus[];
    }

    if (sourceIds.length === 1) {
      return [await sourcesApi.ingest(sourceIds[0])];
    }

    const statusResponses: SourceIngestionStatus[] = [];
    const sourceIdChunks = chunkSourceIds(sourceIds);

    for (const sourceIdChunk of sourceIdChunks) {
      const chunkStatuses = await sourcesApi.bulkIngest(sourceIdChunk);
      statusResponses.push(...chunkStatuses);
    }

    return statusResponses;
  }

  function reconcileTrackedIngestions(nextSources: WorkspaceSource[]) {
    setTrackedIngestionIds((currentIds) =>
      currentIds.filter((sourceId) => {
        const source = nextSources.find((candidate) => candidate.id === sourceId);
        return source ? !isResolvedStatus(getEffectiveStatus(source)) : false;
      }),
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

    async function hydrateNotebook() {
      try {
        const notebookData = await notebooksApi.get(notebookId);

        if (!isActive) {
          return;
        }

        setNotebook(notebookData);
      } catch (error) {
        if (!isActive) {
          return;
        }

        const message = error instanceof Error ? error.message : "Failed to load notebook.";
        setErrorMessage(message);
      }
    }

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

        const message = error instanceof Error ? error.message : "Failed to load notebook sources.";

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
    setNotebook(null);
    setTrackedIngestionIds([]);
    setActiveSnapshotSourceId(null);
    setPinnedSnapshotSourceId(null);
    setSnapshotLoadingSourceId(null);
    setSnapshotSummaries({});
    setSnapshotErrorMessages({});
    void hydrateNotebook();
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
      const previewContainer = snapshotModalRef.current;
      if (previewContainer && event.target instanceof Node && !previewContainer.contains(event.target)) {
        setActiveSnapshotSourceId(null);
        setPinnedSnapshotSourceId(null);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setActiveSnapshotSourceId(null);
        setPinnedSnapshotSourceId(null);
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
    if (!openMenuSourceId) {
      return;
    }

    function handlePointerDown(event: PointerEvent) {
      if (!(event.target instanceof Node)) {
        return;
      }

      const menuButton = openMenuSourceId ? sourceMenuButtonRefs.current.get(openMenuSourceId) : undefined;
      const menuRoot = sourceMenuRef.current;

      if (menuButton?.contains(event.target) || menuRoot?.contains(event.target)) {
        return;
      }

      setOpenMenuSourceId(null);
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpenMenuSourceId(null);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [openMenuSourceId]);

  useEffect(() => {
    if (!openMenuSourceId) {
      setSourceMenuPosition(null);
      return;
    }

    function recalculate() {
      const menuButton = openMenuSourceId ? sourceMenuButtonRefs.current.get(openMenuSourceId) : undefined;
      if (!menuButton || !menuButton.isConnected) {
        setOpenMenuSourceId(null);
        return;
      }

      const rect = menuButton.getBoundingClientRect();
      const menuHeight = sourceMenuRef.current?.offsetHeight ?? 156;
      const width = Math.min(SOURCE_MENU_WIDTH_PX, window.innerWidth - SOURCE_MENU_MARGIN_PX * 2);

      let top = rect.bottom + SOURCE_MENU_OFFSET_PX;
      let left = rect.right - width;

      if (top + menuHeight > window.innerHeight - SOURCE_MENU_MARGIN_PX) {
        top = rect.top - menuHeight - SOURCE_MENU_OFFSET_PX;
      }
      if (top < SOURCE_MENU_MARGIN_PX) {
        top = SOURCE_MENU_MARGIN_PX;
      }
      if (left < SOURCE_MENU_MARGIN_PX) {
        left = SOURCE_MENU_MARGIN_PX;
      }
      if (left + width > window.innerWidth - SOURCE_MENU_MARGIN_PX) {
        left = window.innerWidth - SOURCE_MENU_MARGIN_PX - width;
      }

      setSourceMenuPosition({ top, left, width });
    }

    recalculate();

    const container = sourcesListRef.current;
    container?.addEventListener("scroll", recalculate);
    window.addEventListener("resize", recalculate);
    window.addEventListener("scroll", recalculate, true);

    return () => {
      container?.removeEventListener("scroll", recalculate);
      window.removeEventListener("resize", recalculate);
      window.removeEventListener("scroll", recalculate, true);
    };
  }, [openMenuSourceId]);

  useEffect(() => {
    if (activeSnapshotSourceId && !sources.some((source) => source.id === activeSnapshotSourceId)) {
      setActiveSnapshotSourceId(null);
      setPinnedSnapshotSourceId(null);
    }
  }, [activeSnapshotSourceId, sources]);

  useEffect(() => {
    if (openMenuSourceId && !sources.some((source) => source.id === openMenuSourceId)) {
      setOpenMenuSourceId(null);
    }
  }, [openMenuSourceId, sources]);

  useEffect(() => {
    return () => {
      cancelScheduledSnapshotClose();
    };
  }, []);

  useEffect(() => {
    if (!activeSnapshotSourceId) {
      setSnapshotPosition(null);
      return;
    }

    function recalculate() {
      const article = document.querySelector(
        `[data-testid="source-row-${activeSnapshotSourceId}"]`,
      );
      if (!article) {
        setSnapshotPosition(null);
        return;
      }

      const rect = article.getBoundingClientRect();
      const popoverWidth = 320;
      const estimatedHeight = 280;
      const margin = 8;

      let top = rect.bottom + margin;
      let left = rect.right - popoverWidth;

      if (top + estimatedHeight > window.innerHeight - margin) {
        top = rect.top - estimatedHeight - margin;
      }
      if (left < margin) {
        left = rect.left;
      }
      if (top < margin) {
        top = margin;
      }
      if (left + popoverWidth > window.innerWidth - margin) {
        left = window.innerWidth - margin - popoverWidth;
      }

      setSnapshotPosition({ top, left });
    }

    recalculate();

    const container = sourcesListRef.current;
    container?.addEventListener("scroll", recalculate);
    window.addEventListener("resize", recalculate);

    return () => {
      container?.removeEventListener("scroll", recalculate);
      window.removeEventListener("resize", recalculate);
    };
  }, [activeSnapshotSourceId]);

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
          : source,
      ),
    );
    setTrackedIngestionIds(
      has_pending_sources
        ? statuses.filter((status) => !isResolvedStatus(status.status)).map((status) => status.source_id)
        : [],
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

  function cancelScheduledSnapshotClose() {
    if (snapshotCloseTimeoutRef.current === null) {
      return;
    }
    window.clearTimeout(snapshotCloseTimeoutRef.current);
    snapshotCloseTimeoutRef.current = null;
  }

  function scheduleSnapshotClose() {
    cancelScheduledSnapshotClose();
    snapshotCloseTimeoutRef.current = window.setTimeout(() => {
      setActiveSnapshotSourceId(null);
      setPinnedSnapshotSourceId(null);
    }, 120);
  }

  async function openSnapshotPreview(source: WorkspaceSource) {
    cancelScheduledSnapshotClose();
    setActiveSnapshotSourceId(source.id);

    if (getEffectiveStatus(source) !== "ready") {
      return;
    }

    if (snapshotSummaries[source.id] || snapshotLoadingSourceId === source.id) {
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
        [source.id]: error instanceof Error ? error.message : "Snapshot preview is not available for this source yet.",
      }));
    } finally {
      setSnapshotLoadingSourceId((currentLoadingSourceId) =>
        currentLoadingSourceId === source.id ? null : currentLoadingSourceId,
      );
    }
  }

  async function enqueueIngestionForSources(nextSources: NotebookSource[]) {
    if (nextSources.length === 0) {
      return;
    }

    const statuses = await enqueueIngestionForSourceIds(nextSources.map((source) => source.id));

    const trackedIds = statuses.filter((status) => status.job_status !== "failed").map((status) => status.source_id);

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

  async function retryPendingAndFailedSources() {
    if (retryableSources.length === 0) {
      return;
    }

    try {
      setIsRetryingIngestion(true);
      setErrorMessage(null);

      const statuses = await enqueueIngestionForSourceIds(retryableSources.map((source) => source.id));

      const trackedIds = statuses.filter((status) => status.job_status !== "failed").map((status) => status.source_id);

      if (trackedIds.length > 0) {
        setTrackedIngestionIds((currentIds) => [
          ...currentIds,
          ...trackedIds.filter((sourceId) => !currentIds.includes(sourceId)),
        ]);
      }

      const failedStatus = statuses.find((status) => status.job_status === "failed");

      await loadSources({ initial: false, silent: true });

      if (failedStatus) {
        throw new Error(failedStatus.error_message ?? "Failed to retry ingestion for some sources.");
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to retry ingestion.");
    } finally {
      setIsRetryingIngestion(false);
    }
  }

  async function retrySingleSource(sourceId: string) {
    try {
      setRetryingSourceId(sourceId);
      setErrorMessage(null);

      const statuses = await enqueueIngestionForSourceIds([sourceId]);
      const trackedIds = statuses.filter((status) => status.job_status !== "failed").map((status) => status.source_id);

      if (trackedIds.length > 0) {
        setTrackedIngestionIds((currentIds) => [...currentIds, ...trackedIds.filter((id) => !currentIds.includes(id))]);
      }

      await loadSources({ initial: false, silent: true });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to retry ingestion.");
    } finally {
      setRetryingSourceId((current) => (current === sourceId ? null : current));
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
      setSources((currentSources) => currentSources.filter((source) => source.id !== sourcePendingDelete.id));
      setSourcePendingDelete(null);
    } catch (error) {
      setDeleteErrorMessage(error instanceof Error ? error.message : "Failed to delete this source.");
    } finally {
      setIsDeletingSource(false);
    }
  }

  function toggleSourceMenu(sourceId: string) {
    setOpenMenuSourceId((current) => (current === sourceId ? null : sourceId));
  }

  const readySourceCount = sources.filter((s) => getEffectiveStatus(s) === "ready").length;
  const isNotebookReady = readySourceCount > 0;
  const activeSnapshotSource = activeSnapshotSourceId
    ? sources.find((s) => s.id === activeSnapshotSourceId) ?? null
    : null;
  const openMenuSource = openMenuSourceId ? sources.find((source) => source.id === openMenuSourceId) ?? null : null;

  return (
    <div className="space-y-6">
      {/* Sources Section */}
      <Card className="border-slate-200 bg-white/95 shadow-sm">
        <CardHeader className="gap-4 border-b border-slate-200/60 pb-5">
          <div className="flex flex-row gap-4 items-center justify-between">
            <div>
              <CardTitle className="text-xl font-semibold">Sources</CardTitle>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                onClick={() => setIsSourceDialogOpen(true)}
                disabled={isLoading || isRefreshing || isSubmittingSource}
                className="bg-primary text-sm font-medium"
                size="lg"
              >
                <Plus className="mr-2 h-4 w-4" />
                ADD SOURCE
              </Button>
              <Button
                variant="outline"
                size="icon"
                aria-label={retryableSources.length > 0 ? "Retry pending/failed" : "Refresh sources"}
                onClick={() => {
                  if (isRetryingIngestion) {
                    refreshSources();
                    return;
                  }
                  if (retryableSources.length !== 0) {
                    void retryPendingAndFailedSources();
                  } else {
                    refreshSources();
                  }
                }}
                disabled={isLoading || isRefreshing || isSubmittingSource}
                className="h-10 w-10"
              >
                <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 pt-5">
          {/* Status Count Badges */}
          <div className="flex flex-wrap gap-2">
            <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">
              {sourceCounts.total} total
            </span>
            <span className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-amber-700">
              {sourceCounts.pending} pending
            </span>
            <span className="inline-flex items-center rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-sky-700">
              {sourceCounts.processing} processing
            </span>
            <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-emerald-700">
              {sourceCounts.ready} ready
            </span>
            {sourceCounts.failed ? (
              <span className="inline-flex items-center rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-rose-700">
                {sourceCounts.failed} failed
              </span>
            ) : null}
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
            <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/60 p-8 text-center">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Truth boundary</p>
              <p className="mt-3 text-base font-semibold text-slate-900">No sources yet</p>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">
                Add a PDF, pasted text, or URL to start grounding this notebook.
              </p>
            </div>
          ) : (
            <div ref={sourcesListRef} className="space-y-2 max-h-[calc(100vh-694px)] min-h-[198px] overflow-scroll">
              {sources.map((source) => {
                const status = getEffectiveStatus(source);
                const failureMessage = status === "failed" ? getFailureMessage(source) : null;
                const progressMessage = status === "failed" ? null : formatProgressMessage(source);
                const progressPercentage = (() => {
                  const progress = source.ingestion?.progress;
                  if (!progress || typeof progress !== "object") {
                    return null;
                  }
                  const percentage = (progress as Record<string, unknown>).percentage;
                  return typeof percentage === "number" ? percentage : null;
                })();

                return (
                  <article
                    key={source.id}
                    data-testid={`source-row-${source.id}`}
                    className={`group relative overflow-visible rounded-xl border border-slate-200 bg-white/80 p-3 transition-all hover:bg-white hover:shadow-md ${
                      activeSnapshotSourceId === source.id || openMenuSourceId === source.id ? "z-20" : "z-0"
                    }`}
                    onMouseEnter={() => {
                      cancelScheduledSnapshotClose();
                      if (openMenuSourceId && openMenuSourceId !== source.id) {
                        return;
                      }
                      if (pinnedSnapshotSourceId && pinnedSnapshotSourceId !== source.id) {
                        return;
                      }
                      void openSnapshotPreview(source);
                    }}
                    onMouseLeave={() => {
                      if (activeSnapshotSourceId === source.id && pinnedSnapshotSourceId !== source.id) {
                        scheduleSnapshotClose();
                      }
                    }}
                  >
                    {(() => {
                      const sourceTypeConfig = sourceTypeIconStyles[source.source_type] ?? sourceTypeIconStyles.text;
                      const SourceTypeIcon = sourceTypeConfig.icon;
                      const menuOpen = openMenuSourceId === source.id;

                      return (
                        <>
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex min-w-0 flex-1 items-center gap-3">
                              <div
                                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${sourceTypeConfig.className}`}
                              >
                                <SourceTypeIcon className="h-4 w-4" />
                              </div>

                              <div className="min-w-0 flex-1">
                                <div className="flex items-baseline gap-2">
                                  <h3 className="truncate text-sm font-semibold text-slate-900">{source.title}</h3>
                                  <span
                                    className={`shrink-0 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                                      status === "ready"
                                        ? "bg-emerald-50 text-emerald-700"
                                        : status === "processing"
                                          ? "bg-sky-50 text-sky-700"
                                          : status === "failed"
                                            ? "bg-rose-50 text-rose-700"
                                            : "bg-amber-50 text-amber-700"
                                    }`}
                                  >
                                    <span className="h-1 w-1 rounded-full bg-current" />
                                    {formatStatusLabel(status)}
                                  </span>
                                </div>
                                <div className="mt-0.5 flex items-center gap-2 text-[11px] text-slate-500">
                                  <span className="uppercase tracking-wide">
                                    {sourceTypeLabels[source.source_type]}
                                  </span>
                                  <span>•</span>
                                  <span>{formatDate(source.created_at)}</span>
                                </div>
                              </div>
                            </div>

                            <div className="flex shrink-0 items-center gap-1">
                              <Button
                                ref={(node) => {
                                  if (node) {
                                    sourceMenuButtonRefs.current.set(source.id, node);
                                    return;
                                  }

                                  sourceMenuButtonRefs.current.delete(source.id);
                                }}
                                type="button"
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                                aria-label={`More actions for ${source.title}`}
                                aria-expanded={menuOpen}
                                onClick={() => toggleSourceMenu(source.id)}
                              >
                                <MoreVertical className="h-4 w-4" />
                                <span className="sr-only">{`View source snapshot for ${source.title}`}</span>
                              </Button>
                            </div>
                          </div>

                          {progressMessage ? (
                            <div className="mt-2 space-y-1.5">
                              <div className="flex items-center justify-between gap-2">
                                <p className="min-w-0 break-words text-xs text-slate-600">{progressMessage}</p>
                                {progressPercentage !== null && (
                                  <span className="shrink-0 text-xs font-medium text-sky-600">
                                    {Math.round(progressPercentage)}%
                                  </span>
                                )}
                              </div>
                              {progressPercentage !== null && (
                                <div className="h-1 w-full overflow-hidden rounded-full bg-slate-100">
                                  <div
                                    className="h-full rounded-full bg-sky-500"
                                    style={{
                                      width: `${Math.max(0, Math.min(100, progressPercentage))}%`,
                                    }}
                                  />
                                </div>
                              )}
                            </div>
                          ) : null}

                          {failureMessage ? (
                            <div className="mt-2 flex items-start justify-between gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800">
                              <p className="min-w-0 break-words">{failureMessage}</p>
                              <button
                                type="button"
                                className="shrink-0 text-[10px] font-semibold uppercase tracking-wider text-rose-700 hover:text-rose-900"
                                onClick={() => void retrySingleSource(source.id)}
                              >
                                Retry
                              </button>
                            </div>
                          ) : null}
                        </>
                      );
                    })()}
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
            }),
          )
        }
        onCreateUrl={({ title, url }) =>
          handleSourceMutation(() =>
            sourcesApi.createUrl(notebookId, {
              title,
              url,
            }),
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

      {/* Bottom Sections */}
      <div className="grid gap-5 tablet:grid-cols-2">
        <Card className="border-slate-200 bg-white/95 shadow-sm">
          <CardHeader className="space-y-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Notebook Summary</p>
            <CardTitle className="text-lg font-semibold">Key insights and overview</CardTitle>
            <CardDescription className="text-sm text-slate-600">
              Reserved for Feature 4.1 once summaries are generated from ready sources.
            </CardDescription>
          </CardHeader>
        </Card>

        <Card className="border-slate-200 bg-white/95 shadow-sm">
          <CardHeader className="space-y-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Generated Assets</p>
            <CardTitle className="text-lg font-semibold">Derived content</CardTitle>
            <CardDescription className="text-sm text-slate-600">
              Reserved for Phase 5 outputs such as briefings, FAQs, and study guides.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>

      {openMenuSource && sourceMenuPosition
        ? createPortal(
            <div
              ref={sourceMenuRef}
              style={{
                position: "fixed",
                top: sourceMenuPosition.top,
                left: sourceMenuPosition.left,
                width: sourceMenuPosition.width,
                zIndex: 60,
              }}
              className="max-w-[calc(100vw-1rem)] rounded-xl border border-slate-200 bg-white p-1 shadow-lg"
            >
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-700 transition hover:bg-slate-50"
                onClick={() => {
                  setOpenMenuSourceId(null);
                  setPinnedSnapshotSourceId(openMenuSource.id);
                  void openSnapshotPreview(openMenuSource);
                }}
              >
                <Eye className="h-4 w-4" />
                Preview snapshot
              </button>

              {(() => {
                const status = getEffectiveStatus(openMenuSource);

                if (status !== "pending" && status !== "failed") {
                  return null;
                }

                return (
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-700 transition hover:bg-slate-50"
                    onClick={() => {
                      setOpenMenuSourceId(null);
                      void retrySingleSource(openMenuSource.id);
                    }}
                  >
                    <RefreshCw className="h-4 w-4" />
                    Retry source
                  </button>
                );
              })()}

              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-rose-700 transition hover:bg-rose-50"
                onClick={() => {
                  setOpenMenuSourceId(null);
                  setDeleteErrorMessage(null);
                  setSourcePendingDelete(openMenuSource);
                }}
              >
                <Trash2 className="h-4 w-4" />
                Delete source
              </button>
            </div>,
            document.body,
          )
        : null}

      {activeSnapshotSource && snapshotPosition
        ? createPortal(
            <div
              ref={snapshotModalRef}
              style={{
                position: "fixed",
                top: snapshotPosition.top,
                left: snapshotPosition.left,
                zIndex: 50,
              }}
              className="w-80 max-w-[calc(100vw-1.5rem)] rounded-xl border border-slate-200 bg-white px-3 py-3 shadow-lg"
              onMouseEnter={cancelScheduledSnapshotClose}
              onMouseLeave={() => {
                if (pinnedSnapshotSourceId !== activeSnapshotSource.id) {
                  scheduleSnapshotClose();
                }
              }}
            >
              <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
                Snapshot preview
              </p>

              {snapshotLoadingSourceId === activeSnapshotSource.id ? (
                <p className="mt-2 text-xs text-slate-500">Loading snapshot preview...</p>
              ) : snapshotErrorMessages[activeSnapshotSource.id] ? (
                <p className="mt-2 text-xs text-rose-700">
                  {snapshotErrorMessages[activeSnapshotSource.id]}
                </p>
              ) : snapshotSummaries[activeSnapshotSource.id] ? (
                <div className="mt-2 space-y-2.5">
                  <p className="text-xs leading-relaxed text-slate-700">
                    {snapshotSummaries[activeSnapshotSource.id].overview}
                  </p>
                  {snapshotSummaries[activeSnapshotSource.id].covered_themes.length > 0 ? (
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Themes
                      </p>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {snapshotSummaries[activeSnapshotSource.id].covered_themes.map((theme) => (
                          <span
                            key={theme}
                            className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-700"
                          >
                            {theme}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {snapshotSummaries[activeSnapshotSource.id].top_keywords.length > 0 ? (
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Keywords
                      </p>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {snapshotSummaries[activeSnapshotSource.id].top_keywords.map((keyword) => (
                          <span
                            key={keyword}
                            className="rounded-md border border-sky-200 bg-sky-50 px-2 py-0.5 text-[11px] text-sky-700"
                          >
                            {keyword}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : (
                <p className="mt-2 text-xs text-slate-500">
                  {getSnapshotUnavailableMessage(activeSnapshotSource)}
                </p>
              )}
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}

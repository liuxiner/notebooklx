"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  FileText,
  Globe,
  MoreVertical,
  Plus,
  Trash2,
  Upload,
} from "lucide-react";

import {
  sourcesApi,
  type NotebookSource,
  type SourceIngestionStatus,
  type SourceStatus,
  type SourceType,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { SourceManagementDialog } from "@/components/notebooks/source-management-dialog";
import { SourceDeleteDialog } from "@/components/notebooks/source-delete-dialog";

interface NotebookSourcesPanelProps {
  notebookId: string;
}

interface PanelSource extends NotebookSource {
  ingestion: SourceIngestionStatus | null;
}

const INGESTION_POLL_INTERVAL_MS = 1500;
const MAX_BULK_INGESTION_SOURCES = 50;

const statusStyles: Record<SourceStatus, { badge: string; dot: string; label: string }> = {
  pending: {
    badge: "bg-slate-100 text-slate-700",
    dot: "bg-slate-400",
    label: "Pending",
  },
  processing: {
    badge: "bg-amber-50 text-amber-800",
    dot: "bg-amber-500",
    label: "Processing",
  },
  ready: {
    badge: "bg-emerald-50 text-emerald-800",
    dot: "bg-emerald-500",
    label: "Ready",
  },
  failed: {
    badge: "bg-rose-50 text-rose-800",
    dot: "bg-rose-500",
    label: "Failed",
  },
};

function isResolvedStatus(status: SourceStatus): boolean {
  return status === "ready" || status === "failed";
}

function getEffectiveStatus(source: PanelSource): SourceStatus {
  return source.ingestion?.status ?? source.status;
}

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

function sourceIcon(sourceType: SourceType) {
  switch (sourceType) {
    case "url":
      return Globe;
    default:
      return FileText;
  }
}

export function NotebookSourcesPanel({ notebookId }: NotebookSourcesPanelProps) {
  const [sources, setSources] = useState<PanelSource[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [trackedIngestionIds, setTrackedIngestionIds] = useState<string[]>([]);
  const [openMenuSourceId, setOpenMenuSourceId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const [sourcePendingDelete, setSourcePendingDelete] = useState<PanelSource | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteErrorMessage, setDeleteErrorMessage] = useState<string | null>(null);

  const sourcesByUpdated = useMemo(
    () => [...sources].sort((left, right) => {
      const leftTime = new Date(left.updated_at).getTime();
      const rightTime = new Date(right.updated_at).getTime();
      return rightTime - leftTime;
    }),
    [sources]
  );

  useEffect(() => {
    let isActive = true;

    async function hydrateSources() {
      try {
        setIsLoading(true);
        setErrorMessage(null);

        const list = await sourcesApi.list(notebookId);
        if (!isActive) return;

        if (list.length === 0) {
          setSources([]);
          setTrackedIngestionIds([]);
          return;
        }

        const { statuses, has_pending_sources } = await sourcesApi.bulkStatus(
          list.map((source) => source.id)
        );
        if (!isActive) return;

        const statusMap = new Map(
          statuses.map((status) => [status.source_id, status] as const)
        );

        setSources(
          list.map((source) => ({
            ...source,
            ingestion: statusMap.get(source.id) ?? null,
          }))
        );
        setTrackedIngestionIds(
          has_pending_sources
            ? statuses
                .filter((status) => !isResolvedStatus(status.status))
                .map((status) => status.source_id)
            : []
        );
      } catch (error) {
        if (!isActive) return;
        setSources([]);
        setTrackedIngestionIds([]);
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to load sources."
        );
      } finally {
        if (!isActive) return;
        setIsLoading(false);
      }
    }

    void hydrateSources();

    return () => {
      isActive = false;
    };
  }, [notebookId]);

  useEffect(() => {
    if (!openMenuSourceId) {
      return;
    }

    function onPointerDown(event: PointerEvent) {
      if (!menuRef.current) return;
      if (event.target instanceof Node && menuRef.current.contains(event.target)) return;
      setOpenMenuSourceId(null);
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpenMenuSourceId(null);
      }
    }

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [openMenuSourceId]);

  useEffect(() => {
    if (trackedIngestionIds.length === 0 || isLoading) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      void refreshTrackedIngestionStatuses().catch(() => undefined);
    }, INGESTION_POLL_INTERVAL_MS);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [isLoading, trackedIngestionIds]);

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

  async function enqueueIngestionForSourceIds(sourceIds: string[]) {
    if (sourceIds.length === 0) return;

    if (sourceIds.length === 1) {
      const status = await sourcesApi.ingest(sourceIds[0]);
      setTrackedIngestionIds((current) =>
        Array.from(new Set([...current, status.source_id]))
      );
      return;
    }

    const chunks = chunkSourceIds(sourceIds);
    const ingestions: SourceIngestionStatus[] = [];
    for (const chunk of chunks) {
      const chunkIngestions = await sourcesApi.bulkIngest(chunk);
      ingestions.push(...chunkIngestions);
    }

    setTrackedIngestionIds((current) =>
      Array.from(new Set([...current, ...ingestions.map((ingestion) => ingestion.source_id)]))
    );
  }

  async function mutateSources(action: () => Promise<unknown>) {
    try {
      setIsSubmitting(true);
      await action();
    } finally {
      setIsSubmitting(false);
    }
  }

  async function reloadSources(silent?: boolean) {
    try {
      if (!silent) {
        setErrorMessage(null);
      }
      const list = await sourcesApi.list(notebookId);
      if (list.length === 0) {
        setSources([]);
        setTrackedIngestionIds([]);
        return;
      }

      const { statuses, has_pending_sources } = await sourcesApi.bulkStatus(
        list.map((source) => source.id)
      );
      const statusMap = new Map(statuses.map((status) => [status.source_id, status] as const));

      setSources(
        list.map((source) => ({
          ...source,
          ingestion: statusMap.get(source.id) ?? null,
        }))
      );
      setTrackedIngestionIds(
        has_pending_sources
          ? statuses
              .filter((status) => !isResolvedStatus(status.status))
              .map((status) => status.source_id)
          : []
      );
    } catch (error) {
      if (!silent) {
        setErrorMessage(error instanceof Error ? error.message : "Failed to refresh sources.");
      }
    }
  }

  async function handleDeleteSource() {
    if (!sourcePendingDelete) return;

    try {
      setIsDeleting(true);
      setDeleteErrorMessage(null);
      await sourcesApi.delete(notebookId, sourcePendingDelete.id);
      setSources((current) => current.filter((source) => source.id !== sourcePendingDelete.id));
      setTrackedIngestionIds((current) => current.filter((id) => id !== sourcePendingDelete.id));
      setSourcePendingDelete(null);
    } catch (error) {
      setDeleteErrorMessage(error instanceof Error ? error.message : "Failed to delete source.");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <>
      <Card className="overflow-hidden rounded-2xl border-slate-200 bg-white shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
              Research materials
            </p>
            <p className="mt-0.5 text-lg font-semibold tracking-tight text-slate-900">
              Sources
            </p>
          </div>
          <Button
            onClick={() => setIsDialogOpen(true)}
            disabled={isLoading || isSubmitting}
            className="h-9 rounded-xl px-3 text-xs font-semibold"
          >
            <Plus className="h-4 w-4" />
            Add Source
          </Button>
        </CardHeader>

        <CardContent className="space-y-3 p-4">
          <button
            type="button"
            onClick={() => setIsDialogOpen(true)}
            disabled={isLoading || isSubmitting}
            className="flex w-full items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50/70 px-3 py-2 text-left text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <span>Add Source</span>
            <Upload className="h-4 w-4 text-slate-400" />
          </button>

          {isLoading ? (
            <div className="flex min-h-32 items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50/70">
              <Spinner size="lg" />
            </div>
          ) : errorMessage ? (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
              {errorMessage}
              <div className="mt-2">
                <Button variant="outline" size="sm" onClick={() => void reloadSources()}>
                  Retry
                </Button>
              </div>
            </div>
          ) : sourcesByUpdated.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/70 p-4 text-sm text-slate-600">
              No sources yet. Add a PDF, text, or URL to start grounding this notebook.
            </div>
          ) : (
            <div className="space-y-2">
              {sourcesByUpdated.map((source) => {
                const status = getEffectiveStatus(source);
                const statusStyle = statusStyles[status];
                const Icon = sourceIcon(source.source_type);
                const isMenuOpen = openMenuSourceId === source.id;

                return (
                  <div
                    key={source.id}
                    className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-3 py-3 shadow-[0_1px_2px_rgba(15,23,42,0.04)]"
                  >
                    <div className="flex min-w-0 flex-1 items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-50 text-slate-600">
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-slate-900">
                          {source.title}
                        </p>
                        <p className="mt-0.5 text-xs text-slate-400">
                          {source.source_type.toUpperCase()}
                        </p>
                      </div>
                    </div>

                    <div className="flex flex-none items-center gap-2">
                      <span
                        className={cn(
                          "inline-flex items-center gap-2 rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em]",
                          statusStyle.badge
                        )}
                      >
                        <span className={cn("h-1.5 w-1.5 rounded-full", statusStyle.dot)} />
                        {statusStyle.label}
                      </span>

                      <div className="relative" ref={isMenuOpen ? menuRef : undefined}>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-9 w-9 rounded-xl text-slate-500 hover:bg-slate-100 hover:text-slate-700"
                          onClick={(event) => {
                            event.stopPropagation();
                            setOpenMenuSourceId((current) =>
                              current === source.id ? null : source.id
                            );
                          }}
                          aria-label={`Source actions for ${source.title}`}
                        >
                          <MoreVertical className="h-4 w-4" />
                        </Button>

                        {isMenuOpen ? (
                          <div
                            className="absolute right-0 top-10 z-20 w-40 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-[0_14px_30px_rgba(15,23,42,0.12)]"
                            role="menu"
                            aria-label="Source menu"
                            onClick={(event) => event.stopPropagation()}
                          >
                            <button
                              type="button"
                              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-rose-700 hover:bg-rose-50"
                              role="menuitem"
                              onClick={() => {
                                setOpenMenuSourceId(null);
                                setDeleteErrorMessage(null);
                                setSourcePendingDelete(source);
                              }}
                            >
                              <Trash2 className="h-4 w-4" />
                              Delete
                            </button>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <SourceManagementDialog
        open={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        isSubmitting={isSubmitting}
        onUpload={({ file, title }) =>
          mutateSources(async () => {
            const source = await sourcesApi.upload(notebookId, { file, title });
            await enqueueIngestionForSourceIds([source.id]);
            await reloadSources(true);
            setIsDialogOpen(false);
          })
        }
        onUploadMany={({ files }) =>
          mutateSources(async () => {
            const created = await sourcesApi.uploadMany(notebookId, { files });
            await enqueueIngestionForSourceIds(created.map((source) => source.id));
            await reloadSources(true);
            setIsDialogOpen(false);
          })
        }
        onCreateText={({ title, content }) =>
          mutateSources(async () => {
            const source = await sourcesApi.createText(notebookId, { title, content });
            await enqueueIngestionForSourceIds([source.id]);
            await reloadSources(true);
            setIsDialogOpen(false);
          })
        }
        onCreateUrl={({ title, url }) =>
          mutateSources(async () => {
            const source = await sourcesApi.createUrl(notebookId, { title, url });
            await enqueueIngestionForSourceIds([source.id]);
            await reloadSources(true);
            setIsDialogOpen(false);
          })
        }
      />

      <SourceDeleteDialog
        open={sourcePendingDelete !== null}
        onOpenChange={(open) => {
          if (!open) {
            setSourcePendingDelete(null);
            setDeleteErrorMessage(null);
          }
        }}
        sourceTitle={sourcePendingDelete?.title ?? null}
        onConfirm={handleDeleteSource}
        isDeleting={isDeleting}
        errorMessage={deleteErrorMessage}
      />
    </>
  );
}


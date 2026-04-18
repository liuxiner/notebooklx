"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  BarChart3,
  BookOpen,
  ChevronDown,
  Clock,
  LayoutGrid,
  LibraryBig,
  List,
  Plus,
  Search,
  Settings,
} from "lucide-react";

import { notebooksApi, sourcesApi, type Notebook, ApiError } from "@/lib/api";
import { useToast } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/notebooks/empty-state";
import { NotebookCard } from "@/components/notebooks/notebook-card";
import { NotebookFormDialog } from "@/components/notebooks/notebook-form-dialog";
import { DeleteDialog } from "@/components/notebooks/delete-dialog";
import { cn } from "@/lib/utils";

type NotebookViewMode = "grid" | "list";

const MAX_SOURCE_COUNT_FETCH = 30;
const SOURCE_COUNT_CONCURRENCY = 5;

function compareByUpdatedAtDesc(left: Notebook, right: Notebook) {
  return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime();
}

async function runWithConcurrency<T>(
  tasks: Array<() => Promise<T>>,
  concurrency: number
): Promise<T[]> {
  const results: T[] = [];
  const queue = [...tasks];
  const workers = Array.from({ length: Math.max(1, concurrency) }, async () => {
    while (queue.length) {
      const task = queue.shift();
      if (!task) return;
      results.push(await task());
    }
  });
  await Promise.all(workers);
  return results;
}

export default function NotebooksPage() {
  const router = useRouter();
  const { showToast } = useToast();

  // State for notebooks list
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<NotebookViewMode>("grid");
  const [sourceCounts, setSourceCounts] = useState<Record<string, number>>({});

  // State for create/edit dialog
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [editingNotebook, setEditingNotebook] = useState<Notebook | null>(null);

  // State for delete dialog
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deletingNotebook, setDeletingNotebook] = useState<Notebook | null>(null);

  // Load notebooks on mount
  useEffect(() => {
    loadNotebooks();
  }, []);

  useEffect(() => {
    if (isLoading || notebooks.length === 0) {
      return;
    }

    const targetNotebooks = notebooks.slice(0, MAX_SOURCE_COUNT_FETCH);
    const notebookIdsToFetch = targetNotebooks
      .map((notebook) => notebook.id)
      .filter((id) => typeof sourceCounts[id] !== "number");

    if (notebookIdsToFetch.length === 0) {
      return;
    }

    void (async () => {
      const tasks = notebookIdsToFetch.map((notebookId) => async () => {
        try {
          const sources = await sourcesApi.list(notebookId);
          return { notebookId, count: sources.length };
        } catch {
          return null;
        }
      });

      const results = await runWithConcurrency(tasks, SOURCE_COUNT_CONCURRENCY);

      setSourceCounts((current) => {
        const next = { ...current };
        for (const result of results) {
          if (!result) continue;
          next[result.notebookId] = result.count;
        }
        return next;
      });
    })();
  }, [isLoading, notebooks, sourceCounts]);

  async function loadNotebooks() {
    try {
      setIsLoading(true);
      const data = await notebooksApi.list();
      setNotebooks(data);
    } catch (error) {
      console.error("Failed to load notebooks:", error);
      showToast("Failed to load notebooks. Please try again.", "error");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleCreateOrUpdate(data: { name: string; description: string }) {
    try {
      setIsSubmitting(true);

      if (editingNotebook) {
        // Update existing notebook
        const updated = await notebooksApi.update(editingNotebook.id, data);
        setNotebooks((prev) =>
          prev.map((nb) => (nb.id === updated.id ? updated : nb))
        );
        showToast("Notebook updated successfully", "success");
      } else {
        // Create new notebook
        const created = await notebooksApi.create(data);
        setNotebooks((prev) => [created, ...prev]);
        showToast("Notebook created successfully", "success");
      }

      setIsFormOpen(false);
      setEditingNotebook(null);
    } catch (error) {
      console.error("Failed to save notebook:", error);
      const message =
        error instanceof ApiError
          ? error.message
          : "Failed to save notebook. Please try again.";
      showToast(message, "error");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!deletingNotebook) return;

    try {
      setIsDeleting(true);
      await notebooksApi.delete(deletingNotebook.id);
      setNotebooks((prev) => prev.filter((nb) => nb.id !== deletingNotebook.id));
      showToast("Notebook deleted successfully", "success");
      setIsDeleteOpen(false);
      setDeletingNotebook(null);
    } catch (error) {
      console.error("Failed to delete notebook:", error);
      const message =
        error instanceof ApiError
          ? error.message
          : "Failed to delete notebook. Please try again.";
      showToast(message, "error");
    } finally {
      setIsDeleting(false);
    }
  }

  function openCreateDialog() {
    setEditingNotebook(null);
    setIsFormOpen(true);
  }

  function openEditDialog(notebook: Notebook) {
    setEditingNotebook(notebook);
    setIsFormOpen(true);
  }

  function openDeleteDialog(notebook: Notebook) {
    setDeletingNotebook(notebook);
    setIsDeleteOpen(true);
  }

  function handleNotebookClick(notebookId: string) {
    router.push(`/notebooks/${notebookId}`);
  }

  const filteredNotebooks = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    const base = [...notebooks].sort(compareByUpdatedAtDesc);
    if (!query) return base;

    return base.filter((notebook) => {
      const haystack = `${notebook.name} ${notebook.description ?? ""}`.toLowerCase();
      return haystack.includes(query);
    });
  }, [notebooks, searchQuery]);

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Desktop top bar */}
      <div className="hidden desktop:block sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center gap-6 px-6">
          <div className="flex items-center gap-2 text-slate-900">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <BookOpen className="h-4 w-4" />
            </div>
            <span className="text-sm font-semibold tracking-tight">
              Internal Knowledge Curator
            </span>
          </div>

          <div className="ml-auto flex items-center gap-3">
            <div className="relative w-[320px]">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search knowledge..."
                aria-label="Search knowledge"
                className="h-10 w-full rounded-full border border-slate-200 bg-slate-50/70 pl-9 pr-3 text-sm text-slate-900 shadow-sm outline-none focus:border-primary/40 focus:ring-4 focus:ring-primary/10"
              />
            </div>
            <Button variant="ghost" size="icon" className="h-10 w-10 rounded-full" disabled>
              <Settings className="h-4 w-4" />
              <span className="sr-only">Settings</span>
            </Button>
          </div>
        </div>
      </div>

      <div className="mx-auto flex max-w-[1400px]">
        {/* Desktop sidebar */}
        <aside className="hidden desktop:flex w-64 flex-col gap-6 border-r border-slate-200 bg-white px-5 py-6">
          <div>
            <p className="text-sm font-semibold text-slate-950">Curator Pro</p>
            <p className="text-xs text-slate-500">Senior Researcher</p>
          </div>

          <nav className="space-y-1 text-sm">
            <button
              type="button"
              onClick={() => router.push("/notebooks")}
              className="flex w-full items-center gap-3 rounded-xl bg-primary/10 px-3 py-2 text-left font-medium text-primary"
            >
              <BookOpen className="h-4 w-4" />
              Notebooks
            </button>
            <button
              type="button"
              onClick={() => router.push("/evaluation")}
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-slate-600 hover:bg-slate-50 hover:text-slate-900"
            >
              <BarChart3 className="h-4 w-4" />
              Evaluation
            </button>
            <button
              type="button"
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-slate-400"
              disabled
            >
              <LibraryBig className="h-4 w-4" />
              Library
            </button>
            <button
              type="button"
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-slate-400"
              disabled
            >
              <Clock className="h-4 w-4" />
              History
            </button>
          </nav>

          <div className="mt-auto">
            <Button variant="outline" className="w-full justify-center" disabled>
              <Plus className="h-4 w-4" />
              New Analysis
            </Button>
          </div>
        </aside>

        {/* Main */}
        <main className="flex-1 px-4 py-6 tablet:px-6 desktop:px-10">
          {/* Mobile top bar */}
          <div className="desktop:hidden mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-900">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <BookOpen className="h-4 w-4" />
              </div>
              <span className="text-xs font-semibold tracking-tight">
                Internal Knowledge Curator
              </span>
            </div>
          </div>

          <div className="flex flex-col gap-4 tablet:flex-row tablet:items-end tablet:justify-between">
            <div>
              <h1 className="text-3xl font-semibold tracking-tight text-slate-950 tablet:text-4xl">
                Notebooks
              </h1>
              <p className="mt-1 text-sm italic text-slate-500">
                Your curated collection of academic explorations.
              </p>
            </div>

            <div className="flex flex-col gap-2 xs:flex-row xs:items-center xs:justify-end">
              <Button
                onClick={openCreateDialog}
                disabled={isLoading}
                className="w-full xs:w-auto"
              >
                <Plus className="h-4 w-4" />
                New Notebook
              </Button>
            </div>
          </div>

          {/* Mobile search */}
          <div className="desktop:hidden mt-4">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search your research..."
                aria-label="Search your research"
                className="h-11 w-full rounded-2xl border border-slate-200 bg-white pl-10 pr-3 text-sm text-slate-900 shadow-sm outline-none focus:border-primary/40 focus:ring-4 focus:ring-primary/10"
              />
            </div>
          </div>

          {/* Desktop controls */}
          <div className="mt-6 hidden desktop:flex items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="inline-flex overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
                <button
                  type="button"
                  onClick={() => setViewMode("grid")}
                  className={cn(
                    "flex items-center gap-2 px-3 py-2 text-xs font-semibold",
                    viewMode === "grid"
                      ? "bg-primary/10 text-primary"
                      : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
                  )}
                  aria-pressed={viewMode === "grid"}
                >
                  <LayoutGrid className="h-4 w-4" />
                  GRID
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode("list")}
                  className={cn(
                    "flex items-center gap-2 px-3 py-2 text-xs font-semibold",
                    viewMode === "list"
                      ? "bg-primary/10 text-primary"
                      : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
                  )}
                  aria-pressed={viewMode === "list"}
                >
                  <List className="h-4 w-4" />
                  LIST
                </button>
              </div>

              <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
                <span className="uppercase tracking-[0.18em]">Sort by:</span>
                <button
                  type="button"
                  className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10"
                  disabled
                >
                  Recent <ChevronDown className="h-3 w-3" />
                </button>
              </div>
            </div>

            <p className="text-xs text-slate-400">
              Showing {filteredNotebooks.length} active research projects
            </p>
          </div>

          <div className="mt-6">
            {isLoading ? (
              <div className="flex min-h-[240px] items-center justify-center rounded-2xl border border-slate-200 bg-white">
                <Spinner size="lg" />
              </div>
            ) : null}

            {!isLoading && filteredNotebooks.length === 0 ? (
              <EmptyState onCreateNotebook={openCreateDialog} />
            ) : null}

            {!isLoading && filteredNotebooks.length > 0 ? (
              <div
                className={cn(
                  "grid gap-4",
                  viewMode === "grid"
                    ? "grid-cols-1 tablet:grid-cols-2 desktop:grid-cols-3"
                    : "grid-cols-1"
                )}
              >
                {filteredNotebooks.map((notebook) => (
                  <NotebookCard
                    key={notebook.id}
                    notebook={notebook}
                    view={viewMode}
                    sourceCount={sourceCounts[notebook.id]}
                    onClick={() => handleNotebookClick(notebook.id)}
                    onEdit={() => openEditDialog(notebook)}
                    onDelete={() => openDeleteDialog(notebook)}
                  />
                ))}

                <button
                  type="button"
                  onClick={openCreateDialog}
                  className="group flex min-h-[168px] flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-slate-200 bg-white/40 p-6 text-center text-slate-500 transition-colors hover:border-primary/40 hover:bg-primary/5 hover:text-slate-700"
                >
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-slate-200 bg-white text-slate-500 shadow-sm transition-colors group-hover:border-primary/30 group-hover:text-primary">
                    <Plus className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-700">Start New Project</p>
                    <p className="mt-1 text-xs text-slate-400">Initialize workspace</p>
                  </div>
                </button>
              </div>
            ) : null}
          </div>

          {/* Mobile spacing for bottom nav */}
          <div className="h-20 desktop:hidden" />
        </main>
      </div>

      {/* Mobile bottom nav + FAB */}
      <div className="desktop:hidden fixed bottom-0 left-0 right-0 z-50 border-t border-slate-200 bg-white">
        <div className="mx-auto grid max-w-md grid-cols-3 px-6 py-3 text-xs text-slate-500">
          <button type="button" className="flex flex-col items-center gap-1 text-primary">
            <BookOpen className="h-5 w-5" />
            Notebooks
          </button>
          <button
            type="button"
            className="flex flex-col items-center gap-1"
            onClick={() => router.push("/evaluation")}
          >
            <BarChart3 className="h-5 w-5" />
            Evaluation
          </button>
          <button type="button" className="flex flex-col items-center gap-1" disabled>
            <Settings className="h-5 w-5" />
            Settings
          </button>
        </div>
      </div>

      <button
        type="button"
        onClick={openCreateDialog}
        className="desktop:hidden fixed bottom-20 right-5 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-white shadow-[0_18px_45px_rgba(15,23,42,0.25)] transition-transform active:translate-y-px"
        aria-label="Create notebook"
      >
        <Plus className="h-5 w-5" />
      </button>

      <NotebookFormDialog
        open={isFormOpen}
        onOpenChange={(open) => {
          setIsFormOpen(open);
          if (!open) setEditingNotebook(null);
        }}
        onSubmit={handleCreateOrUpdate}
        notebook={editingNotebook}
        isSubmitting={isSubmitting}
      />

      <DeleteDialog
        open={isDeleteOpen}
        onOpenChange={setIsDeleteOpen}
        onConfirm={handleDelete}
        notebook={deletingNotebook}
        isDeleting={isDeleting}
      />
    </div>
  );
}

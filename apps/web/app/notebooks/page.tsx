"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { BookOpen, Plus } from "lucide-react";
import { notebooksApi, type Notebook, ApiError } from "@/lib/api";
import { useToast } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/notebooks/empty-state";
import { NotebookCard } from "@/components/notebooks/notebook-card";
import { NotebookFormDialog } from "@/components/notebooks/notebook-form-dialog";
import { DeleteDialog } from "@/components/notebooks/delete-dialog";

export default function NotebooksPage() {
  const router = useRouter();
  const { showToast } = useToast();

  // State for notebooks list
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [isLoading, setIsLoading] = useState(true);

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

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-7xl px-4 py-8 lg:py-10">
        <section className="overflow-hidden rounded-[2rem] border border-slate-200/90 bg-white/92 p-6 shadow-[0_18px_45px_rgba(15,23,42,0.06)] backdrop-blur-sm sm:p-8">
          <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-sky-50 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.2em] text-sky-800">
                <BookOpen className="h-3.5 w-3.5" />
                Source-grounded workspace
              </div>
              <h1 className="mt-4 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl">
                Notebooks
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
                Organize your knowledge from multiple sources, keep your evidence
                traceable, and move from source collection to grounded chat in one
                calm workspace.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] lg:min-w-[360px]">
              <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/80 p-4 shadow-sm">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  Active notebooks
                </p>
                <p className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
                  {isLoading ? "..." : notebooks.length}
                </p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Each notebook defines its own source boundary for grounded answers.
                </p>
              </div>

              <Button
                onClick={openCreateDialog}
                disabled={isLoading}
                className="h-auto min-h-[112px] flex-col items-start justify-end rounded-[1.5rem] px-5 py-5 text-left"
              >
                <Plus className="h-5 w-5" />
                <span>{notebooks.length === 0 ? "Create your first notebook" : "New Notebook"}</span>
              </Button>
            </div>
          </div>
        </section>

        <div className="mt-8">
          {isLoading ? (
            <div className="flex min-h-[320px] items-center justify-center rounded-[2rem] border border-slate-200 bg-white/80">
              <Spinner size="lg" />
            </div>
          ) : null}

          {!isLoading && notebooks.length === 0 ? (
            <EmptyState onCreateNotebook={openCreateDialog} />
          ) : null}

          {!isLoading && notebooks.length > 0 ? (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {notebooks.map((notebook) => (
                <NotebookCard
                  key={notebook.id}
                  notebook={notebook}
                  onClick={() => handleNotebookClick(notebook.id)}
                  onEdit={() => openEditDialog(notebook)}
                  onDelete={() => openDeleteDialog(notebook)}
                />
              ))}
            </div>
          ) : null}
        </div>

        {!isLoading && notebooks.length > 0 ? (
          <div className="mt-6 flex justify-end">
            <Button variant="outline" onClick={openCreateDialog}>
              <Plus className="mr-2 h-4 w-4" />
              Add another notebook
            </Button>
          </div>
        ) : null}

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
    </div>
  );
}

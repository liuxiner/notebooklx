"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
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
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Notebooks</h1>
            <p className="text-muted-foreground mt-1">
              Organize your knowledge from multiple sources
            </p>
          </div>
          {!isLoading && notebooks.length > 0 && (
            <Button onClick={openCreateDialog}>
              <Plus className="mr-2 h-4 w-4" />
              New Notebook
            </Button>
          )}
        </div>

        {/* Loading state */}
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Spinner size="lg" />
          </div>
        )}

        {/* Empty state */}
        {!isLoading && notebooks.length === 0 && (
          <EmptyState onCreateNotebook={openCreateDialog} />
        )}

        {/* Notebooks grid */}
        {!isLoading && notebooks.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
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
        )}

        {/* Create/Edit Dialog */}
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

        {/* Delete Dialog */}
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

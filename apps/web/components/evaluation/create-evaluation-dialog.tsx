/**
 * Create Evaluation Dialog Component
 *
 * Dialog for creating new evaluation tests with query and ground truth selection.
 */
"use client";

import { useEffect, useState } from "react";
import { evaluationApi } from "@/lib/evaluation-api";
import type { Notebook } from "@/lib/api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import { Plus } from "lucide-react";
import ChunkSelector from "./chunk-selector";

interface CreateEvaluationDialogProps {
  initialNotebookId?: string;
  notebooks: Notebook[];
  notebooksLoading: boolean;
  notebooksError: string | null;
  onSuccess?: () => void;
}

export default function CreateEvaluationDialog({
  initialNotebookId,
  notebooks,
  notebooksLoading,
  notebooksError,
  onSuccess,
}: CreateEvaluationDialogProps) {
  const [open, setOpen] = useState(false);
  const [selectedNotebookId, setSelectedNotebookId] = useState(initialNotebookId ?? "");
  const [query, setQuery] = useState("");
  const [selectedChunkIds, setSelectedChunkIds] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setSelectedNotebookId(initialNotebookId ?? "");
    }
  }, [initialNotebookId, open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!query.trim()) {
      setError("Query is required");
      return;
    }

    if (!selectedNotebookId) {
      setError("Please select a notebook first");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const result = await evaluationApi.create({
        notebook_id: selectedNotebookId,
        query: query.trim(),
        ground_truth_chunk_ids: selectedChunkIds.length > 0 ? selectedChunkIds : undefined,
      });

      // Optionally start the evaluation run automatically
      if (result.id) {
        await evaluationApi.start(result.id);
      }

      // Reset form
      setQuery("");
      setSelectedChunkIds([]);
      setOpen(false);

      // Notify parent
      if (onSuccess) {
        onSuccess();
      }
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to create evaluation test");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenChange = (newOpen: boolean) => {
    if (!submitting) {
      setOpen(newOpen);
      setSelectedNotebookId(initialNotebookId ?? "");
      setQuery("");
      setSelectedChunkIds([]);
      setError(null);
    }
  };

  const handleNotebookChange = (value: string) => {
    setSelectedNotebookId(value);
    setSelectedChunkIds([]);
    setError(null);
  };

  const notebookSelectionDisabled =
    submitting || notebooksLoading || Boolean(notebooksError) || notebooks.length === 0;
  const submitDisabled =
    submitting ||
    !query.trim() ||
    !selectedNotebookId ||
    notebooksLoading ||
    Boolean(notebooksError) ||
    notebooks.length === 0;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="h-4 w-4 mr-2" />
          Create Test
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create Evaluation Test</DialogTitle>
          <DialogDescription>
            Create a new evaluation test to measure retrieval, citation, and answer quality.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="evaluation-notebook">
              Notebook <span className="text-destructive">*</span>
            </Label>
            <select
              id="evaluation-notebook"
              aria-label="Notebook"
              value={selectedNotebookId}
              onChange={(e) => handleNotebookChange(e.target.value)}
              disabled={notebookSelectionDisabled}
              className="flex h-10 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <option value="">
                {notebooksLoading
                  ? "Loading notebooks..."
                  : notebooks.length === 0
                    ? "No notebooks available"
                    : "Select a notebook"}
              </option>
              {notebooks.map((notebook) => (
                <option key={notebook.id} value={notebook.id}>
                  {notebook.name}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500">
              {notebooksError
                ? notebooksError
                : notebooks.length === 0
                  ? "No notebooks available yet. Create a notebook first."
                  : "Select the notebook you want to evaluate before choosing expected evidence."}
            </p>
          </div>

          {/* Query Input */}
          <div className="space-y-2">
            <Label htmlFor="query">
              Test Query <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="query"
              placeholder="Enter a question to test the system (e.g., 'What are the key risks mentioned in the report?')"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              rows={3}
              required
              disabled={submitting}
            />
            <p className="text-xs text-slate-500">
              This query will be used to test retrieval and answer generation.
            </p>
          </div>

          {/* Ground Truth Selection */}
          {selectedNotebookId && (
            <div className="space-y-2">
              <Label>
                Ground Truth Chunks <span className="text-slate-500">(optional)</span>
              </Label>
              <p className="text-xs text-slate-500 mb-3">
                Select the chunks that should ideally be retrieved for this query. This enables
                retrieval quality metrics like Recall@5 and MRR.
              </p>
              <ChunkSelector
                key={selectedNotebookId}
                notebookId={selectedNotebookId}
                selectedChunkIds={selectedChunkIds}
                onSelectionChange={setSelectedChunkIds}
              />
            </div>
          )}

          {/* Error Display */}
          {error && (
            <div className="text-sm text-destructive bg-destructive/5 border border-destructive/20 rounded-md p-3">
              {error}
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={submitDisabled}>
              {submitting ? (
                <>
                  <Spinner className="mr-2" />
                  Creating...
                </>
              ) : (
                "Create & Run Test"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

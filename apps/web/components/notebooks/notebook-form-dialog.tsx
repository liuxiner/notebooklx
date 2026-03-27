"use client";

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { Notebook } from "@/lib/api";

interface NotebookFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: { name: string; description: string }) => Promise<void>;
  notebook?: Notebook | null;
  isSubmitting: boolean;
}

export function NotebookFormDialog({
  open,
  onOpenChange,
  onSubmit,
  notebook,
  isSubmitting,
}: NotebookFormDialogProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  // Reset form when dialog opens/closes or notebook changes
  useEffect(() => {
    if (open && notebook) {
      setName(notebook.name);
      setDescription(notebook.description || "");
    } else if (!open) {
      setName("");
      setDescription("");
    }
  }, [open, notebook]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    await onSubmit({ name: name.trim(), description: description.trim() });
  };

  const isEdit = !!notebook;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Notebook" : "Create New Notebook"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update your notebook's name and description."
              : "Create a new notebook to organize your sources and knowledge."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">
                Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="name"
                placeholder="My Research Notebook"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                disabled={isSubmitting}
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description (optional)</Label>
              <Textarea
                id="description"
                placeholder="A brief description of what this notebook contains..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={isSubmitting}
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting || !name.trim()}>
              {isSubmitting ? "Saving..." : isEdit ? "Save Changes" : "Create Notebook"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

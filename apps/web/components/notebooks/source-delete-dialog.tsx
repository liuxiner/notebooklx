"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface SourceDeleteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sourceTitle: string | null;
  onConfirm: () => Promise<void>;
  isDeleting: boolean;
  errorMessage: string | null;
}

export function SourceDeleteDialog({
  open,
  onOpenChange,
  sourceTitle,
  onConfirm,
  isDeleting,
  errorMessage,
}: SourceDeleteDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete source?</DialogTitle>
          <DialogDescription>
            Remove{" "}
            <span className="font-semibold text-foreground">
              {sourceTitle || "this source"}
            </span>{" "}
            from the notebook. This action cannot be undone.
          </DialogDescription>
        </DialogHeader>

        {errorMessage ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
            {errorMessage}
          </div>
        ) : null}

        <DialogFooter className="gap-2 border-t border-slate-200 pt-4">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isDeleting}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={() => void onConfirm()}
            disabled={isDeleting}
          >
            {isDeleting ? "Deleting source..." : "Delete source"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

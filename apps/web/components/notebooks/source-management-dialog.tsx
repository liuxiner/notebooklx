"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

type SourceMode = "upload" | "text" | "url";

interface SourceManagementDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpload: (payload: { file: File; title: string }) => Promise<void>;
  onCreateText: (payload: { title: string; content: string }) => Promise<void>;
  onCreateUrl: (payload: { title: string; url: string }) => Promise<void>;
  isSubmitting: boolean;
}

const modeButtonStyles =
  "rounded-full px-3 py-1 text-sm font-medium transition-colors";

function isSupportedUploadFile(file: File): boolean {
  const filename = file.name.toLowerCase();
  return (
    file.type === "application/pdf" ||
    file.type === "text/plain" ||
    filename.endsWith(".pdf") ||
    filename.endsWith(".txt")
  );
}

function isValidHttpUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

export function SourceManagementDialog({
  open,
  onOpenChange,
  onUpload,
  onCreateText,
  onCreateUrl,
  isSubmitting,
}: SourceManagementDialogProps) {
  const [mode, setMode] = useState<SourceMode>("upload");
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [lastAutoFilledUploadTitle, setLastAutoFilledUploadTitle] = useState("");
  const [content, setContent] = useState("");
  const [url, setUrl] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setMode("upload");
      setTitle("");
      setFile(null);
      setLastAutoFilledUploadTitle("");
      setContent("");
      setUrl("");
      setErrorMessage(null);
    }
  }, [open]);

  function switchMode(nextMode: SourceMode) {
    setMode(nextMode);
    setErrorMessage(null);
  }

  function handleUploadFileChange(nextFile: File | null) {
    setFile(nextFile);
    setErrorMessage(null);

    if (!nextFile) {
      if (title === lastAutoFilledUploadTitle) {
        setTitle("");
      }
      setLastAutoFilledUploadTitle("");
      return;
    }

    const nextAutoTitle = nextFile.name;
    if (!title.trim() || title === lastAutoFilledUploadTitle) {
      setTitle(nextAutoTitle);
    }
    setLastAutoFilledUploadTitle(nextAutoTitle);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage(null);

    try {
      if (mode === "upload") {
        if (!file) {
          setErrorMessage("Choose a PDF or TXT file to upload.");
          return;
        }

        if (!isSupportedUploadFile(file)) {
          setErrorMessage("Only PDF and TXT files are supported.");
          return;
        }

        await onUpload({
          file,
          title: title.trim(),
        });
        return;
      }

      if (mode === "text") {
        if (!content.trim()) {
          setErrorMessage("Paste text content before adding this source.");
          return;
        }

        await onCreateText({
          title: title.trim(),
          content: content.trim(),
        });
        return;
      }

      if (!isValidHttpUrl(url.trim())) {
        setErrorMessage("Enter a valid URL.");
        return;
      }

      await onCreateUrl({
        title: title.trim(),
        url: url.trim(),
      });
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to add source."
      );
    }
  }

  const submitLabel =
    mode === "upload"
      ? isSubmitting
        ? "Uploading source..."
        : "Upload source"
      : mode === "text"
        ? isSubmitting
          ? "Adding text..."
          : "Add text"
        : isSubmitting
          ? "Adding URL..."
          : "Add URL";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add source</DialogTitle>
          <DialogDescription>
            Add a PDF or TXT upload, paste text, or capture a URL for this notebook.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} noValidate>
          <div className="space-y-4 py-4">
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className={`${modeButtonStyles} ${
                  mode === "upload"
                    ? "bg-slate-900 text-white"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
                aria-pressed={mode === "upload"}
                onClick={() => switchMode("upload")}
                disabled={isSubmitting}
              >
                Upload
              </button>
              <button
                type="button"
                className={`${modeButtonStyles} ${
                  mode === "text"
                    ? "bg-slate-900 text-white"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
                aria-pressed={mode === "text"}
                onClick={() => switchMode("text")}
                disabled={isSubmitting}
              >
                Text
              </button>
              <button
                type="button"
                className={`${modeButtonStyles} ${
                  mode === "url"
                    ? "bg-slate-900 text-white"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
                aria-pressed={mode === "url"}
                onClick={() => switchMode("url")}
                disabled={isSubmitting}
              >
                URL
              </button>
            </div>

            {mode === "upload" ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="source-file">Choose file</Label>
                  <Input
                    id="source-file"
                    type="file"
                    accept=".pdf,.txt,application/pdf,text/plain"
                    onChange={(event) =>
                      handleUploadFileChange(event.target.files?.[0] ?? null)
                    }
                    disabled={isSubmitting}
                  />
                  <p className="text-xs text-muted-foreground">
                    Supported upload types: PDF and TXT.
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="source-title-upload">Title</Label>
                  <Input
                    id="source-title-upload"
                    placeholder="Quarterly Brief"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    disabled={isSubmitting}
                  />
                </div>
              </>
            ) : null}

            {mode === "text" ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="source-title-text">Title</Label>
                  <Input
                    id="source-title-text"
                    placeholder="Interview transcript"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    disabled={isSubmitting}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="source-content">Pasted text</Label>
                  <Textarea
                    id="source-content"
                    placeholder="Paste notes, transcripts, or excerpts here..."
                    rows={8}
                    value={content}
                    onChange={(event) => setContent(event.target.value)}
                    disabled={isSubmitting}
                  />
                </div>
              </>
            ) : null}

            {mode === "url" ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="source-title-url">Title</Label>
                  <Input
                    id="source-title-url"
                    placeholder="Optional display title"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    disabled={isSubmitting}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="source-url">Source URL</Label>
                  <Input
                    id="source-url"
                    type="url"
                    placeholder="https://example.com/article"
                    value={url}
                    onChange={(event) => setUrl(event.target.value)}
                    disabled={isSubmitting}
                  />
                </div>
              </>
            ) : null}

            {errorMessage ? (
              <div className="rounded-2xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
                {errorMessage}
              </div>
            ) : null}
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
            <Button type="submit" disabled={isSubmitting}>
              {submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

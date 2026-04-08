"use client";

import { ArrowRight, Pencil, Trash2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { Notebook } from "@/lib/api";

interface NotebookCardProps {
  notebook: Notebook;
  onClick: () => void;
  onEdit: () => void;
  onDelete: () => void;
}

export function NotebookCard({ notebook, onClick, onEdit, onDelete }: NotebookCardProps) {
  const createdDate = new Date(notebook.created_at).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  const description = notebook.description
    ? notebook.description.length > 150
      ? `${notebook.description.substring(0, 150)}...`
      : notebook.description
    : "No description";

  return (
    <Card
      className="group cursor-pointer overflow-hidden border-slate-200 bg-white/95 transition-all duration-200 hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-[0_12px_24px_rgba(15,23,42,0.08)]"
      onClick={onClick}
    >
      <CardHeader className="gap-4 border-b border-slate-200/80 bg-[linear-gradient(180deg,rgba(248,250,252,0.92),rgba(255,255,255,0.98))]">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600">
                Notebook
              </span>
              <CardDescription className="font-mono text-[11px] uppercase tracking-[0.12em] text-slate-500">
                {createdDate}
              </CardDescription>
            </div>
            <CardTitle className="mt-4 truncate text-2xl">{notebook.name}</CardTitle>
          </div>
          <div className="flex gap-1 rounded-full bg-white/90 p-1 opacity-0 shadow-sm transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={(e) => {
                e.stopPropagation();
                onEdit();
              }}
            >
              <Pencil className="h-4 w-4" />
              <span className="sr-only">Edit notebook</span>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-destructive hover:bg-rose-50 hover:text-destructive"
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
              }}
            >
              <Trash2 className="h-4 w-4" />
              <span className="sr-only">Delete notebook</span>
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="line-clamp-3 text-sm leading-6 text-muted-foreground">{description}</p>
        <div className="flex items-center justify-between gap-3">
          <span className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            Source-grounded workspace
          </span>
          <span className="inline-flex items-center gap-1.5 text-sm font-medium text-primary">
            Open workspace
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

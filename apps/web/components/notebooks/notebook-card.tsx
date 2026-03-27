"use client";

import { MoreVertical, Trash2, Pencil } from "lucide-react";
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
      className="cursor-pointer transition-shadow hover:shadow-md group"
      onClick={onClick}
    >
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <CardTitle className="truncate">{notebook.name}</CardTitle>
            <CardDescription className="mt-1.5">{createdDate}</CardDescription>
          </div>
          <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
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
              className="h-8 w-8 text-destructive hover:text-destructive"
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
      <CardContent>
        <p className="text-sm text-muted-foreground line-clamp-3">{description}</p>
      </CardContent>
    </Card>
  );
}

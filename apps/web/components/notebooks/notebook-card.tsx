"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { MoreVertical, Pencil, Trash2 } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Notebook } from "@/lib/api";

interface NotebookCardProps {
  notebook: Notebook;
  view?: "grid" | "list";
  sourceCount?: number | null;
  onClick: () => void;
  onEdit: () => void;
  onDelete: () => void;
}

function formatRelativeTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const now = Date.now();
  const diffSeconds = Math.round((date.getTime() - now) / 1000);
  const absSeconds = Math.abs(diffSeconds);
  const rtf = new Intl.RelativeTimeFormat("en-US", { numeric: "auto" });

  if (absSeconds < 60) return rtf.format(diffSeconds, "second");

  const diffMinutes = Math.round(diffSeconds / 60);
  if (Math.abs(diffMinutes) < 60) return rtf.format(diffMinutes, "minute");

  const diffHours = Math.round(diffSeconds / 3600);
  if (Math.abs(diffHours) < 24) return rtf.format(diffHours, "hour");

  const diffDays = Math.round(diffSeconds / 86400);
  if (Math.abs(diffDays) < 30) return rtf.format(diffDays, "day");

  const diffMonths = Math.round(diffSeconds / 2592000);
  if (Math.abs(diffMonths) < 12) return rtf.format(diffMonths, "month");

  const diffYears = Math.round(diffSeconds / 31536000);
  return rtf.format(diffYears, "year");
}

function hashToIndex(input: string, size: number) {
  let hash = 0;
  for (let index = 0; index < input.length; index += 1) {
    hash = (hash * 31 + input.charCodeAt(index)) >>> 0;
  }
  return hash % size;
}

export function NotebookCard({
  notebook,
  view = "grid",
  sourceCount,
  onClick,
  onEdit,
  onDelete,
}: NotebookCardProps) {
  const menuRef = useRef<HTMLDivElement | null>(null);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const description = notebook.description?.trim() || "No description";
  const updatedLabel = useMemo(
    () => formatRelativeTime(notebook.updated_at),
    [notebook.updated_at]
  );
  const accent = useMemo(() => {
    const palette = [
      {
        bg: "bg-indigo-50",
        text: "text-indigo-700",
        ring: "ring-indigo-100",
        icon: "bg-indigo-100 text-indigo-700",
      },
      {
        bg: "bg-orange-50",
        text: "text-orange-700",
        ring: "ring-orange-100",
        icon: "bg-orange-100 text-orange-700",
      },
      {
        bg: "bg-emerald-50",
        text: "text-emerald-700",
        ring: "ring-emerald-100",
        icon: "bg-emerald-100 text-emerald-700",
      },
      {
        bg: "bg-sky-50",
        text: "text-sky-700",
        ring: "ring-sky-100",
        icon: "bg-sky-100 text-sky-700",
      },
    ];
    return palette[hashToIndex(notebook.id || notebook.name, palette.length)];
  }, [notebook.id, notebook.name]);

  useEffect(() => {
    if (!isMenuOpen) {
      return;
    }

    function onPointerDown(event: PointerEvent) {
      if (!menuRef.current) return;
      if (event.target instanceof Node && menuRef.current.contains(event.target)) return;
      setIsMenuOpen(false);
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsMenuOpen(false);
      }
    }

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [isMenuOpen]);

  const sourcesLabel =
    typeof sourceCount === "number"
      ? `${sourceCount} ${sourceCount === 1 ? "Source" : "Sources"}`
      : "— Sources";

  return (
    <Card
      className={cn(
        "group cursor-pointer overflow-hidden rounded-2xl border-slate-200 bg-white transition-colors hover:border-slate-300 hover:shadow-[0_10px_22px_rgba(15,23,42,0.06)]"
      )}
      onClick={onClick}
    >
      <CardHeader
        className={cn(
          "flex flex-row items-start justify-between gap-3",
          view === "list" ? "pb-0" : "pb-2"
        )}
      >
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <div
            className={cn(
              "flex h-10 w-10 flex-none items-center justify-center rounded-xl ring-1",
              accent.bg,
              accent.ring
            )}
            aria-hidden="true"
          >
            <div className={cn("h-6 w-6 rounded-lg", accent.icon)} />
          </div>

          <div className="min-w-0 flex-1">
            <CardTitle
              className={cn(
                "truncate text-base font-semibold tracking-tight text-slate-900",
                view === "grid" ? "tablet:text-lg" : "text-base"
              )}
            >
              <span className={cn("hover:underline", accent.text)}>{notebook.name}</span>
            </CardTitle>
            <CardDescription className="mt-1 line-clamp-2 text-sm leading-6 text-slate-500">
              {description}
            </CardDescription>
          </div>
        </div>

        <div className="relative flex flex-none items-center" ref={menuRef}>
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9 rounded-xl text-slate-500 hover:bg-slate-100 hover:text-slate-700"
            onClick={(event) => {
              event.stopPropagation();
              setIsMenuOpen((open) => !open);
            }}
            aria-label="Notebook actions"
            aria-expanded={isMenuOpen}
          >
            <MoreVertical className="h-4 w-4" />
          </Button>

          {isMenuOpen ? (
            <div
              className="absolute right-0 top-10 z-20 w-40 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-[0_14px_30px_rgba(15,23,42,0.12)]"
              role="menu"
              aria-label="Notebook menu"
              onClick={(event) => event.stopPropagation()}
            >
              <button
                type="button"
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
                role="menuitem"
                onClick={() => {
                  setIsMenuOpen(false);
                  onEdit();
                }}
              >
                <Pencil className="h-4 w-4" />
                Edit
              </button>
              <button
                type="button"
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-rose-700 hover:bg-rose-50"
                role="menuitem"
                onClick={() => {
                  setIsMenuOpen(false);
                  onDelete();
                }}
              >
                <Trash2 className="h-4 w-4" />
                Delete
              </button>
            </div>
          ) : null}
        </div>
      </CardHeader>

      <CardContent className={cn(view === "list" ? "pt-3" : "pt-3")}>
        <div className="flex items-center justify-between gap-3 text-xs text-slate-400">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-slate-300" aria-hidden="true" />
            <span className="font-medium text-slate-500">{sourcesLabel}</span>
          </span>
          <span className="whitespace-nowrap text-slate-400">
            {updatedLabel ? `Edited ${updatedLabel}` : ""}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

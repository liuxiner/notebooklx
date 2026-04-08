import { BookOpen } from "lucide-react";
import { Button } from "@/components/ui/button";

interface EmptyStateProps {
  onCreateNotebook: () => void;
}

export function EmptyState({ onCreateNotebook }: EmptyStateProps) {
  return (
    <div className="flex min-h-[420px] flex-col items-center justify-center rounded-[2rem] border border-dashed border-slate-300 bg-white/75 p-8 text-center shadow-[0_1px_3px_rgba(15,23,42,0.04)] backdrop-blur-sm">
      <div className="mb-4 rounded-2xl border border-slate-200 bg-slate-50 p-5 shadow-sm">
        <BookOpen className="h-12 w-12 text-slate-500" />
      </div>
      <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
        Sources First
      </p>
      <h2 className="mb-2 mt-3 text-3xl font-semibold tracking-tight text-slate-950">
        No notebooks yet
      </h2>
      <p className="mb-6 max-w-md text-base leading-7 text-muted-foreground">
        Create your first notebook to start organizing your knowledge from multiple sources.
      </p>
      <Button onClick={onCreateNotebook}>Create Your First Notebook</Button>
    </div>
  );
}

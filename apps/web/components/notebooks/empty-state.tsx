import { BookOpen } from "lucide-react";
import { Button } from "@/components/ui/button";

interface EmptyStateProps {
  onCreateNotebook: () => void;
}

export function EmptyState({ onCreateNotebook }: EmptyStateProps) {
  return (
    <div className="flex min-h-[360px] flex-col items-center justify-center rounded-[1.75rem] border border-dashed border-slate-300 bg-white/75 p-6 text-center shadow-[0_1px_3px_rgba(15,23,42,0.04)] backdrop-blur-sm tablet:min-h-[420px] tablet:rounded-[2rem] tablet:p-8">
      <div className="mb-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 shadow-sm tablet:p-5">
        <BookOpen className="h-12 w-12 text-slate-500" />
      </div>
      <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
        Sources First
      </p>
      <h2 className="mb-2 mt-3 text-2xl font-semibold tracking-tight text-slate-950 xs:text-3xl">
        No notebooks yet
      </h2>
      <p className="mb-6 max-w-md text-sm leading-7 text-muted-foreground xs:text-base">
        Create your first notebook to start organizing your knowledge from multiple sources.
      </p>
      <Button onClick={onCreateNotebook}>Create Your First Notebook</Button>
    </div>
  );
}

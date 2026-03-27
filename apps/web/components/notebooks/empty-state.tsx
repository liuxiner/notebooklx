import { BookOpen } from "lucide-react";
import { Button } from "@/components/ui/button";

interface EmptyStateProps {
  onCreateNotebook: () => void;
}

export function EmptyState({ onCreateNotebook }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] text-center p-8">
      <div className="rounded-full bg-muted p-6 mb-4">
        <BookOpen className="h-12 w-12 text-muted-foreground" />
      </div>
      <h2 className="text-2xl font-semibold mb-2">No notebooks yet</h2>
      <p className="text-muted-foreground mb-6 max-w-md">
        Create your first notebook to start organizing your knowledge from multiple sources.
      </p>
      <Button onClick={onCreateNotebook}>Create Your First Notebook</Button>
    </div>
  );
}

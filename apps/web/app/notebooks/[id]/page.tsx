"use client";

import { useParams, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotebookDetailPage() {
  const params = useParams();
  const router = useRouter();
  const notebookId = params.id as string;

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-8">
        <Button
          variant="ghost"
          className="mb-4"
          onClick={() => router.push("/notebooks")}
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Notebooks
        </Button>
        <div className="flex items-center justify-center h-[400px]">
          <div className="text-center">
            <h1 className="text-2xl font-bold mb-2">Notebook Detail</h1>
            <p className="text-muted-foreground">
              Notebook ID: {notebookId}
            </p>
            <p className="text-muted-foreground mt-4">
              (This page will be implemented in a future feature)
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

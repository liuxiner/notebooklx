"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { ChatPanel } from "@/components/chat/chat-panel";
import { NotebookWorkspace } from "@/components/notebooks/notebook-workspace";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { notebooksApi, type Notebook } from "@/lib/api";

export default function NotebookDetailPage() {
  const params = useParams();
  const router = useRouter();
  const notebookId = params.id as string;
  const [notebook, setNotebook] = useState<Notebook | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    async function loadNotebook() {
      try {
        setIsLoading(true);
        setErrorMessage(null);
        const data = await notebooksApi.get(notebookId);

        if (isActive) {
          setNotebook(data);
        }
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "Failed to load notebook details.";

        if (isActive) {
          setErrorMessage(message);
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    }

    void loadNotebook();

    return () => {
      isActive = false;
    };
  }, [notebookId]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <div className="container mx-auto flex min-h-screen max-w-7xl items-center justify-center px-4 py-8">
          <Spinner size="lg" />
        </div>
      </div>
    );
  }

  if (!notebook) {
    return (
      <div className="min-h-screen bg-background">
        <div className="container mx-auto max-w-3xl px-4 py-8">
          <Button
            variant="ghost"
            className="mb-4"
            onClick={() => router.push("/notebooks")}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Notebooks
          </Button>

          <Card>
            <CardHeader>
              <CardTitle>Notebook unavailable</CardTitle>
              <CardDescription>
                {errorMessage || "This notebook could not be loaded."}
              </CardDescription>
            </CardHeader>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(226,232,240,0.7),_transparent_35%),linear-gradient(180deg,_rgba(248,250,252,0.96),_rgba(255,255,255,1))]">
      <div className="container mx-auto max-w-7xl px-4 py-8">
        <Button
          variant="ghost"
          className="mb-4"
          onClick={() => router.push("/notebooks")}
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Notebooks
        </Button>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(340px,420px)]">
          <section className="space-y-6">
            <Card className="border-slate-200 bg-white/90 shadow-sm">
              <CardHeader className="space-y-3">
                <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-500">
                  Notebook workspace
                </p>
                <div>
                  <CardTitle className="text-3xl">{notebook.name}</CardTitle>
                  <CardDescription className="mt-2 max-w-2xl text-base leading-7">
                    {notebook.description || "No description yet."}
                  </CardDescription>
                </div>
              </CardHeader>
              <CardContent className="grid gap-4 text-sm text-muted-foreground sm:grid-cols-2">
                <div className="rounded-2xl border border-border bg-slate-50/80 p-4">
                  <p className="font-medium text-slate-900">Notebook ID</p>
                  <p className="mt-2 break-all leading-6">{notebookId}</p>
                </div>
                <div className="rounded-2xl border border-border bg-slate-50/80 p-4">
                  <p className="font-medium text-slate-900">Ready for chat</p>
                  <p className="mt-2 leading-6">
                    Use the panel on the right to ask grounded questions against
                    your sources.
                  </p>
                </div>
              </CardContent>
            </Card>

            <NotebookWorkspace notebookId={notebook.id} />
          </section>

          <aside className="lg:sticky lg:top-8 lg:h-[calc(100vh-4rem)]">
            <ChatPanel notebookId={notebook.id} notebookName={notebook.name} />
          </aside>
        </div>
      </div>
    </div>
  );
}

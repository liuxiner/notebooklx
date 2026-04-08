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
      <div className="min-h-screen">
        <div className="mx-auto flex min-h-screen max-w-7xl items-center justify-center px-4 py-8">
          <Spinner size="lg" />
        </div>
      </div>
    );
  }

  if (!notebook) {
    return (
      <div className="min-h-screen">
        <div className="mx-auto max-w-3xl px-4 py-8">
          <Button
            variant="ghost"
            className="mb-4 text-slate-700"
            onClick={() => router.push("/notebooks")}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Notebooks
          </Button>

          <Card className="border-slate-200 bg-white/90">
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
    <div className="min-h-screen">
      <div className="mx-auto max-w-[1440px] px-4 py-8">
        <Button
          variant="ghost"
          className="mb-4 text-slate-700"
          onClick={() => router.push("/notebooks")}
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Notebooks
        </Button>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(340px,420px)]">
          <section className="space-y-6">
            <Card className="overflow-hidden border-slate-200 bg-white/92 shadow-[0_18px_45px_rgba(15,23,42,0.06)]">
              <CardHeader className="gap-5 border-b border-slate-200/80 bg-[linear-gradient(180deg,rgba(248,250,252,0.92),rgba(255,255,255,0.98))]">
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                  Notebook workspace
                </p>
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="max-w-2xl">
                    <CardTitle className="text-4xl">{notebook.name}</CardTitle>
                    <CardDescription className="mt-3 max-w-2xl text-base leading-7">
                      {notebook.description || "No description yet."}
                    </CardDescription>
                  </div>

                  <div className="rounded-[1.5rem] border border-sky-200 bg-sky-50 px-4 py-4 shadow-sm lg:max-w-xs">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-800">
                      Ready for grounded chat
                    </p>
                    <p className="mt-2 text-sm leading-6 text-sky-950">
                      Ask focused questions on the right. Every answer stays tied to
                      sources in this notebook.
                    </p>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="grid gap-4 text-sm text-muted-foreground sm:grid-cols-2">
                <div className="rounded-[1.5rem] border border-border bg-slate-50/80 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                    Notebook ID
                  </p>
                  <p className="mt-3 break-all font-mono text-sm leading-6 text-slate-900">
                    {notebookId}
                  </p>
                </div>
                <div className="rounded-[1.5rem] border border-border bg-slate-50/80 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                    Trust boundary
                  </p>
                  <p className="mt-3 leading-6 text-slate-700">
                    Sources define the truth boundary. Upload new material in the
                    workspace below to expand what this notebook can answer.
                  </p>
                </div>
              </CardContent>
            </Card>

            <NotebookWorkspace notebookId={notebook.id} />
          </section>

          <aside className="lg:sticky lg:top-6 lg:h-[calc(100vh-3rem)]">
            <ChatPanel notebookId={notebook.id} notebookName={notebook.name} />
          </aside>
        </div>
      </div>
    </div>
  );
}

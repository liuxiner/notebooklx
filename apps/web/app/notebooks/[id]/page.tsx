"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, BookOpen, CheckCircle2, Pencil, Settings } from "lucide-react";

import { ChatPanel } from "@/components/chat/chat-panel";
import { NotebookWorkspace } from "@/components/notebooks/notebook-workspace";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { notebooksApi, type Notebook } from "@/lib/api";

function NotebookOverviewCard({ notebook }: { notebook: Notebook }) {
  return (
    <Card className="overflow-hidden rounded-2xl border-slate-200 bg-white shadow-sm">
      <CardHeader className="relative gap-4 px-5 py-5 tablet:px-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <CardTitle className="text-3xl font-semibold tracking-tight text-slate-950 tablet:text-4xl">
              {notebook.name}
            </CardTitle>
            <CardDescription className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              {notebook.description || "Grounded notebook workspace for source-first research."}
            </CardDescription>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-10 w-10 rounded-full text-slate-500 hover:bg-slate-100"
            disabled
          >
            <Pencil className="h-4 w-4" />
            <span className="sr-only">Edit notebook</span>
          </Button>
        </div>
      </CardHeader>
    </Card>
  );
}

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
        <div className="mx-auto flex min-h-screen max-w-7xl items-center justify-center px-4 py-6 tablet:py-8">
          <Spinner size="lg" />
        </div>
      </div>
    );
  }

  if (!notebook) {
    return (
      <div className="min-h-screen">
        <div className="mx-auto max-w-3xl px-4 py-6 tablet:py-8">
          <Button
            variant="ghost"
            className="mb-4 w-full justify-start text-slate-700 xs:w-auto"
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
    <div className="min-h-screen bg-slate-50">
      {/* Desktop top bar */}
      <div className="hidden desktop:block sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center gap-6 px-6">
          <div className="flex items-center gap-2 text-slate-900">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <BookOpen className="h-4 w-4" />
            </div>
            <span className="text-sm font-semibold tracking-tight">
              Internal Knowledge Curator
            </span>
          </div>

          <div className="ml-auto flex items-center gap-3">
            <Button variant="ghost" size="icon" className="h-10 w-10 rounded-full" disabled>
              <Settings className="h-4 w-4" />
              <span className="sr-only">Settings</span>
            </Button>
          </div>
        </div>
      </div>

      <div className="mx-auto flex max-w-[1400px]">
        <main className="flex-1 px-4 py-6 tablet:px-6 desktop:px-10">
          <div className="mb-4">
            <Button
              variant="ghost"
              className="w-full justify-start text-slate-700 xs:w-auto desktop:text-sm"
              onClick={() => router.push("/notebooks")}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Notebooks
            </Button>
          </div>

          <div className="grid gap-6 desktop:grid-cols-[minmax(0,1fr)_minmax(340px,420px)] desktop:items-start">
            <section className="space-y-6">
              <NotebookOverviewCard notebook={notebook} />
              <NotebookWorkspace notebookId={notebook.id} />
            </section>

            <aside className="desktop:self-start desktop:sticky desktop:top-20">
              <ChatPanel notebookId={notebook.id} notebookName={notebook.name} variant="scholar" />
            </aside>
          </div>

          <div className="h-24 desktop:hidden" />
        </main>
      </div>

      {/* Mobile bottom nav */}
      <div className="desktop:hidden fixed bottom-0 left-0 right-0 z-50 border-t border-slate-200 bg-white">
        <div className="mx-auto grid max-w-md grid-cols-3 px-6 py-3 text-xs text-slate-500">
          <button
            type="button"
            className="flex flex-col items-center gap-1"
            onClick={() => router.push("/notebooks")}
          >
            <BookOpen className="h-5 w-5" />
            Notebooks
          </button>
          <button type="button" className="flex flex-col items-center gap-1 text-primary">
            <BookOpen className="h-5 w-5" />
            Sources
          </button>
          <button type="button" className="flex flex-col items-center gap-1" disabled>
            <Settings className="h-5 w-5" />
            Settings
          </button>
        </div>
      </div>
    </div>
  );
}

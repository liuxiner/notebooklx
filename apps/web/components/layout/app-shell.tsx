"use client";

import { useRouter } from "next/navigation";
import {
  BarChart3,
  BookOpen,
  Clock,
  LibraryBig,
  Plus,
  Search,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type ActiveNav = "notebooks" | "evaluation";

interface AppShellProps {
  activeNav: ActiveNav;
  children: React.ReactNode;
  /** Optional search bar content for the desktop top bar */
  searchBar?: React.ReactNode;
  /** Optional right-side actions for the desktop top bar */
  topBarActions?: React.ReactNode;
}

const NAV_ITEMS = [
  { key: "notebooks" as const, label: "Notebooks", icon: BookOpen, href: "/notebooks" },
  { key: "evaluation" as const, label: "Evaluation", icon: BarChart3, href: "/evaluation" },
  { key: "library" as const, label: "Library", icon: LibraryBig, disabled: true },
  { key: "history" as const, label: "History", icon: Clock, disabled: true },
];

export function AppShell({ activeNav, children, searchBar, topBarActions }: AppShellProps) {
  const router = useRouter();

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
            {searchBar}
            {topBarActions}
            <Button variant="ghost" size="icon" className="h-10 w-10 rounded-full" disabled>
              <Settings className="h-4 w-4" />
              <span className="sr-only">Settings</span>
            </Button>
          </div>
        </div>
      </div>

      <div className="mx-auto flex max-w-[1400px]">
        {/* Desktop sidebar */}
        <aside className="hidden desktop:flex w-64 flex-col gap-6 border-r border-slate-200 bg-white px-5 py-6 min-h-[calc(100vh-56px)] sticky top-14">
          <div>
            <p className="text-sm font-semibold text-slate-950">Curator Pro</p>
            <p className="text-xs text-slate-500">Senior Researcher</p>
          </div>

          <nav className="space-y-1 text-sm">
            {NAV_ITEMS.map((item) => {
              const isActive = item.key === activeNav;
              const Icon = item.icon;

              if (item.disabled) {
                return (
                  <button
                    key={item.key}
                    type="button"
                    className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-slate-400"
                    disabled
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </button>
                );
              }

              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => router.push(item.href!)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left font-medium transition-colors",
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </button>
              );
            })}
          </nav>

          <div className="mt-auto">
            <button
              type="button"
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
              disabled
            >
              <Plus className="h-4 w-4" />
              New Analysis
            </button>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 px-4 py-6 tablet:px-6 desktop:px-10">
          {children}
        </main>
      </div>

      {/* Mobile bottom nav */}
      <div className="desktop:hidden fixed bottom-0 left-0 right-0 z-50 border-t border-slate-200 bg-white">
        <div className="mx-auto grid max-w-md grid-cols-3 px-6 py-3 text-xs text-slate-500">
          <button
            type="button"
            onClick={() => router.push("/notebooks")}
            className={cn(
              "flex flex-col items-center gap-1",
              activeNav === "notebooks" ? "text-primary" : ""
            )}
          >
            <BookOpen className="h-5 w-5" />
            Notebooks
          </button>
          <button
            type="button"
            onClick={() => router.push("/evaluation")}
            className={cn(
              "flex flex-col items-center gap-1",
              activeNav === "evaluation" ? "text-primary" : ""
            )}
          >
            <BarChart3 className="h-5 w-5" />
            Evaluation
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

/**
 * Inline Button-like element used by AppShell top bar.
 * Extracted to avoid importing full Button with its dependencies.
 */
function Button({
  variant,
  size,
  className,
  disabled,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: string;
  size?: string;
}) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors",
        variant === "ghost" && "hover:bg-slate-100 hover:text-slate-900",
        size === "icon" && "h-10 w-10",
        disabled && "opacity-50 cursor-not-allowed",
        className
      )}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
}

/**
 * Reusable mobile top bar brand component.
 * Used by pages that need a mobile brand header inside the main content area.
 */
export function MobileBrandHeader() {
  return (
    <div className="desktop:hidden mb-4 flex items-center justify-between">
      <div className="flex items-center gap-2 text-slate-900">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <BookOpen className="h-4 w-4" />
        </div>
        <span className="text-xs font-semibold tracking-tight">
          Internal Knowledge Curator
        </span>
      </div>
    </div>
  );
}

"use client";

import React, { type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { CitationMarker } from "@/components/chat/citation-marker";
import type { ChatCitation } from "@/lib/chat-stream";

interface MarkdownWithCitationsProps {
  content: string;
  citations: ChatCitation[];
  activeCitationIndex: number | null | undefined;
  onCitationSelect?: (index: number, target?: HTMLButtonElement) => void;
  className?: string;
}

const CITATION_PATTERN = /(\[\d+\])/g;

/**
 * Split a text string into segments, rendering citation markers
 * as CitationMarker components and everything else as text.
 */
function renderTextWithCitations(
  text: string,
  citationIndexSet: Set<number>,
  activeCitationIndex: number | null | undefined,
  onCitationSelect?: (index: number, target?: HTMLButtonElement) => void,
): ReactNode[] {
  const segments = text.split(CITATION_PATTERN).filter(Boolean);
  return segments.map((segment, index) => {
    const match = /^\[(\d+)\]$/.exec(segment);
    if (!match) return <span key={`text-${index}`}>{segment}</span>;

    const citationIndex = Number(match[1]);
    if (!citationIndexSet.has(citationIndex)) {
      return <span key={`text-${index}`}>{segment}</span>;
    }

    return (
      <CitationMarker
        key={`citation-${citationIndex}-${index}`}
        index={citationIndex}
        isActive={activeCitationIndex === citationIndex}
        onSelect={onCitationSelect}
      />
    );
  });
}

/**
 * Recursively process React children to inject CitationMarker components
 * wherever [N] patterns appear in text nodes.
 */
function processChildrenWithCitations(
  children: ReactNode,
  citationIndexSet: Set<number>,
  activeCitationIndex: number | null | undefined,
  onCitationSelect?: (index: number, target?: HTMLButtonElement) => void,
): ReactNode {
  if (typeof children === "string") {
    if (!CITATION_PATTERN.test(children)) {
      return children;
    }
    CITATION_PATTERN.lastIndex = 0;
    const result = renderTextWithCitations(children, citationIndexSet, activeCitationIndex, onCitationSelect);
    return <>{result}</>;
  }

  if (typeof children === "number") {
    return children;
  }

  if (Array.isArray(children)) {
    return (
      <>
        {children.map((child, i) =>
          // eslint-disable-next-line @typescript-eslint/no-unnecessary-type-assertion
          React.isValidElement(child)
            ? processChildrenWithCitations(child, citationIndexSet, activeCitationIndex, onCitationSelect)
            : processChildrenWithCitations(child, citationIndexSet, activeCitationIndex, onCitationSelect),
        )}
      </>
    );
  }

  if (React.isValidElement(children)) {
    const childContent = children.props.children;
    if (childContent === undefined || childContent === null) return children;
    const processedChildren = processChildrenWithCitations(
      childContent,
      citationIndexSet,
      activeCitationIndex,
      onCitationSelect,
    );
    return React.cloneElement(children, undefined, processedChildren);
  }

  return children;
}

export function MarkdownWithCitations({
  content,
  citations,
  activeCitationIndex,
  onCitationSelect,
  className,
}: MarkdownWithCitationsProps) {
  const citationIndexSet = new Set(citations.map((c) => c.citation_index));

  const processChildren = (children: ReactNode) =>
    processChildrenWithCitations(children, citationIndexSet, activeCitationIndex, onCitationSelect);

  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => (
            <p className="mb-3 last:mb-0 leading-7">{processChildren(children)}</p>
          ),
          li: ({ children }) => (
            <li className="mb-1 leading-7">{processChildren(children)}</li>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-slate-900">{processChildren(children)}</strong>
          ),
          em: ({ children }) => <em>{processChildren(children)}</em>,
          h1: ({ children }) => (
            <h1 className="mb-3 mt-6 text-xl font-bold text-slate-900 first:mt-0">
              {processChildren(children)}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-2 mt-5 text-lg font-bold text-slate-900 first:mt-0">
              {processChildren(children)}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-2 mt-4 text-base font-bold text-slate-900 first:mt-0">
              {processChildren(children)}
            </h3>
          ),
          ul: ({ children }) => <ul className="mb-3 list-disc space-y-1 pl-6 last:mb-0">{children}</ul>,
          ol: ({ children }) => <ol className="mb-3 list-decimal space-y-1 pl-6 last:mb-0">{children}</ol>,
          blockquote: ({ children }) => (
            <blockquote className="my-3 border-l-3 border-slate-300 pl-4 text-slate-600">{children}</blockquote>
          ),
          code: ({ className: codeClassName, children }) => {
            const isInline = !codeClassName;
            if (isInline) {
              return (
                <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-sm text-slate-800">
                  {children}
                </code>
              );
            }
            return (
              <pre className="my-3 overflow-x-auto rounded-xl bg-slate-900 p-4 font-mono text-sm text-slate-100">
                <code>{children}</code>
              </pre>
            );
          },
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#4f46e5] underline decoration-[#4f46e5]/30 underline-offset-2 hover:decoration-[#4f46e5]"
            >
              {children}
            </a>
          ),
          hr: () => <hr className="my-4 border-slate-200" />,
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto">
              <table className="w-full border-collapse text-sm">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-slate-200 bg-slate-50 px-3 py-2 text-left font-semibold">
              {processChildren(children)}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-slate-200 px-3 py-2">{processChildren(children)}</td>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

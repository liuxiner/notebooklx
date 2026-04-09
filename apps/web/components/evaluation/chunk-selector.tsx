/**
 * Chunk Selector Component
 *
 * Allows users to select source chunks as ground truth for evaluation tests.
 */
"use client";

import { useEffect, useState } from "react";
import { evaluationApi, type ChunkItem } from "@/lib/evaluation-api";
import { Checkbox } from "@/components/ui/checkbox";
import { Spinner } from "@/components/ui/spinner";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";

interface ChunkSelectorProps {
  notebookId: string;
  selectedChunkIds: string[];
  onSelectionChange: (chunkIds: string[]) => void;
}

export default function ChunkSelector({ notebookId, selectedChunkIds, onSelectionChange }: ChunkSelectorProps) {
  const [chunks, setChunks] = useState<ChunkItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    const fetchChunks = async () => {
      setLoading(true);
      setError(null);
      setSearchQuery("");
      try {
        const result = await evaluationApi.getNotebookChunks(notebookId, 100, 0);
        setChunks(result.chunks);
      } catch (err) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Failed to load chunks");
        }
      } finally {
        setLoading(false);
      }
    };

    if (notebookId) {
      fetchChunks();
    }
  }, [notebookId]);

  const filteredChunks = chunks.filter((chunk) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return chunk.content.toLowerCase().includes(query) || chunk.source_title.toLowerCase().includes(query);
  });

  const handleToggleChunk = (chunkId: string) => {
    if (selectedChunkIds.includes(chunkId)) {
      onSelectionChange(selectedChunkIds.filter((id) => id !== chunkId));
    } else {
      onSelectionChange([...selectedChunkIds, chunkId]);
    }
  };

  const handleCheckedChange = (chunkId: string, checked: boolean | "indeterminate") => {
    if (checked) {
      if (!selectedChunkIds.includes(chunkId)) {
        onSelectionChange([...selectedChunkIds, chunkId]);
      }
      return;
    }

    onSelectionChange(selectedChunkIds.filter((id) => id !== chunkId));
  };

  const handleToggleAll = () => {
    const filteredIds = filteredChunks.map((chunk) => chunk.id);
    const allFilteredSelected =
      filteredIds.length > 0 && filteredIds.every((chunkId) => selectedChunkIds.includes(chunkId));

    if (allFilteredSelected) {
      onSelectionChange(selectedChunkIds.filter((chunkId) => !filteredIds.includes(chunkId)));
    } else {
      onSelectionChange([...selectedChunkIds, ...filteredIds.filter((chunkId) => !selectedChunkIds.includes(chunkId))]);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Spinner />
      </div>
    );
  }

  if (error) {
    return <div className="text-sm text-destructive py-4">{error}</div>;
  }

  if (chunks.length === 0) {
    return (
      <div className="text-sm text-slate-500 py-4">No chunks available. Please ensure sources have been ingested.</div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <Input
          type="text"
          placeholder="Search chunks..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Select All */}
      <div className="flex items-center gap-2 pb-2 border-b border-slate-200">
        <Checkbox
          id="select-all"
          checked={filteredChunks.length > 0 && filteredChunks.every((chunk) => selectedChunkIds.includes(chunk.id))}
          onCheckedChange={handleToggleAll}
        />
        <label htmlFor="select-all" className="text-sm font-medium cursor-pointer">
          Select All ({selectedChunkIds.length} selected)
        </label>
      </div>

      {/* Chunk List */}
      <div className="h-[400px] overflow-y-auto rounded-md border border-slate-200">
        <div className="p-4 space-y-3">
          {filteredChunks.map((chunk) => (
            <div
              key={chunk.id}
              className="flex items-start gap-3 rounded-md border border-slate-200 p-3 hover:bg-slate-50"
            >
              <Checkbox
                aria-label={`Select ${chunk.source_title} chunk ${chunk.chunk_index + 1}`}
                checked={selectedChunkIds.includes(chunk.id)}
                onCheckedChange={(checked) => handleCheckedChange(chunk.id, checked)}
                className="mt-1"
              />
              <button
                type="button"
                className="flex-1 min-w-0 text-left"
                onClick={() => handleToggleChunk(chunk.id)}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium text-slate-700">{chunk.source_title}</span>
                  <span className="text-xs text-slate-500">Chunk #{chunk.chunk_index}</span>
                  <span className="text-xs text-slate-500">{`Page ${chunk.metadata.page ?? "1"}`}</span>
                </div>
                <p className="text-sm text-slate-600 line-clamp-3">{chunk.preview}</p>
                <div className="text-xs text-slate-400 mt-1">{chunk.token_count} tokens</div>
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

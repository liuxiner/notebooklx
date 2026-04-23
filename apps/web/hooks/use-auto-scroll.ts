import { useCallback, useEffect, useRef } from "react";

interface UseAutoScrollOptions {
  /** Ref to the scrollable container element */
  containerRef: React.RefObject<HTMLElement | null>;
  /** Ref to the bottom sentinel element */
  bottomRef: React.RefObject<HTMLElement | null>;
  /** Dependencies that trigger auto-scroll when user is near bottom */
  deps: unknown[];
  /** Distance from bottom in px to consider "near bottom". Default 150. */
  threshold?: number;
}

/**
 * Auto-scrolls to bottom when content changes, but only if the user
 * is already near the bottom of the scroll container. When forceScroll
 * is called, it scrolls regardless of position (used on new user message).
 */
export function useAutoScroll({
  containerRef,
  bottomRef,
  deps,
  threshold = 150,
}: UseAutoScrollOptions) {
  const isNearBottomRef = useRef(true);
  const forceScrollRef = useRef(false);

  // Track scroll position
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      isNearBottomRef.current = scrollHeight - scrollTop - clientHeight < threshold;
    };

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => container.removeEventListener("scroll", handleScroll);
  }, [containerRef, threshold]);

  // Auto-scroll when deps change
  useEffect(() => {
    if (!isNearBottomRef.current && !forceScrollRef.current) {
      return;
    }

    forceScrollRef.current = false;
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  const forceScroll = useCallback(() => {
    forceScrollRef.current = true;
    isNearBottomRef.current = true;
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [bottomRef]);

  return { forceScroll };
}

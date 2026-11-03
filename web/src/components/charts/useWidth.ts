// A chart is drawn at its container's width in pixels, so its text keeps its size on any screen (the MVP report
// measured its boxes the same way). Until the container is measured — and in tests, where nothing has a size — the
// fallback width stands. The container itself is kept too: a touch's tip stays until a press outside it.

import { type RefCallback, type RefObject, useCallback, useRef, useState } from "react";

export function useWidth(fallback = 640): [RefCallback<HTMLDivElement>, number, RefObject<HTMLDivElement | null>] {
  const [width, setWidth] = useState(fallback);
  const box = useRef<HTMLDivElement | null>(null);
  const ref = useCallback<RefCallback<HTMLDivElement>>((node) => {
    box.current = node;
    if (!node) {
      return undefined;
    }
    const measure = () => {
      const measured = Math.floor(node.clientWidth);
      if (measured > 0) {
        setWidth(measured);
      }
    };
    measure();
    if (typeof ResizeObserver === "undefined") {
      return undefined;
    }
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return [ref, width, box];
}

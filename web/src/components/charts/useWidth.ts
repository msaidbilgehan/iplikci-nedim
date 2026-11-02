// A chart is drawn at its container's width in pixels, so its text keeps its size on any screen (the MVP report
// measured its boxes the same way). Until the container is measured — and in tests, where nothing has a size — the
// fallback width stands.

import { type RefCallback, useCallback, useState } from "react";

export function useWidth(fallback = 640): [RefCallback<HTMLDivElement>, number] {
  const [width, setWidth] = useState(fallback);
  const ref = useCallback<RefCallback<HTMLDivElement>>((node) => {
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
  return [ref, width];
}

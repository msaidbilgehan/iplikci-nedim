import { type ComponentPropsWithoutRef, type RefObject, useEffect, useRef, useState } from "react";

import { cn } from "../../lib/cn";

interface ScrollRegion {
  label: string | null; // the table's caption, which names the region
}

/**
 * Whether the wrapper scrolls sideways now, checked again as it or its table changes size. A table wider than a phone's
 * screen scrolls; the keyboard must reach it then (WCAG 2.1.1; axe's scrollable-region-focusable).
 */
function useScrollRegion(wrapper: RefObject<HTMLDivElement | null>): ScrollRegion | null {
  const [region, setRegion] = useState<ScrollRegion | null>(null);
  useEffect(() => {
    const element = wrapper.current;
    if (!element) {
      return undefined;
    }
    const check = () => {
      const scrolls = element.scrollWidth > element.clientWidth;
      const label = element.querySelector("caption")?.textContent?.trim() || null;
      setRegion((was) => (!scrolls ? null : was?.label === label ? was : { label }));
    };
    check();
    if (typeof ResizeObserver === "undefined") {
      return undefined;
    }
    const observer = new ResizeObserver(check);
    observer.observe(element);
    if (element.firstElementChild) {
      observer.observe(element.firstElementChild);
    }
    return () => observer.disconnect();
  }, [wrapper]);
  return region;
}

export function Table({ className, ...rest }: ComponentPropsWithoutRef<"table">) {
  const wrapper = useRef<HTMLDivElement>(null);
  const region = useScrollRegion(wrapper);
  return (
    <div
      ref={wrapper}
      tabIndex={region ? 0 : undefined}
      role={region?.label ? "region" : undefined}
      aria-label={region?.label ?? undefined}
      className={cn(
        "overflow-x-auto",
        region && "rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
      )}
    >
      <table className={cn("w-full border-collapse text-left text-sm", className)} {...rest} />
    </div>
  );
}

export function Th({ className, ...rest }: ComponentPropsWithoutRef<"th">) {
  return (
    <th
      scope="col"
      className={cn(
        "border-b border-zinc-200 px-2 py-2 font-medium text-zinc-600 dark:border-zinc-700 dark:text-zinc-300",
        className,
      )}
      {...rest}
    />
  );
}

export function Td({ className, ...rest }: ComponentPropsWithoutRef<"td">) {
  return (
    <td className={cn("border-b border-zinc-100 px-2 py-2 align-top dark:border-zinc-800", className)} {...rest} />
  );
}

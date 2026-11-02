// Views of one thing, one shown at a time (Radix Tabs): the arrow keys move between the tabs and Tab goes on into the
// shown panel. Two looks: a line under the chosen tab for a screen's sections, and joined buttons for a small switch
// such as a chart's "Grafik / Tablo".

import * as RadixTabs from "@radix-ui/react-tabs";
import { type ComponentPropsWithoutRef, createContext, useContext } from "react";

import { cn } from "../../lib/cn";

type Look = "line" | "segmented";

const LookContext = createContext<Look>("line");
const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600";

export const Tabs = RadixTabs.Root;

interface TabListProps extends ComponentPropsWithoutRef<typeof RadixTabs.List> {
  look?: Look;
}

export function TabList({ look = "line", className, ...rest }: TabListProps) {
  return (
    <LookContext value={look}>
      <RadixTabs.List
        className={cn(
          look === "line"
            ? "flex flex-wrap gap-1 border-b border-zinc-200 dark:border-zinc-700"
            : "inline-flex rounded-md border border-zinc-300 bg-white p-0.5 dark:border-zinc-600 dark:bg-zinc-800",
          className,
        )}
        {...rest}
      />
    </LookContext>
  );
}

export function Tab({ className, ...rest }: ComponentPropsWithoutRef<typeof RadixTabs.Trigger>) {
  const look = useContext(LookContext);
  return (
    <RadixTabs.Trigger
      className={cn(
        "inline-flex items-center justify-center text-sm font-medium",
        FOCUS,
        look === "line"
          ? cn(
              "-mb-px min-h-11 border-b-2 border-transparent px-3",
              "text-zinc-700 hover:text-zinc-950 dark:text-zinc-300 dark:hover:text-zinc-50",
              "data-[state=active]:border-teal-700 data-[state=active]:text-teal-900",
              "dark:data-[state=active]:border-teal-400 dark:data-[state=active]:text-teal-100",
            )
          : cn(
              "min-h-8 rounded px-2.5",
              "text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-700",
              "data-[state=active]:bg-teal-700 data-[state=active]:text-white",
              "dark:data-[state=active]:bg-teal-400 dark:data-[state=active]:text-zinc-950",
            ),
        className,
      )}
      {...rest}
    />
  );
}

export function TabPanel({ className, ...rest }: ComponentPropsWithoutRef<typeof RadixTabs.Content>) {
  return <RadixTabs.Content className={cn("rounded-sm", FOCUS, className)} {...rest} />;
}

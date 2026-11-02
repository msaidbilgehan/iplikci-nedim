// A long screen in parts, one shown at a time (Radix Tabs, ui/Tabs): the chosen part lives in the address
// (?bolum=<id>), so a link can lead to it and the browser's back button returns to it. The first part is the default and
// leaves the address clean. A part that is not shown is not rendered, so its data is asked for only when it is opened.

import type { ReactNode } from "react";
import { useSearchParams } from "react-router";

import { Tab, TabList, TabPanel, Tabs } from "./Tabs";

export const SECTION_PARAM = "bolum";

export interface Section {
  id: string; // the address's word for it: "harcamalar"
  label: string;
  badge?: ReactNode; // a count beside the label
  content: () => ReactNode;
}

interface SectionTabsProps {
  label: string; // the tab list's name for screen readers: "Değerlendirmenin bölümleri"
  sections: readonly Section[];
}

/** The part the address names, or the first. */
export function chosenSection(params: URLSearchParams, sections: readonly { id: string }[]): string {
  const named = params.get(SECTION_PARAM);
  return sections.find((section) => section.id === named)?.id ?? sections[0]?.id ?? "";
}

export function SectionTabs({ label, sections }: SectionTabsProps) {
  const [params, setParams] = useSearchParams();
  const chosen = chosenSection(params, sections);
  const first = sections[0]?.id;
  const choose = (id: string) =>
    setParams(
      (was) => {
        const next = new URLSearchParams(was);
        if (id === first) {
          next.delete(SECTION_PARAM);
        } else {
          next.set(SECTION_PARAM, id);
        }
        return next;
      },
      { replace: true },
    );
  return (
    <Tabs value={chosen} onValueChange={choose} className="flex flex-col gap-5">
      <TabList aria-label={label}>
        {sections.map((section) => (
          <Tab key={section.id} value={section.id} className="shrink-0 gap-2">
            {section.label}
            {/* The space keeps the count a word of its own in the tab's name: "Yaklaşanlar 3". */}
            {section.badge ? <> {section.badge}</> : null}
          </Tab>
        ))}
      </TabList>
      {sections.map((section) => (
        <TabPanel key={section.id} value={section.id} className="flex flex-col gap-6">
          {section.id === chosen ? section.content() : null}
        </TabPanel>
      ))}
    </Tabs>
  );
}

/** A count beside a part's name: a number to see; the words come with the label. */
export function SectionCount({ count }: { count: number }) {
  if (count <= 0) {
    return null;
  }
  return (
    <span className="inline-flex min-w-5 items-center justify-center rounded-full bg-zinc-200 px-1.5 text-xs font-semibold text-zinc-800 dark:bg-zinc-700 dark:text-zinc-100">
      {count}
    </span>
  );
}

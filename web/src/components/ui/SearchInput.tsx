// A screen's text search, sent once the typing pauses: the address keeps one entry for it, not one per letter. When the
// address changes from elsewhere (a chip took the search off), the box follows it.

import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";

import { cn } from "../../lib/cn";

const SEARCH_MS = 300; // the search waits for a pause in the typing
const INPUT = cn(
  "min-h-11 w-full rounded-md border px-3 text-sm",
  "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);

interface SearchInputProps {
  label: string;
  hint: string; // where it looks: "Açıklama, işyeri, not ya da etiket"
  value: string; // the search the address holds
  onChange: (q: string) => void;
}

export function SearchInput({ label, hint, value, onChange }: SearchInputProps) {
  const id = useId();
  const hintId = useId();
  const [text, setText] = useState(value);
  const latest = useRef(onChange);
  const sent = useRef(value);
  useLayoutEffect(() => {
    latest.current = onChange;
  });
  useEffect(() => {
    // The address changed from elsewhere (a chip took the search off): the box follows it.
    if (value !== sent.current) {
      sent.current = value;
      setText(value);
    }
  }, [value]);
  useEffect(() => {
    if (text.trim() === sent.current.trim()) {
      return undefined;
    }
    const timer = setTimeout(() => {
      sent.current = text.trim();
      latest.current(text);
    }, SEARCH_MS);
    return () => clearTimeout(timer);
  }, [text]);
  return (
    // Wide enough to type in, or on a line of its own on a phone's screen.
    <div className="flex min-w-60 flex-1 flex-col gap-1 text-sm">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="search"
        value={text}
        aria-describedby={hintId}
        onChange={(event) => setText(event.target.value)}
        className={INPUT}
      />
      <span id={hintId} className="text-xs text-zinc-600 dark:text-zinc-300">
        {hint}
      </span>
    </div>
  );
}

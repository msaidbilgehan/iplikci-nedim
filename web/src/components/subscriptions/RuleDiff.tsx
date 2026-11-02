// A rule edit's difference in the user's rule file, as the service writes it (a unified diff): a line it adds starts
// with +, one it takes away with -, so the marks say it and the colours only follow them. Long lines wrap: the panel
// never scrolls sideways.

import { cn } from "../../lib/cn";

const ADDED = "bg-emerald-50 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-100";
const REMOVED = "bg-red-50 text-red-900 dark:bg-red-950 dark:text-red-100";
const MARGIN = "text-zinc-600 dark:text-zinc-400"; // the file's names and the hunks' places

function toneOf(line: string): string {
  if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("@@")) {
    return MARGIN;
  }
  if (line.startsWith("+")) {
    return ADDED;
  }
  return line.startsWith("-") ? REMOVED : "";
}

export function RuleDiff({ diff }: { diff: string }) {
  return (
    <pre
      className={cn(
        "rounded-md border border-zinc-200 bg-zinc-50 p-2 text-xs leading-5 dark:border-zinc-700 dark:bg-zinc-950",
        "text-zinc-900 dark:text-zinc-100",
      )}
    >
      {diff.split("\n").map((line, index) => (
        // The lines of one difference never move or change: a line's place in it is its key.
        <span key={`${index}:${line}`} className={cn("block px-1 break-words whitespace-pre-wrap", toneOf(line))}>
          {line || " "}
        </span>
      ))}
    </pre>
  );
}

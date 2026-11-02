// The month's pace as a bar (F05, F06): what was spent so far against the typical month, with a mark where the typical
// month stood on the same day. The numbers are written beside it; the bar only repeats them for the eye, so it is
// hidden from screen readers. Without a typical month there is nothing to measure against and no bar.

import type { Pace } from "../api/types";

export function PaceMeter({ pace }: { pace: Pace }) {
  if (pace.typical === null || pace.typical.minor <= 0) {
    return null;
  }
  const scale = Math.max(pace.typical.minor, pace.spent.minor);
  const share = (minor: number) => `${Math.min(100, Math.max(0, (minor / scale) * 100))}%`;
  return (
    <div aria-hidden="true" className="relative my-3 h-3 rounded-full bg-zinc-200 dark:bg-zinc-700">
      <div className="h-3 rounded-full bg-chart-accent" style={{ width: share(pace.spent.minor) }} />
      {pace.by_day ? (
        <div
          className="absolute -top-1 h-5 w-0.5 -translate-x-1/2 rounded bg-zinc-900 dark:bg-zinc-100"
          style={{ left: share(pace.by_day.minor) }}
        />
      ) : null}
    </div>
  );
}

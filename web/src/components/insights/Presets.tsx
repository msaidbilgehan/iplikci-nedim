// The period presets the MVP report offered ("Son 3 ay" … "Tümü"): each writes its days into the address's from and to,
// which the date fields beside them show; the one the address is reads as pressed. Their bounds are the data's first
// and last month in the accounts kept, so "Son 3 ay" means the newest three months with documents.

import { useTranslation } from "react-i18next";

import type { SpendingPeriod } from "../../api/types";
import { cn } from "../../lib/cn";
import { type Preset, PRESETS, presetOf, presetRange } from "./query";

interface PresetsProps {
  period: SpendingPeriod;
  params: URLSearchParams;
  onChoose: (range: { from: string; to: string } | null) => void;
}

export function Presets({ period, params, onChoose }: PresetsProps) {
  const { t } = useTranslation("insights");
  const chosen = presetOf(params, period.first, period.last);
  // The year before the data's last has no rows when the data begins in the last one's year.
  const isEmpty = (preset: Preset) => preset === "lastYear" && period.first.slice(0, 4) === period.last.slice(0, 4);
  return (
    <div role="group" aria-label={t("presets.label")} className="flex flex-wrap items-center gap-2">
      <span aria-hidden="true" className="text-sm text-zinc-700 dark:text-zinc-300">
        {t("presets.label")}
      </span>
      <div
        className={cn(
          "inline-flex flex-wrap rounded-md border p-0.5",
          "border-zinc-300 bg-white dark:border-zinc-600 dark:bg-zinc-800",
        )}
      >
        {PRESETS.map((preset) => (
          <button
            key={preset}
            type="button"
            aria-pressed={chosen === preset}
            disabled={isEmpty(preset)}
            onClick={() => onChoose(presetRange(preset, period.first, period.last))}
            className={cn(
              "inline-flex min-h-10 items-center rounded px-2.5 text-sm font-medium",
              "text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-700",
              "aria-pressed:bg-teal-700 aria-pressed:text-white",
              "dark:aria-pressed:bg-teal-400 dark:aria-pressed:text-zinc-950",
              "disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
            )}
          >
            {t(`presets.${preset}`)}
          </button>
        ))}
      </div>
    </div>
  );
}

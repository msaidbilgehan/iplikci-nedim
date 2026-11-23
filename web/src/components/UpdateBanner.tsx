// A new version of the program, told on every screen (ADR-0022, F21). In "ask" mode, or when an install by itself did
// not come up, the banner asks: one button installs it, and a fold shows what it brings. While a version installs, by
// itself in "auto" or as the user asked, it says so. A copy installed by hand is told where to get it. The Settings
// screen's Güncellemeler card holds the same, so the banner leaves that screen alone.

import { useId } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router";

import { useInstallUpdate, useUpdate } from "../api/queries";
import type { UpdateRelease, UpdateState } from "../api/types";
import { cn } from "../lib/cn";
import { formatSize } from "../lib/format";
import { ReleaseNotes } from "./settings/UpdatesCard";
import { Button } from "./ui/Button";
import { InfoIcon } from "./ui/Icons";

const SETTINGS = "/ayarlar";
const BOX = cn(
  "mb-6 flex gap-3 rounded-md border p-3 text-sm",
  "border-teal-300 bg-teal-50 text-teal-950 dark:border-teal-800 dark:bg-teal-950 dark:text-teal-50",
);
const LINK = cn(
  "font-medium underline underline-offset-2 text-teal-800 hover:text-teal-950 dark:text-teal-200 dark:hover:text-white",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);

export function UpdateBanner() {
  const { pathname } = useLocation();
  const found = useUpdate().data;
  if (!found || pathname === SETTINGS) {
    return null;
  }
  if (found.installing) {
    return <Installing version={found.installing} />;
  }
  if (!found.available) {
    return null;
  }
  return found.automatic && found.available.size > 0 ? (
    <Ready state={found} release={found.available} />
  ) : (
    <ByHand release={found.available} />
  );
}

function Installing({ version }: { version: string }) {
  const { t } = useTranslation("shell");
  return (
    <div role="status" aria-live="polite" className={BOX}>
      <InfoIcon className="mt-0.5 size-5 shrink-0" />
      <div>
        <p className="font-semibold">{t("update.installing", { version })}</p>
        <p className="mt-1">{t("update.installingText")}</p>
      </div>
    </div>
  );
}

/** The version found, to install with one button: in "ask" mode, or after an install by itself that failed. */
function Ready({ state, release }: { state: UpdateState; release: UpdateRelease }) {
  const { t } = useTranslation("shell");
  const install = useInstallUpdate();
  const title = useId();
  const failed = state.last !== null && !state.last.ok && state.last.to_version === release.version;
  return (
    <section aria-labelledby={title} className={BOX}>
      <InfoIcon className="mt-0.5 size-5 shrink-0" />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <p id={title} className="font-semibold">
          {t("update.ready", { version: release.version })}
        </p>
        <p>
          {failed ? t("update.failedText") : t("update.readyText")}{" "}
          {failed ? (
            <Link to={SETTINGS} className={LINK}>
              {t("update.settings")}
            </Link>
          ) : null}
        </p>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Button disabled={install.isPending || install.isSuccess} onClick={() => install.mutate()}>
            {t("update.install", { size: formatSize(release.size) })}
          </Button>
          {release.notes ? (
            <details className="min-w-0">
              <summary className={cn("inline-flex min-h-11 cursor-pointer items-center", LINK)}>
                {t("update.notes")}
              </summary>
              <div className="mt-2">
                <ReleaseNotes text={release.notes} />
              </div>
            </details>
          ) : null}
        </div>
        {install.isError ? (
          <p role="alert" className="font-medium text-red-800 dark:text-red-200">
            {t("update.refused", { error: install.error.message })}
          </p>
        ) : null}
      </div>
    </section>
  );
}

/** A copy installed by hand cannot install itself: the release's page has its installer. */
function ByHand({ release }: { release: UpdateRelease }) {
  const { t } = useTranslation("shell");
  const title = useId();
  return (
    <section aria-labelledby={title} className={BOX}>
      <InfoIcon className="mt-0.5 size-5 shrink-0" />
      <div className="flex flex-col gap-1">
        <p id={title} className="font-semibold">
          {t("update.released", { version: release.version })}
        </p>
        <p>
          {t("update.byHandText")}{" "}
          <a
            href={release.page}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`${t("update.page")} ${t("update.newTab")}`}
            className={LINK}
          >
            {t("update.page")}
          </a>
        </p>
      </div>
    </section>
  );
}

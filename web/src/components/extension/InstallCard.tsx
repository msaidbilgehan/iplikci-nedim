// Installing the browser extension (ADR-0016, K20): until it is in a store, the browser loads it unpacked from a
// folder the service keeps in the data folder. The card has the service make that folder and show it in the file
// manager, gives its path and the extensions page's address to copy, and walks through the browser's steps.

import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useExtension, useShowExtensionFolder } from "../../api/queries";
import { Failure } from "../QueryState";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";

const EXTENSIONS_PAGE = "chrome://extensions"; // a page may not link it: the user types or pastes it

export function InstallCard() {
  const { t } = useTranslation("extension");
  const extension = useExtension();
  const show = useShowExtensionFolder();
  const folder = show.data?.folder ?? extension.data?.folder ?? "";
  const unavailable = extension.data?.available === false;
  const stale = extension.data !== undefined && extension.data.folder !== "" && !extension.data.current;
  return (
    <Card title={t("install.title")}>
      <div className="flex max-w-3xl flex-col gap-3 text-sm">
        <p className="text-zinc-700 dark:text-zinc-300">{t("install.intro")}</p>
        {extension.isError ? <Failure error={extension.error} onRetry={() => void extension.refetch()} /> : null}
        {unavailable ? (
          <Alert tone="warning" title={t("install.unavailableTitle")}>
            <p>{t("install.unavailableText")}</p>
          </Alert>
        ) : null}
        <ol className="flex list-decimal flex-col gap-3 pl-5">
          <li>
            <div className="flex flex-col gap-2">
              <p>{t("install.stepFolder")}</p>
              <Button
                className="self-start"
                onClick={() => show.mutate()}
                disabled={show.isPending || unavailable || extension.isPending}
              >
                {folder ? t("install.showAgain") : t("install.show")}
              </Button>
              {show.data ? (
                <p role="status" className="text-zinc-700 dark:text-zinc-300">
                  {show.data.opened ? t("install.opened") : t("install.notOpened")}
                </p>
              ) : null}
              {show.isError ? <Failure error={show.error} onRetry={() => show.mutate()} /> : null}
              {folder ? <Copyable label={t("install.folderLabel")} text={folder} /> : null}
              {stale && !show.data ? <p className="text-amber-800 dark:text-amber-200">{t("install.stale")}</p> : null}
            </div>
          </li>
          <li>
            <div className="flex flex-col gap-2">
              <p>{t("install.stepPage")}</p>
              <Copyable label={t("install.pageLabel")} text={EXTENSIONS_PAGE} />
              <p className="text-zinc-600 dark:text-zinc-400">{t("install.otherBrowsers")}</p>
            </div>
          </li>
          <li>{t("install.stepDeveloper")}</li>
          <li>
            <p>{t("install.stepLoad")}</p>
            <p className="mt-1 text-zinc-600 dark:text-zinc-400">{t("install.stepLoadHint")}</p>
          </li>
          <li>{t("install.stepDone")}</li>
        </ol>
        <p className="text-zinc-600 dark:text-zinc-400">{t("install.keep")}</p>
      </div>
    </Card>
  );
}

type Copied = "idle" | "done" | "failed";

/** A path or an address in full, with a button that puts it on the clipboard and says whether it did. */
function Copyable({ label, text }: { label: string; text: string }) {
  const { t } = useTranslation("extension");
  const [copied, setCopied] = useState<Copied>("idle");
  const [shown, setShown] = useState(text);
  if (shown !== text) {
    setShown(text);
    setCopied("idle");
  }
  const copy = () => {
    if (navigator.clipboard === undefined) {
      setCopied("failed");
      return;
    }
    navigator.clipboard.writeText(text).then(
      () => setCopied("done"),
      () => setCopied("failed"),
    );
  };
  return (
    <div className="flex flex-col gap-1">
      <span className="text-zinc-600 dark:text-zinc-400">{label}</span>
      <div className="flex flex-wrap items-center gap-2">
        <code className="rounded bg-zinc-100 px-2 py-1 font-mono break-all text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100">
          {text}
        </code>
        <Button variant="secondary" onClick={copy} aria-label={t("install.copyNamed", { name: label })}>
          {t("install.copy")}
        </Button>
        <span aria-live="polite" className="text-zinc-700 dark:text-zinc-300">
          {copied === "done" ? t("install.copied") : copied === "failed" ? t("install.copyFailed") : ""}
        </span>
      </div>
    </div>
  );
}

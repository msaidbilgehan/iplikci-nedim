// The Belge ekle screen (F02, K24): where the documents the user downloads from their banks by hand come in, a whole
// folder of them or single files. What each document is comes from its content, never its file or folder name; the
// plan shows what happens to each before anything is kept, and the files stay where they are. From a phone, the
// paired Telegram bot takes them too (ADR-0021).

import { useTranslation } from "react-i18next";

import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { AddressStep } from "../components/ui/Say";
import { UploadPanel } from "./UploadPanel";

const STEPS = ["download", "gather", "choose", "check"] as const;

export default function AddDocumentsPage() {
  const { t } = useTranslation("documents");
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("add.title")} description={t("add.description")} />
      <UploadPanel title={t("add.panel")} />
      <Card title={t("add.how")}>
        <ol className="flex list-decimal flex-col gap-1.5 pl-5 text-sm">
          {STEPS.map((step) => (
            <li key={step}>{t(`add.steps.${step}`)}</li>
          ))}
        </ol>
        <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-zinc-700 dark:text-zinc-300">
          <span>{t("add.mail")}</span>
          <AddressStep to="/kurulum/eklenti" label={t("add.mailLink")} />
        </p>
        <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-zinc-700 dark:text-zinc-300">
          <span>{t("add.telegram")}</span>
          <AddressStep to="/bildirimler?bolum=kanallar" label={t("add.telegramLink")} />
        </p>
      </Card>
    </div>
  );
}

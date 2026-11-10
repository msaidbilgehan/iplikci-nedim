// The Settings screen (F17): the setup wizard's fields, to change at any time — the user's names and the company names,
// how e-mail comes in and from which day, how long backups are kept — a backup on request or put back, the service's
// state with stopping, restarting and removing it (ADR-0017), the program's own updates (ADR-0022, F21), the optional
// EVDS key that brings TÜFE (F12), and where
// the rest is set: the notifications, the browser extension, the documents, the non-bank senders and the wizard
// itself. Secrets are only entered, never shown; the e-mail address is shown masked. The detailed view adds the
// settings' raw values.
//
// A step that ends the service (components/settings/ServiceLife) replaces the cards with what happened: their
// questions could only fail while the service is gone, and a restored service needs a new session.

import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { useServiceState, useSettings } from "../api/queries";
import type { Settings } from "../api/types";
import { useView } from "../components/Preferences";
import { Failure, Loading } from "../components/QueryState";
import { BackupEditor, BackupNow } from "../components/settings/BackupField";
import { EvdsCard } from "../components/settings/EvdsKey";
import { LINK, MailEditor } from "../components/settings/MailFields";
import { BusinessNamesEditor, HINT, NamesEditor } from "../components/settings/NameList";
import { UpdatesCard } from "../components/settings/UpdatesCard";
import { BackupRestore, type Ending, EndingState, ServiceCard, showsCards } from "../components/settings/ServiceLife";
import { Card, Facts } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { Say } from "../components/ui/Say";
import { formatDay } from "../lib/format";

const SYSTEM = { screen: "system", id: "", query: {} } as const;

export default function SettingsPage() {
  const { t } = useTranslation("settings");
  const [ending, setEnding] = useState<Ending | null>(null);
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("page.title")} description={t("page.description")} />
      {ending ? <EndingState ending={ending} onChange={setEnding} /> : null}
      {showsCards(ending) ? <SettingsCards onEnding={setEnding} /> : null}
    </div>
  );
}

function SettingsCards({ onEnding }: { onEnding: (ending: Ending) => void }) {
  const settings = useSettings();
  return (
    <>
      {settings.isPending ? <Loading /> : null}
      {settings.isError ? <Failure error={settings.error} onRetry={() => void settings.refetch()} /> : null}
      {settings.data ? <Cards settings={settings.data} onEnding={onEnding} /> : null}
    </>
  );
}

function Cards({ settings, onEnding }: { settings: Settings; onEnding: (ending: Ending) => void }) {
  const { t } = useTranslation("settings");
  const { view } = useView();
  const names = (
    <Card title={t("page.names")}>
      <Say>{t("page.namesSay", { names: settings.names.length, companies: settings.business_names.length })}</Say>
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold">{t("page.yours")}</h3>
          <NamesEditor settings={settings} />
        </div>
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold">{t("page.companies")}</h3>
          <BusinessNamesEditor settings={settings} />
        </div>
      </div>
    </Card>
  );
  const mail = (
    <Card title={t("page.mail")}>
      <Say>{t("page.mailSay")}</Say>
      <MailEditor settings={settings} pairing="link" />
    </Card>
  );
  const backup = (
    <Card title={t("page.backup")}>
      <Say next={{ link: SYSTEM, label: t("page.backupNext") }}>
        {t("page.backupSay", { count: settings.backup_days })}
      </Say>
      <div className="flex flex-col gap-4">
        <BackupEditor settings={settings} />
        <BackupNow />
        <BackupRestore onEnding={onEnding} />
      </div>
    </Card>
  );
  const service = <ServiceCard home={settings.home} onEnding={onEnding} />;
  const evds = <EvdsCard />;
  const updates = <UpdatesCard />;
  const more = <MoreCard />;
  if (view === "simple") {
    // Two columns that do not move as a card grows: the names and e-mail on one side, the backups, the service and the
    // other screens on the other. A phone stacks them in the detailed view's order.
    return (
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-4">
          {names}
          {mail}
          {evds}
        </div>
        <div className="flex min-w-0 flex-col gap-4">
          {backup}
          {service}
          {updates}
          {more}
        </div>
      </div>
    );
  }
  return (
    <div className="grid items-start gap-4">
      {names}
      {mail}
      {backup}
      {service}
      {updates}
      {evds}
      {more}
      <RawCard settings={settings} />
    </div>
  );
}

// The screens where the rest is set, each with what it holds; all are built.
const ELSEWHERE = [
  ["/bildirimler", "notifications"],
  ["/kurulum/eklenti", "extension"],
  ["/kurulum/claude", "claude"],
  ["/belgeler", "documents"],
  ["/sistem", "system"],
  ["/kurulum", "setup"],
] as const;

function MoreCard() {
  const { t } = useTranslation("settings");
  return (
    <Card title={t("page.more")}>
      <Say>{t("page.moreSay")}</Say>
      <ul className="flex flex-col gap-3">
        {ELSEWHERE.map(([to, key]) => (
          <li key={key} className="flex flex-col gap-0.5 text-sm">
            <Link to={to} className={LINK}>
              {t(`page.links.${key}`)}
            </Link>
            <span className={HINT}>{t(`page.linkText.${key}`)}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** The settings as they are written, for the detailed view: codes and numbers, no secret and no full address. */
function RawCard({ settings }: { settings: Settings }) {
  const { t } = useTranslation("settings");
  const service = useServiceState().data;
  const mail = settings.mail;
  const facts: Array<[string, ReactNode]> = [
    [t("page.raw.home"), <code className="break-all">{settings.home}</code>],
    [t("page.raw.port"), <code>{settings.port}</code>],
    [t("page.raw.connector"), <code>{mail.connector}</code>],
    [t("page.raw.account"), mail.configured ? mail.address : t("page.raw.none")],
    [t("page.raw.server"), mail.server ? <code>{mail.server}</code> : "—"],
    [t("page.raw.start"), formatDay(mail.start)],
    [t("page.raw.banks"), <code className="break-all">{settings.bank_senders.join(", ")}</code>],
    [t("page.raw.backupDays"), String(settings.backup_days)],
    [t("page.raw.remote"), t("page.raw.remoteOff")],
  ];
  if (service) {
    facts.push(
      [t("page.raw.manager"), service.manager ? <code>{service.manager}</code> : "—"],
      [t("page.raw.registered"), service.registered ? t("page.raw.yes") : t("page.raw.no")],
    );
  }
  return (
    <Card title={t("page.raw.title")}>
      <Facts items={facts} />
    </Card>
  );
}

// What each step of the setup wizard asks (F17). The settings' own fields are the Settings screen's too
// (components/settings); installing and pairing the extension, the non-bank senders, the upload panel and the
// notification channels are the parts their screens show. No step needs a terminal (K14); the service's step and the
// remote access only say where they stand.

import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { useSystem } from "../../api/queries";
import type { Settings, SetupStep } from "../../api/types";
import { formatTime } from "../../lib/format";
import { OtherSendersCard } from "../../pages/SystemPage";
import { UploadPanel } from "../../pages/UploadPanel";
import { ChannelsCard } from "../notify/ChannelsCard";
import { TelegramCard } from "../notify/TelegramCard";
import { BusinessNamesEditor, HINT, NamesEditor } from "../settings/NameList";
import { LINK, MailEditor } from "../settings/MailFields";
import { Facts } from "../ui/Card";

interface StepContentProps {
  step: SetupStep;
  done: boolean;
  settings: Settings;
}

export function StepContent({ step, done, settings }: StepContentProps) {
  const { t } = useTranslation("setup");
  const about = t(`about.${step}`, { defaultValue: "" });
  return (
    <div className="flex flex-col gap-4">
      {about ? <p className={HINT}>{about}</p> : null}
      <Fields step={step} done={done} settings={settings} />
    </div>
  );
}

function Fields({ step, done, settings }: StepContentProps) {
  const { t } = useTranslation("setup");
  switch (step) {
    case "data_folder":
      return (
        <div className="flex flex-col gap-3">
          <Facts items={[[t("folder"), <code className="break-all">{settings.home}</code>]]} />
          {/* ADR-0025: a new computer brings the data from the sync folder; any computer backs up to it. */}
          <p className="text-sm">
            {t("sync.text")}{" "}
            <Link to="/ayarlar" className={LINK}>
              {t("sync.link")}
            </Link>
          </p>
        </div>
      );
    case "names":
      return <NamesEditor settings={settings} />;
    case "business_names":
      return <BusinessNamesEditor settings={settings} />;
    case "mail":
      return <MailEditor settings={settings} />;
    case "senders":
      return (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <p className="text-sm font-medium">{t("banks", { count: settings.bank_senders.length })}</p>
            <ul aria-label={t("banksList")} className="flex flex-wrap gap-x-3 gap-y-1 text-sm">
              {settings.bank_senders.map((domain) => (
                <li key={domain}>
                  <code className="break-all">{domain}</code>
                </li>
              ))}
            </ul>
          </div>
          <OtherSendersCard />
        </div>
      );
    case "documents":
      return <UploadPanel />;
    case "notifications":
      return (
        <div className="grid items-start gap-4 xl:grid-cols-2">
          <TelegramCard />
          <ChannelsCard />
        </div>
      );
    case "service":
      return <Service registered={done} />;
    case "remote":
      return <p className="text-sm">{t("remote")}</p>;
    default:
      return null; // a step this version does not know: its note says where it stands
  }
}

/**
 * The service as it runs now: its version and since when. Whether it starts with the computer is the step's note; when
 * it does not, what that means and what registers it.
 */
function Service({ registered }: { registered: boolean }) {
  const { t } = useTranslation("setup");
  const service = useSystem().data?.service;
  return (
    <div className="flex flex-col gap-2 text-sm">
      {service ? (
        <p>{t("service.running", { version: service.version, since: formatTime(service.started_at) })}</p>
      ) : null}
      {registered ? null : <p>{t("service.notRegistered")}</p>}
    </div>
  );
}

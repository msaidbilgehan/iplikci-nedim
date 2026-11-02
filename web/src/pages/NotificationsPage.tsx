// The Notifications screen (F13, ADR-0010), one tab each (?bolum=…): the interface's notification box, the channels
// with the quiet hours and the Telegram bot, the alert rules with their editor, and the delivery history of every
// channel. The box and the history follow the event stream, and the box is asked again every minute. Each card says
// in the simple view what it holds in a sentence; the detailed view adds the events, their codes and every channel's
// state as the service gives them.

import { useTranslation } from "react-i18next";

import { useUnreadNotifications } from "../api/queries";
import { ChannelsCard } from "../components/notify/ChannelsCard";
import { DeliveryLog } from "../components/notify/DeliveryLog";
import { NotificationBox } from "../components/notify/NotificationBox";
import { RulesCard } from "../components/notify/RulesCard";
import { TelegramCard } from "../components/notify/TelegramCard";
import { PageHeader } from "../components/ui/PageHeader";
import { SectionCount, SectionTabs } from "../components/ui/SectionTabs";

export default function NotificationsPage() {
  const { t } = useTranslation("notifications");
  const unread = useUnreadNotifications();
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("page.title")} description={t("page.description")} />
      <SectionTabs
        label={t("page.sections")}
        sections={[
          {
            id: "kutu",
            label: t("page.box"),
            badge: <SectionCount count={unread} />,
            content: () => <NotificationBox />,
          },
          {
            id: "kanallar",
            label: t("page.channels"),
            content: () => (
              <div className="grid items-start gap-4 lg:grid-cols-2">
                <ChannelsCard />
                <TelegramCard />
              </div>
            ),
          },
          { id: "kurallar", label: t("page.rules"), content: () => <RulesCard /> },
          { id: "gecmis", label: t("page.log"), content: () => <DeliveryLog /> },
        ]}
      />
    </div>
  );
}

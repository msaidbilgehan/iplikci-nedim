// The Notifications screen (F13, ADR-0010): the interface's notification box, the channels with the quiet hours, the
// Telegram bot, the alert rules with their editor, and the delivery history of every channel. The box and the
// history follow the event stream, and the box is asked again every minute. Each card says in the simple view what it
// holds in a sentence; the detailed view adds the events, their codes and every channel's state as the service gives
// them.

import { useTranslation } from "react-i18next";

import { ChannelsCard } from "../components/notify/ChannelsCard";
import { DeliveryLog } from "../components/notify/DeliveryLog";
import { NotificationBox } from "../components/notify/NotificationBox";
import { RulesCard } from "../components/notify/RulesCard";
import { TelegramCard } from "../components/notify/TelegramCard";
import { PageHeader } from "../components/ui/PageHeader";

export default function NotificationsPage() {
  const { t } = useTranslation("notifications");
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={t("page.title")} description={t("page.description")} />
      <NotificationBox />
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <ChannelsCard />
        <TelegramCard />
      </div>
      <RulesCard />
      <DeliveryLog />
    </div>
  );
}

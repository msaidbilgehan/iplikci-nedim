// The Notifications screen (F13, ADR-0010): the interface's notification box, the channels with the quiet hours, the
// Telegram bot, the alert rules with their editor, and the delivery history of every channel. The box and the
// history follow the event stream, and the box is asked again every minute.

import { ChannelsCard } from "../components/notify/ChannelsCard";
import { DeliveryLog } from "../components/notify/DeliveryLog";
import { NotificationBox } from "../components/notify/NotificationBox";
import { RulesCard } from "../components/notify/RulesCard";
import { TelegramCard } from "../components/notify/TelegramCard";

export default function NotificationsPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Bildirimler</h1>
      <p className="max-w-3xl text-sm text-zinc-700 dark:text-zinc-300">
        Kurallara uyan her olay buradaki bildirim kutusuna düşer; açtığınız kanallara da gönderilir. Aynı olay için her
        kanala tek bildirim gider.
      </p>
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

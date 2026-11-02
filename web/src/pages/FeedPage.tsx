// The Akış screen (F05): every event of the log as it comes, newest first, narrowed by account, kind and certainty;
// then, one click away, what stands now (each account's balance as far as the documents tell, each card's period, the
// month's pace against the typical month) and what the next 14 days hold. The event stream refreshes it all live
// (useEventStream).

import { useTranslation } from "react-i18next";

import { useAccounts, useLabels, useNow } from "../api/queries";
import { UpcomingCard } from "../components/feed/Upcoming";
import { EventsSection } from "../components/feed/Events";
import { NowSection } from "../components/feed/Now";
import { accountOptions } from "../components/filters";
import { PageHeader } from "../components/ui/PageHeader";
import { SectionCount, SectionTabs } from "../components/ui/SectionTabs";

export default function FeedPage() {
  const { t } = useTranslation("feed");
  const now = useNow();
  const labels = useLabels().data ?? {};
  const accounts = useAccounts();
  const days = now.data?.upcoming.length ?? 0;
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("title")} description={t("description")} />
      <SectionTabs
        label={t("sections")}
        sections={[
          {
            id: "olaylar",
            label: t("events.title"),
            content: () => (
              <EventsSection labels={labels} accounts={accountOptions(accounts.data, labels, t("events.closed"))} />
            ),
          },
          { id: "su-an", label: t("now.title"), content: () => <NowSection now={now} labels={labels} /> },
          {
            id: "yaklasanlar",
            label: t("upcoming.title"),
            badge: <SectionCount count={days} />,
            content: () => <UpcomingCard now={now} labels={labels} />,
          },
        ]}
      />
    </div>
  );
}

// The Akış screen (F05): what stands now (each account's balance as far as the documents tell, each card's period, the
// month's pace against the typical month), what the next 14 days hold, and every event of the log as it comes, newest
// first, narrowed by account, kind and certainty. The event stream refreshes it all live (useEventStream).

import { useTranslation } from "react-i18next";

import { useAccounts, useLabels, useNow } from "../api/queries";
import { UpcomingCard } from "../components/feed/Due";
import { EventsSection } from "../components/feed/Events";
import { NowSection } from "../components/feed/Now";
import { accountOptions } from "../components/filters";
import { PageHeader } from "../components/ui/PageHeader";

export default function FeedPage() {
  const { t } = useTranslation("feed");
  const now = useNow();
  const labels = useLabels().data ?? {};
  const accounts = useAccounts();
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("title")} description={t("description")} />
      <NowSection now={now} labels={labels} />
      <UpcomingCard now={now} labels={labels} />
      <EventsSection labels={labels} accounts={accountOptions(accounts.data, labels, t("events.closed"))} />
    </div>
  );
}

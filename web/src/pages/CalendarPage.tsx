// The Calendar screen (F09): what is expected in the next 60 days, and each TL account's balance day by day for the
// same days. Both rest on the past payments and the documents' newest balances and are estimates, labelled so; the
// forecast says what it assumes, with its windows and numbers.

import { useTranslation } from "react-i18next";

import { useCalendar, useForecast, useLabels } from "../api/queries";
import { Agenda } from "../components/calendar/Agenda";
import { ForecastView } from "../components/calendar/ForecastView";
import { Failure, Loading } from "../components/QueryState";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";

export default function CalendarPage() {
  const { t } = useTranslation("calendar");
  const calendar = useCalendar();
  const forecast = useForecast();
  const labels = useLabels().data ?? {};
  const estimate = <Badge tone="neutral">{t("estimate")}</Badge>;
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("title")} description={t("description")} />
      <Card title={t("agenda.title")} action={estimate}>
        {calendar.isPending ? <Loading /> : null}
        {calendar.isError ? <Failure error={calendar.error} onRetry={() => void calendar.refetch()} /> : null}
        {calendar.data ? <Agenda calendar={calendar.data} labels={labels} /> : null}
      </Card>
      <Card title={t("forecast.title")} action={estimate}>
        {forecast.isPending ? <Loading /> : null}
        {forecast.isError ? <Failure error={forecast.error} onRetry={() => void forecast.refetch()} /> : null}
        {forecast.data ? <ForecastView forecast={forecast.data} /> : null}
      </Card>
    </div>
  );
}

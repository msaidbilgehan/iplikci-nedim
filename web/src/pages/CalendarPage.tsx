// The Calendar screen (F09): what is expected in the next 60 days, and each TL account's balance day by day for the
// same days. Both rest on the past payments and the documents' newest balances and are estimates, labelled so; the
// forecast says what it assumes, with its windows and numbers. A day in the address (?gun=) narrows the list to it: a
// forecast's day leads here, from this screen's chart or the Pano's, as do a notice's due day and a series' next
// payment. A day chosen on the chart below brings the list into view.

import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { useCalendar, useForecast, useLabels } from "../api/queries";
import { Agenda } from "../components/calendar/Agenda";
import { ForecastView } from "../components/calendar/ForecastView";
import { Failure, Loading } from "../components/QueryState";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";

const DAY = "gun";
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

export default function CalendarPage() {
  const { t } = useTranslation("calendar");
  const calendar = useCalendar();
  const forecast = useForecast();
  const labels = useLabels().data ?? {};
  const [params, setParams] = useSearchParams();
  const day = ISO_DAY.test(params.get(DAY) ?? "") ? (params.get(DAY) ?? "") : "";
  const agenda = useRef<HTMLDivElement>(null);
  const shown = useRef(day);
  useEffect(() => {
    // A day chosen on this screen, on the forecast under the list: the list it narrows comes into view.
    if (day && day !== shown.current) {
      agenda.current?.scrollIntoView?.({ block: "start" });
    }
    shown.current = day;
  }, [day]);
  const allDays = () =>
    setParams((was) => {
      const next = new URLSearchParams(was);
      next.delete(DAY);
      return next;
    });
  const estimate = <Badge tone="neutral">{t("estimate")}</Badge>;
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("title")} description={t("description")} />
      <div ref={agenda} className="scroll-mt-4">
        <Card title={t("agenda.title")} action={estimate}>
          {calendar.isPending ? <Loading /> : null}
          {calendar.isError ? <Failure error={calendar.error} onRetry={() => void calendar.refetch()} /> : null}
          {calendar.data ? <Agenda calendar={calendar.data} labels={labels} day={day} onAllDays={allDays} /> : null}
        </Card>
      </div>
      <Card title={t("forecast.title")} action={estimate}>
        {forecast.isPending ? <Loading /> : null}
        {forecast.isError ? <Failure error={forecast.error} onRetry={() => void forecast.refetch()} /> : null}
        {forecast.data ? <ForecastView forecast={forecast.data} /> : null}
      </Card>
    </div>
  );
}

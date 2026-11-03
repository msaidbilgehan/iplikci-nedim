// Where the exchange rates stand, on the System screen (F12, architecture §15): the providers the settings name, each
// source's newest bulletin and the days kept, the business days of the history still missing, the last fetch and its
// error, and the steps that ask the service to fetch now — the day's bulletin with the days missed since the newest,
// or every missing day of the history. Without a provider nothing is fetched and the documents' rates are used.

import { useTranslation } from "react-i18next";

import { useFetchRates } from "../../api/queries";
import type { Labels, RatesState, RateSource } from "../../api/types";
import { formatDay, formatTime } from "../../lib/format";
import { labelOf } from "../../lib/labels";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Card, Facts } from "../ui/Card";

const SMALL = "text-sm text-zinc-600 dark:text-zinc-300";

export function RatesStatusCard({ rates, labels }: { rates: RatesState; labels: Labels }) {
  const { t } = useTranslation("system");
  const fetch = useFetchRates();
  const offline = rates.providers.length === 0;
  const name = (source: RateSource) => labelOf(labels, "RateSource", source);
  const facts: Array<[string, string]> = [
    [t("rates.providers"), offline ? t("rates.noProvider") : rates.providers.map(name).join(", ")],
    ...rates.sources.map((s): [string, string] => [
      t("rates.newest", { source: name(s.source) }),
      t("rates.newestValue", { day: formatDay(s.newest), count: s.days }),
    ]),
    [
      t("rates.kept"),
      rates.start ? t("rates.keptValue", { count: rates.days, start: formatDay(rates.start) }) : t("rates.keptNone"),
    ],
  ];
  if (!offline) {
    facts.push(
      [t("rates.missing"), rates.missing ? t("rates.missingValue", { count: rates.missing }) : t("rates.complete")],
      [t("rates.lastRun"), rates.last_run ? formatTime(rates.last_run) : t("rates.never")],
    );
  }
  return (
    <Card
      title={t("rates.title")}
      action={
        offline ? null : (
          <Button variant="secondary" onClick={() => fetch.mutate(false)} disabled={fetch.isPending}>
            {fetch.isPending ? t("rates.asking") : t("rates.now")}
          </Button>
        )
      }
    >
      <div className="flex flex-col gap-3">
        <Facts items={facts} />
        {offline ? <p className={SMALL}>{t("rates.offline")}</p> : null}
        {!offline && rates.missing > 0 ? (
          <div className="flex flex-col items-start gap-1">
            <Button variant="secondary" onClick={() => fetch.mutate(true)} disabled={fetch.isPending}>
              {t("rates.history")}
            </Button>
            <p className={SMALL}>{t("rates.historyText")}</p>
          </div>
        ) : null}
        {rates.last_error ? (
          <Alert tone="warning" title={t("rates.errorTitle")}>
            <p>{rates.last_error}</p>
            <p>{t("rates.errorText")}</p>
          </Alert>
        ) : null}
        {fetch.isSuccess ? (
          <Alert tone="good" title={t("rates.askedTitle")} live>
            <p>{t("rates.askedText")}</p>
          </Alert>
        ) : null}
        {fetch.isError ? (
          <Alert tone="critical" title={t("rates.failed")} live>
            <p>{fetch.error.message}</p>
          </Alert>
        ) : null}
      </div>
    </Card>
  );
}

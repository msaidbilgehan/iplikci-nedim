// The Subscriptions screen (F08): the monthly and periodic payments with their status, what to expect next and the
// rows behind them, the regular income and the card purchases with installments left. Every number comes from
// /api/subscriptions; the names of the statuses and periods come from /api/labels.

import { useLabels, useSubscriptions } from "../api/queries";
import type { Installment, Labels, Series, Subscriptions } from "../api/types";
import { Empty, Failure, Loading } from "../components/QueryState";
import { Badge, type Tone } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { Table, Td, Th } from "../components/ui/Table";
import { formatDay, formatMoney, formatMonth } from "../lib/format";

const STATUS_TONES: Record<Series["status"], Tone> = {
  active: "good",
  ended: "neutral",
  cancelled: "neutral",
  paid_after_cancel: "warning",
};

const RUNNING: ReadonlySet<Series["status"]> = new Set(["active", "paid_after_cancel"]);
const MUTED = "block text-xs text-zinc-600 dark:text-zinc-300";

export default function SubscriptionsPage() {
  const subscriptions = useSubscriptions();
  const labels = useLabels();
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Abonelikler</h1>
      {subscriptions.isPending ? <Loading /> : null}
      {subscriptions.isError ? (
        <Failure error={subscriptions.error} onRetry={() => void subscriptions.refetch()} />
      ) : null}
      {subscriptions.data ? <SubscriptionCards found={subscriptions.data} labels={labels.data ?? {}} /> : null}
    </div>
  );
}

function SubscriptionCards({ found, labels }: { found: Subscriptions; labels: Labels }) {
  const listed = found.series.filter((s) => s.listed);
  const monthly = listed.filter((s) => s.period === "month" && RUNNING.has(s.status));
  const periodic = listed.filter((s) => s.period !== "month" && RUNNING.has(s.status));
  const ended = listed.filter((s) => !RUNNING.has(s.status));
  const income = found.income.filter((s) => s.listed);
  if (listed.length === 0 && income.length === 0 && found.installments.length === 0) {
    return (
      <Empty title="Henüz düzenli ödeme bulunmadı">
        En az üç ay süren aylık ödemeler ile altı ayda ya da yılda bir yapılan ödemeler belgeler geldikçe burada görünür.
      </Empty>
    );
  }
  const first = found.window[0];
  const last = found.window[found.window.length - 1];
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-zinc-600 dark:text-zinc-300">
        Durumlar {formatDay(found.as_of)} tarihli son ekstreye göre
        {first && last
          ? `; pencere ${formatMonth(first)} – ${formatMonth(last)} arasındaki ${found.window.length} tam ay`
          : ""}
        .
      </p>
      {monthly.length > 0 ? (
        <Card title="Aylık ödemeler">
          <SeriesTable series={monthly} labels={labels} asOf={found.as_of} caption="Süren aylık ödemeler" />
        </Card>
      ) : null}
      {periodic.length > 0 ? (
        <Card title="Dönemsel ödemeler">
          <SeriesTable
            series={periodic}
            labels={labels}
            asOf={found.as_of}
            caption="Altı ayda ya da yılda bir yapılan ödemeler"
            periodic
          />
        </Card>
      ) : null}
      {ended.length > 0 ? (
        <Card title="Biten ve iptal edilenler">
          <EndedTable series={ended} labels={labels} />
        </Card>
      ) : null}
      {income.length > 0 ? (
        <Card title="Düzenli gelirler">
          <IncomeTable series={income} />
        </Card>
      ) : null}
      {found.installments.length > 0 ? (
        <Card title="Taksitli alışverişler">
          <InstallmentTable installments={found.installments} />
        </Card>
      ) : null}
    </div>
  );
}

interface SeriesTableProps {
  series: Series[];
  labels: Labels;
  asOf: string;
  caption: string;
  periodic?: boolean;
}

function SeriesTable({ series, labels, asOf, caption, periodic = false }: SeriesTableProps) {
  const periods = labels["SeriesPeriod"] ?? {};
  return (
    <Table>
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr>
          <Th>Ödeme</Th>
          <Th>Durum</Th>
          {periodic ? <Th>Sıklık</Th> : null}
          <Th className="text-right">{periodic ? "Dönem başına" : "Aylık tutar"}</Th>
          <Th>Son ödeme</Th>
          <Th>Sonraki ödeme</Th>
          <Th>Fiyat değişimi</Th>
          <Th>Belgeler</Th>
        </tr>
      </thead>
      <tbody>
        {series.map((s) => (
          <tr key={s.id}>
            <Td>
              <span className="font-medium">{s.payee}</span>
              <span className={MUTED}>{s.category}</span>
              <span className={MUTED}>{s.account.label}</span>
            </Td>
            <Td>
              <StatusBadge series={s} labels={labels} />
            </Td>
            {periodic ? <Td>{periods[s.period] ?? s.period}</Td> : null}
            <Td className="text-right tabular-nums">{formatMoney(s.amount)}</Td>
            <Td>
              {formatDay(s.last_day)}
              <span className={MUTED}>{formatMoney(s.last_amount)}</span>
            </Td>
            <Td>
              {s.next_day ? formatDay(s.next_day) : "—"}
              {s.next_day && s.next_day <= asOf ? <span className={MUTED}>belgelerde henüz görünmüyor</span> : null}
            </Td>
            <Td>
              {s.price_change ? (
                <>
                  {formatMoney(s.price_change.before)} → {formatMoney(s.price_change.after)}
                  <span className={MUTED}>{formatMonth(s.price_change.since.slice(0, 7))}</span>
                </>
              ) : (
                "—"
              )}
            </Td>
            <Td>
              <Payments series={s} labels={labels} />
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function StatusBadge({ series, labels }: { series: Series; labels: Labels }) {
  const statuses = labels["SeriesStatus"] ?? {};
  return (
    <>
      <Badge tone={STATUS_TONES[series.status]}>{statuses[series.status] ?? series.status}</Badge>
      {series.note ? <span className={`mt-1 ${MUTED}`}>{series.note}</span> : null}
    </>
  );
}

/** The rows a series rests on, each with the document it is printed in. */
function Payments({ series, labels }: { series: Series; labels: Labels }) {
  const certainty = labels["Certainty"] ?? {};
  return (
    <details>
      <summary className="cursor-pointer rounded focus-visible:outline-2 focus-visible:outline-teal-600">
        {series.payments.length} ödeme
      </summary>
      <ul className="mt-1 flex flex-col gap-1 text-xs">
        {series.payments.map((p) => (
          <li key={p.fingerprint || `${p.day}-${p.document}`}>
            {formatDay(p.day)} · {formatMoney(p.amount)} · {p.document || "belge adı yok"}
            {p.certainty === "provisional" ? (
              <span className="ml-1">
                <Badge tone="warning">{certainty[p.certainty] ?? p.certainty}</Badge>
              </span>
            ) : null}
          </li>
        ))}
      </ul>
    </details>
  );
}

function EndedTable({ series, labels }: { series: Series[]; labels: Labels }) {
  const periods = labels["SeriesPeriod"] ?? {};
  return (
    <Table>
      <caption className="sr-only">Pencere içinde biten ya da iptal edilen ödemeler</caption>
      <thead>
        <tr>
          <Th>Ödeme</Th>
          <Th>Durum</Th>
          <Th>Sıklık</Th>
          <Th>Son ödeme</Th>
        </tr>
      </thead>
      <tbody>
        {series.map((s) => (
          <tr key={s.id}>
            <Td>
              <span className="font-medium">{s.payee}</span>
              <span className={MUTED}>{s.category}</span>
            </Td>
            <Td>
              <StatusBadge series={s} labels={labels} />
            </Td>
            <Td>{periods[s.period] ?? s.period}</Td>
            <Td>
              {formatDay(s.last_day)}
              <span className={MUTED}>{formatMoney(s.last_amount)}</span>
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function IncomeTable({ series }: { series: Series[] }) {
  return (
    <Table>
      <caption className="sr-only">Düzenli gelirler</caption>
      <thead>
        <tr>
          <Th>Ödeyen</Th>
          <Th className="text-right">Beklenen tutar</Th>
          <Th>Son gelen</Th>
          <Th>Sonraki</Th>
        </tr>
      </thead>
      <tbody>
        {series.map((s) => (
          <tr key={s.id}>
            <Td>
              <span className="font-medium">{s.payee}</span>
              <span className={MUTED}>{s.account.label}</span>
            </Td>
            <Td className="text-right tabular-nums">
              {formatMoney(s.amount)}
              <span className={MUTED}>son üç tutarın medyanı</span>
            </Td>
            <Td>
              {formatDay(s.last_day)}
              <span className={MUTED}>{formatMoney(s.last_amount)}</span>
            </Td>
            <Td>{s.next_day ? formatDay(s.next_day) : "—"}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function InstallmentTable({ installments }: { installments: Installment[] }) {
  return (
    <Table>
      <caption className="sr-only">Kalan taksitleri olan kart alışverişleri</caption>
      <thead>
        <tr>
          <Th>Alışveriş</Th>
          <Th>Taksit</Th>
          <Th className="text-right">Taksit tutarı</Th>
          <Th className="text-right">Kalan</Th>
          <Th>Bitiş</Th>
        </tr>
      </thead>
      <tbody>
        {installments.map((i) => (
          <tr key={i.fingerprint || `${i.card.id}-${i.title}-${i.number}`}>
            <Td>
              <span className="font-medium">{i.title}</span>
              <span className={MUTED}>{i.card.label}</span>
            </Td>
            <Td>
              {i.number}/{i.count}
            </Td>
            <Td className="text-right tabular-nums">{formatMoney(i.amount)}</Td>
            <Td className="text-right tabular-nums">
              {formatMoney(i.remaining)}
              <span className={MUTED}>{i.left} taksit</span>
            </Td>
            <Td>{formatMonth(i.last_day.slice(0, 7))}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

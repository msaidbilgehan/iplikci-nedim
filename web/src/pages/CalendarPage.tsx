// The Calendar screen (F09): what is expected in the next 60 days, and each bank account's balance day by day for the
// same days. Both rest on the past payments and are estimates, labelled so; the forecast says what it assumes, with
// its windows and numbers. A chart can come with the charts' shared rules (features.md); until then, tables.

import { useCalendar, useForecast, useLabels } from "../api/queries";
import type { AccountForecast, Calendar, CalendarItem, Forecast, Money } from "../api/types";
import { Empty, Failure, Loading } from "../components/QueryState";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { Table, Td, Th } from "../components/ui/Table";
import { formatDay, formatFlow, formatMoney } from "../lib/format";

const MUTED = "block text-xs text-zinc-600 dark:text-zinc-300";
const ESTIMATE = <Badge tone="neutral">Tahmin</Badge>;

export default function CalendarPage() {
  const calendar = useCalendar();
  const forecast = useForecast();
  const labels = useLabels();
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Takvim</h1>
      <Card title="Önümüzdeki 60 gün" action={ESTIMATE}>
        {calendar.isPending ? <Loading /> : null}
        {calendar.isError ? <Failure error={calendar.error} onRetry={() => void calendar.refetch()} /> : null}
        {calendar.data ? <Agenda calendar={calendar.data} kinds={labels.data?.["PaymentKind"] ?? {}} /> : null}
      </Card>
      <Card title="Nakit akışı öngörüsü" action={ESTIMATE}>
        {forecast.isPending ? <Loading /> : null}
        {forecast.isError ? <Failure error={forecast.error} onRetry={() => void forecast.refetch()} /> : null}
        {forecast.data ? <ForecastView forecast={forecast.data} /> : null}
      </Card>
    </div>
  );
}

function total(items: CalendarItem[], direction: CalendarItem["direction"]): Money {
  const minor = items.filter((i) => i.direction === direction).reduce((sum, i) => sum + i.amount.minor, 0);
  return { minor, currency: "TRY" };
}

function Agenda({ calendar, kinds }: { calendar: Calendar; kinds: Record<string, string> }) {
  const span = `${formatDay(calendar.today)} – ${formatDay(calendar.end)}`;
  if (calendar.items.length === 0) {
    return (
      <Empty title="Bu günlerde beklenen ödeme ya da gelir yok">
        {span}. Düzenli ödemeler ve maaş belgeler geldikçe buraya düşer.
      </Empty>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-zinc-600 dark:text-zinc-300">
        {span}: geçmiş ödemelerden beklenen günler ve tutarlar.
      </p>
      <Table>
        <caption className="sr-only">Önümüzdeki 60 günde beklenen ödemeler ve gelirler, güne göre</caption>
        <thead>
          <tr>
            <Th>Gün</Th>
            <Th>Tür</Th>
            <Th>Ne</Th>
            <Th>Hesap</Th>
            <Th className="text-right">Tutar</Th>
          </tr>
        </thead>
        <tbody>
          {calendar.items.map((item, index) => (
            <tr key={`${item.day}-${item.kind}-${item.title}-${index}`}>
              <Td className="whitespace-nowrap">{formatDay(item.day)}</Td>
              <Td>{kinds[item.kind] ?? item.kind}</Td>
              <Td>
                <span className="font-medium">{item.title}</span>
                <span className={MUTED}>{item.basis}</span>
              </Td>
              <Td>{item.account.label}</Td>
              <Td className="whitespace-nowrap text-right tabular-nums">
                {formatFlow(item.amount, item.direction)}
                {item.minimum ? <span className={MUTED}>asgari {formatMoney(item.minimum)}</span> : null}
              </Td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <Td colSpan={4} className="font-medium">
              Toplam
            </Td>
            <Td className="text-right tabular-nums">
              <span className="block">giriş {formatFlow(total(calendar.items, "in"), "in")}</span>
              <span className="block">çıkış {formatFlow(total(calendar.items, "out"), "out")}</span>
            </Td>
          </tr>
        </tfoot>
      </Table>
    </div>
  );
}

function ForecastView({ forecast }: { forecast: Forecast }) {
  const skipped = forecast.skipped;
  return (
    <div className="flex flex-col gap-3">
      {forecast.accounts.length === 0 ? (
        <Empty title="Öngörü için bakiyesi bilinen TL hesabı yok">
          Hesap dökümü ya da bakiyesini yazan bir banka bildirimi gelince öngörü burada görünür.
        </Empty>
      ) : (
        <>
          <p className="text-sm text-zinc-600 dark:text-zinc-300">
            {formatDay(forecast.today)} – {formatDay(forecast.end)}, her günün sonundaki bakiye.
          </p>
          <SummaryTable accounts={forecast.accounts} />
          {forecast.accounts.map((account) => (
            <section key={account.account.id} aria-label={`${account.account.label} varsayımları`}>
              <h3 className="text-sm font-semibold">{account.account.label}: varsayımlar</h3>
              <ul className="ml-4 list-disc text-sm text-zinc-700 dark:text-zinc-300">
                {account.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </section>
          ))}
          <DailyTable accounts={forecast.accounts} />
        </>
      )}
      {forecast.notes.length > 0 ? (
        <ul className="ml-4 list-disc text-sm text-zinc-700 dark:text-zinc-300">
          {forecast.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}
      {forecast.elsewhere.length > 0 ? (
        <div className="text-sm">
          <p className="font-medium">Hesaplara düşülmeyen kalemler</p>
          <ul className="ml-4 list-disc text-zinc-700 dark:text-zinc-300">
            {forecast.elsewhere.map((item, index) => (
              <li key={`${item.day}-${item.title}-${index}`}>
                {formatDay(item.day)} {item.title} ({item.account.label}): {formatFlow(item.amount, item.direction)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {skipped.length > 0 ? (
        <div className="text-sm">
          <p className="font-medium">Öngörüye girmeyen hesaplar</p>
          <ul className="ml-4 list-disc text-zinc-700 dark:text-zinc-300">
            {skipped.map((s) => (
              <li key={s.account.id}>
                {s.account.label}: {s.reason}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function SummaryTable({ accounts }: { accounts: AccountForecast[] }) {
  return (
    <Table>
      <caption className="sr-only">Hesap başına bakiye öngörüsü</caption>
      <thead>
        <tr>
          <Th>Hesap</Th>
          <Th className="text-right">Başlangıç</Th>
          <Th className="text-right">60 gün sonra</Th>
          <Th className="text-right">En düşük</Th>
          <Th>Eksi bakiye</Th>
        </tr>
      </thead>
      <tbody>
        {accounts.map((a) => (
          <tr key={a.account.id}>
            <Td className="font-medium">{a.account.label}</Td>
            <Td className="text-right tabular-nums">
              {formatMoney(a.start.balance)}
              <span className={MUTED}>
                {formatDay(a.start.day)} {a.start.source === "notice" ? "bildirimi" : "dökümü"}
                {a.start.moves > 0 ? ` ve ${a.start.moves} hareket` : ""}
              </span>
            </Td>
            <Td className="text-right tabular-nums">{formatMoney(a.end_balance)}</Td>
            <Td className="text-right tabular-nums">
              {formatMoney(a.lowest.balance)}
              <span className={MUTED}>{formatDay(a.lowest.day)}</span>
            </Td>
            <Td>
              {a.negative ? (
                <Badge tone="critical">
                  {formatDay(a.negative.day)}: {formatMoney(a.negative.balance)}
                </Badge>
              ) : (
                <Badge tone="good">Eksiye düşmüyor</Badge>
              )}
              {a.interest ? <span className={MUTED}>KMH faizi ~{formatMoney(a.interest)}</span> : null}
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

/** Every day's closing balance, an account a column: the forecast's table view. */
function DailyTable({ accounts }: { accounts: AccountForecast[] }) {
  const days = accounts[0]?.days.map((point) => point.day) ?? [];
  return (
    <details>
      <summary className="cursor-pointer rounded text-sm font-medium focus-visible:outline-2 focus-visible:outline-teal-600">
        Gün gün bakiyeler
      </summary>
      <Table className="mt-2">
        <caption className="sr-only">Her günün sonundaki tahmini bakiye, hesap başına</caption>
        <thead>
          <tr>
            <Th>Gün</Th>
            {accounts.map((a) => (
              <Th key={a.account.id} className="text-right">
                {a.account.label}
              </Th>
            ))}
          </tr>
        </thead>
        <tbody>
          {days.map((day, index) => (
            <tr key={day}>
              <Td className="whitespace-nowrap">{formatDay(day)}</Td>
              {accounts.map((a) => {
                const point = a.days[index];
                return (
                  <Td key={a.account.id} className="text-right tabular-nums">
                    {point ? formatMoney(point.balance) : "—"}
                  </Td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </Table>
    </details>
  );
}

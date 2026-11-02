// The System screen (F18): the service and its log, the e-mail intake and its non-bank senders, the queue, the
// backups, the exports, the disk and how each reader is doing. Every number comes from /api/system; the event stream
// keeps it current.

import { type FormEvent, useId, useState } from "react";

import {
  useBackupNow,
  useBridges,
  useExports,
  useExportsAgain,
  useLabels,
  useOtherSenders,
  useSetOtherSenders,
  useSystem,
} from "../api/queries";
import type { Bridge, ExportKind, Labels, MailCoverage, RefusedMail, SystemStatus } from "../api/types";
import { HistoryDue } from "../components/HistoryDue";
import { Failure, Loading } from "../components/QueryState";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, Facts } from "../components/ui/Card";
import { Table, Td, Th } from "../components/ui/Table";
import { cn } from "../lib/cn";
import { formatDay, formatSize, formatTime } from "../lib/format";

const LINK_BUTTON = cn(
  "inline-flex min-h-11 items-center rounded-md border px-3 text-sm font-medium",
  "border-zinc-300 bg-white text-zinc-900 hover:bg-zinc-50",
  "dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700",
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600",
);
const SMALL = "text-sm text-zinc-600 dark:text-zinc-300";
const EXPORT_NAMES: Record<ExportKind, string> = {
  report: "Rapor (tek dosya, HTML)",
  csv: "İşlemler (CSV)",
  xlsx: "İşlemler (Excel)",
  month_end: "Ay sonu sayfaları (zip)",
};

export default function SystemPage() {
  const system = useSystem();
  const labels = useLabels();
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Sistem</h1>
      {system.isPending ? <Loading /> : null}
      {system.isError ? <Failure error={system.error} onRetry={() => void system.refetch()} /> : null}
      {system.data ? <SystemCards status={system.data} labels={labels.data ?? {}} /> : null}
    </div>
  );
}

function SystemCards({ status, labels }: { status: SystemStatus; labels: Labels }) {
  const documentLabels = labels["DocumentStatus"] ?? {};
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card
        title="Servis"
        action={
          <a href="/api/system/log" download className={LINK_BUTTON}>
            Günlüğü indir
          </a>
        }
      >
        <div className="flex flex-col gap-3">
          <Facts
            items={[
              ["Sürüm", status.service.version],
              ["Başlangıç", formatTime(status.service.started_at)],
              ["Süreç", String(status.service.pid)],
              ["Veri klasörü", <code key="home">{status.service.home}</code>],
            ]}
          />
          <p className={SMALL}>
            Bir sorun olduğunda günlüğü gönderebilirsiniz: kişisel olabilecek yollar, adlar, adresler, IBAN&apos;lar
            ve uzun numaralar indirilen dosyadan çıkarılır.
          </p>
        </div>
      </Card>
      <MailCard status={status} />
      <OtherSendersCard />
      <QueueCard status={status} jobKinds={labels["JobKind"] ?? {}} />
      <BackupCard status={status} />
      <ExportsCard />
      <Card title="Belgeler">
        <Facts
          items={Object.entries(status.documents)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([code, count]) => [documentLabels[code] ?? code, String(count)])}
        />
      </Card>
      <Card title="Disk">
        <Facts
          items={[
            ["Belge asılları", formatSize(status.disk.vault)],
            ["Veritabanı", formatSize(status.disk.database)],
            ["Diskte boş", formatSize(status.disk.free)],
          ]}
        />
      </Card>
      <ReadersCard status={status} />
    </div>
  );
}

function MailCard({ status }: { status: SystemStatus }) {
  const mail = status.mail;
  const bridges = useBridges();
  const byExtension = mail.connector === "browser_bridge";
  return (
    <Card title="E-posta">
      <div className="flex flex-col gap-3">
        <Facts
          items={[
            ["Bağlantı", byExtension ? "Tarayıcı eklentisi" : "IMAP"],
            ["Durum", mailBadge(status)],
            ["Son alım", mail.last_run ? formatTime(mail.last_run) : "Henüz yok"],
            ["Başlangıç günü", formatDay(mail.start_day)],
          ]}
        />
        {mail.coverage.total > 0 ? <MailCoverageFacts coverage={mail.coverage} /> : null}
        {mail.history_due ? <HistoryDue startDay={mail.start_day} /> : null}
        {mail.refused.length > 0 ? <RefusedList refused={mail.refused} /> : null}
        {mail.stopped ? (
          <Alert tone="critical" title="Giriş reddedildi; e-posta alımı durdu">
            <p>Hesabın kilitlenmemesi için yeniden denenmez. E-posta bağlantısını yeniden kurun.</p>
          </Alert>
        ) : null}
        {mail.last_error && !mail.stopped ? (
          <Alert tone="warning" title="Son alımda sorun oldu">
            <p>{mail.last_error}</p>
          </Alert>
        ) : null}
        {byExtension && bridges.data ? <BridgeSeen bridges={bridges.data} /> : null}
      </div>
    </Card>
  );
}

function mailBadge({ mail }: SystemStatus) {
  if (mail.stopped) {
    return <Badge tone="critical">Durdu</Badge>;
  }
  if (!mail.configured) {
    return <Badge tone="neutral">Kurulu değil</Badge>;
  }
  return mail.last_error ? <Badge tone="warning">Sorunlu</Badge> : <Badge tone="good">Çalışıyor</Badge>;
}

// F01: at least this share of the bank messages is read or knowingly classified as moving no money.
const COVERAGE_TARGET = 0.9;

/** How much of the bank mail was read or knowingly classified (F01), and the kinds of message nothing knows yet. */
function MailCoverageFacts({ coverage }: { coverage: MailCoverage }) {
  // Rounded down, so that a share just under the target never shows as the target itself.
  const percent = Math.floor(coverage.share * 100);
  const onTarget = coverage.share >= COVERAGE_TARGET;
  return (
    <div className="flex flex-col gap-1 text-sm">
      <p className="font-medium">
        E-posta kapsamı: %{percent}{" "}
        <Badge tone={onTarget ? "good" : "warning"}>{onTarget ? "Hedefte" : "Hedefin altında"}</Badge>
      </p>
      <ul className="list-disc pl-5 text-zinc-700 dark:text-zinc-300">
        <li>Banka iletisi: {coverage.total}</li>
        <li>Bildirimi okunan: {coverage.read}</li>
        <li>Ekindeki belgeleri okunan: {coverage.attached}</li>
        <li>Para hareketi taşımayan (kampanya, duyuru, güvenlik, kart): {coverage.no_money}</li>
        <li>Şirket belgesi: {coverage.business}</li>
        <li>Henüz tanınmayan: {coverage.unknown}</li>
      </ul>
      {coverage.left.length > 0 ? (
        <details>
          <summary className="cursor-pointer">Henüz tanınmayan iletiler</summary>
          <ul className="list-disc pl-5 text-zinc-700 dark:text-zinc-300">
            {coverage.left.map((kind) => (
              <li key={`${kind.domain}|${kind.template}`}>
                {kind.domain} · {kind.template || "konusuz"} ({kind.count})
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

/** The messages the extension delivered that were not kept, by why: the trust rule's findings, never their text. */
function RefusedList({ refused }: { refused: RefusedMail[] }) {
  const total = refused.reduce((sum, r) => sum + r.count, 0);
  return (
    <div className="flex flex-col gap-1 text-sm">
      <p className="font-medium">Alınmayan e-postalar: {total}</p>
      <ul className="list-disc pl-5 text-zinc-700 dark:text-zinc-300">
        {refused.map((r) => (
          <li key={`${r.taken}|${r.reason}|${r.domain}`}>
            {r.domain ? `${r.domain}: ` : ""}
            {r.label} ({r.count})
          </li>
        ))}
      </ul>
    </div>
  );
}

function BridgeSeen({ bridges }: { bridges: Bridge[] }) {
  const active = bridges.filter((b) => b.active);
  if (active.length === 0) {
    return <p className="text-sm text-zinc-600 dark:text-zinc-300">Eşleşmiş bir eklenti yok.</p>;
  }
  const name = (b: Bridge): string => b.name || "Tarayıcı eklentisi";
  // Two browsers of the same kind carry the same name: their pairing time tells them apart.
  const shared = (b: Bridge): boolean => active.filter((other) => name(other) === name(b)).length > 1;
  return (
    <ul className="text-sm">
      {active.map((b) => (
        <li key={b.id}>
          {name(b)}
          {shared(b) ? ` (eşleşme ${formatTime(b.created_at)})` : ""}: son görülme{" "}
          {b.last_seen ? formatTime(b.last_seen) : "henüz yok"}
        </li>
      ))}
    </ul>
  );
}

const FIELD = "min-h-11 rounded-md border border-zinc-300 bg-white px-3 dark:border-zinc-600 dark:bg-zinc-900";

/**
 * The non-bank senders (F14): the domains whose bills and receipts are taken in beside the banks' messages. The
 * service checks each domain and refuses a bank's; its message is shown as it says it.
 */
function OtherSendersCard() {
  const senders = useOtherSenders();
  const save = useSetOtherSenders();
  const [draft, setDraft] = useState("");
  const aboutId = useId();
  const errorId = useId();
  const domains = senders.data?.domains ?? [];
  // An added domain sends one more than the list holds: the error is then about what was typed.
  const addFailed = save.isError && (save.variables?.length ?? 0) > domains.length;

  function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const domain = draft.trim();
    if (domain) {
      save.mutate([...domains, domain], { onSuccess: () => setDraft("") });
    }
  }

  return (
    <Card title="Banka dışı göndericiler">
      <div className="flex flex-col gap-3">
        <p id={aboutId} className="text-sm text-zinc-700 dark:text-zinc-300">
          Fatura, abonelik ve alışveriş e-postalarının geldiği alan adları: gönderen adresinde @ işaretinden sonra
          gelen kısım. Yalnızca göndereni doğrulanan (DMARC denetiminden geçen) e-postalar alınır; bu adları taklit
          eden e-postalar alınmaz. Liste değişince tarayıcı eklentisi geçmiş e-postaları yeniden okur.
        </p>
        {senders.isPending ? <Loading /> : null}
        {senders.isError ? <Failure error={senders.error} onRetry={() => void senders.refetch()} /> : null}
        {senders.data && domains.length === 0 ? (
          <p className="text-sm text-zinc-600 dark:text-zinc-300">Henüz banka dışı gönderici yok.</p>
        ) : null}
        {domains.length > 0 ? (
          <ul aria-label="Banka dışı gönderici alan adları" className="flex flex-col gap-1">
            {domains.map((domain) => (
              <li key={domain} className="flex items-center justify-between gap-2 text-sm">
                <code className="break-all">{domain}</code>
                <Button
                  variant="secondary"
                  aria-label={`${domain} alan adını kaldır`}
                  disabled={save.isPending}
                  onClick={() => save.mutate(domains.filter((d) => d !== domain))}
                >
                  Kaldır
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
        {senders.data ? (
          <form onSubmit={add} className="flex flex-wrap items-end gap-2">
            <label className="flex flex-col gap-1 text-sm">
              <span>Alan adı</span>
              <input
                type="text"
                value={draft}
                onChange={(e) => {
                  setDraft(e.target.value);
                  if (save.isError) {
                    save.reset();
                  }
                }}
                placeholder="ör. ornekcell.example"
                autoComplete="off"
                spellCheck={false}
                inputMode="url"
                aria-describedby={addFailed ? `${aboutId} ${errorId}` : aboutId}
                aria-invalid={addFailed ? true : undefined}
                className={FIELD}
              />
            </label>
            <Button type="submit" disabled={save.isPending || draft.trim() === ""}>
              Ekle
            </Button>
          </form>
        ) : null}
        {save.isError ? (
          <div id={errorId}>
            <Alert tone="critical" title="Liste kaydedilemedi" live>
              <p>{save.error.message}</p>
            </Alert>
          </div>
        ) : null}
        {save.isSuccess ? <Alert tone="good" title="Liste kaydedildi" live /> : null}
      </div>
    </Card>
  );
}

function QueueCard({ status, jobKinds }: { status: SystemStatus; jobKinds: Record<string, string> }) {
  const { counts, failures, next_run: nextRun } = status.queue;
  return (
    <Card title="İş kuyruğu">
      <div className="flex flex-col gap-3">
        <Facts
          items={[
            ["Bekleyen", String(counts["queued"] ?? 0)],
            ["Çalışan", String(counts["running"] ?? 0)],
            ["Başarısız", String(counts["failed"] ?? 0)],
            ["Sıradaki", nextRun ? formatTime(nextRun) : "—"],
          ]}
        />
        {failures.length > 0 ? (
          <ul className="flex flex-col gap-1 text-sm">
            {failures.map((job) => (
              <li key={job.id}>
                <Badge tone="critical">{jobKinds[job.kind] ?? job.kind}</Badge>{" "}
                <span className="text-zinc-600 dark:text-zinc-300">
                  {formatTime(job.finished_at)} · {job.attempts} deneme · {job.error}
                </span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </Card>
  );
}

function BackupCard({ status }: { status: SystemStatus }) {
  const backup = status.backup;
  const now = useBackupNow();
  const rehearsal =
    backup.rehearsal_ok === null ? (
      "Henüz yapılmadı"
    ) : (
      <span className="inline-flex flex-wrap items-center gap-2">
        {formatTime(backup.rehearsal)}
        {backup.rehearsal_ok ? <Badge tone="good">Geçti</Badge> : <Badge tone="critical">Sorun buldu</Badge>}
      </span>
    );
  return (
    <Card
      title="Yedek"
      action={
        <Button variant="secondary" onClick={() => now.mutate()} disabled={now.isPending}>
          {now.isPending ? "İsteniyor…" : "Şimdi yedek al"}
        </Button>
      }
    >
      <div className="flex flex-col gap-3">
        <Facts
          items={[
            ["Son yedek", backup.last ? formatTime(backup.last) : "Henüz yok"],
            ["Sıradaki", formatTime(backup.next)],
            ["Saklanan", `${backup.count} yedek, ${formatSize(backup.size)}`],
            ["Geri yükleme provası", rehearsal],
          ]}
        />
        {now.isSuccess ? (
          <Alert tone="good" title="Yedek isteği alındı" live>
            <p>Yedek birkaç saniye içinde alınır; bu sayfa kendiliğinden güncellenir.</p>
          </Alert>
        ) : null}
        {now.isError ? (
          <Alert tone="critical" title="Yedek istenemedi" live>
            <p>{now.error.message}</p>
          </Alert>
        ) : null}
      </div>
    </Card>
  );
}

function ExportsCard() {
  const exports = useExports();
  const again = useExportsAgain();
  return (
    <Card
      title="Dışa aktarımlar"
      action={
        <Button variant="secondary" onClick={() => again.mutate()} disabled={again.isPending}>
          {again.isPending ? "İsteniyor…" : "Yeniden yaz"}
        </Button>
      }
    >
      <div className="flex flex-col gap-3">
        {exports.isPending ? <Loading /> : null}
        {exports.isError ? <Failure error={exports.error} onRetry={() => void exports.refetch()} /> : null}
        {exports.data?.length === 0 ? (
          <p className={SMALL}>Henüz dışa aktarım yok; servis ilk analizini yapınca yazar.</p>
        ) : null}
        {exports.data?.length ? (
          <ul className="flex flex-col gap-3">
            {exports.data.map((item) => (
              <li key={item.kind} className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  <span className="block font-medium">{EXPORT_NAMES[item.kind]}</span>
                  <span className={SMALL}>
                    {formatTime(item.made_at)} · {formatSize(item.size)}
                  </span>
                </span>
                <a
                  href={`/api/exports/${item.kind}`}
                  download
                  className={LINK_BUTTON}
                  aria-label={`İndir: ${EXPORT_NAMES[item.kind]}`}
                >
                  İndir
                </a>
              </li>
            ))}
          </ul>
        ) : null}
        {again.isSuccess ? (
          <Alert tone="good" title="İstek alındı" live>
            <p>Analiz ve dışa aktarımlar birkaç saniye içinde yeniden yazılır; liste kendiliğinden güncellenir.</p>
          </Alert>
        ) : null}
        {again.isError ? (
          <Alert tone="critical" title="İstenemedi" live>
            <p>{again.error.message}</p>
          </Alert>
        ) : null}
      </div>
    </Card>
  );
}

function ReadersCard({ status }: { status: SystemStatus }) {
  const used = status.readers.filter((r) => r.documents > 0 || r.alarms > 0);
  return (
    <Card title="Okuyucular" className="md:col-span-2">
      {used.length === 0 ? (
        <p className="text-sm text-zinc-600 dark:text-zinc-300">
          Henüz okunan belge yok. {status.readers.length} okuyucu hazır.
        </p>
      ) : (
        <Table>
          <thead>
            <tr>
              <Th>Okuyucu</Th>
              <Th>Sürüm</Th>
              <Th>Belge</Th>
              <Th>Doğrulanan</Th>
              <Th>Son okuma</Th>
              <Th>Alarm</Th>
            </tr>
          </thead>
          <tbody>
            {used.map((r) => (
              <tr key={r.parser}>
                <Td>{r.name}</Td>
                <Td>{r.version}</Td>
                <Td>{r.documents}</Td>
                <Td>{r.statements ? `${r.verified}/${r.statements}` : "—"}</Td>
                <Td>{r.last_read ? formatTime(r.last_read) : "—"}</Td>
                <Td>{r.alarms ? <Badge tone="warning">{String(r.alarms)}</Badge> : "—"}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

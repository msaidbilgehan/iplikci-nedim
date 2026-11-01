// The System screen (F18): the service, the e-mail intake, the queue, the backups, the disk and how each reader is
// doing. Every number comes from /api/system; the event stream keeps it current.

import { useBackupNow, useBridges, useLabels, useSystem } from "../api/queries";
import type { Bridge, Labels, RefusedMail, SystemStatus } from "../api/types";
import { HistoryDue } from "../components/HistoryDue";
import { Failure, Loading } from "../components/QueryState";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, Facts } from "../components/ui/Card";
import { Table, Td, Th } from "../components/ui/Table";
import { formatDay, formatSize, formatTime } from "../lib/format";

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
      <Card title="Servis">
        <Facts
          items={[
            ["Sürüm", status.service.version],
            ["Başlangıç", formatTime(status.service.started_at)],
            ["Süreç", String(status.service.pid)],
            ["Veri klasörü", <code key="home">{status.service.home}</code>],
          ]}
        />
      </Card>
      <MailCard status={status} />
      <QueueCard status={status} jobKinds={labels["JobKind"] ?? {}} />
      <BackupCard status={status} />
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
  return (
    <ul className="text-sm">
      {active.map((b) => (
        <li key={b.id}>
          {b.name || "Tarayıcı eklentisi"}: son görülme {b.last_seen ? formatTime(b.last_seen) : "henüz yok"}
        </li>
      ))}
    </ul>
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

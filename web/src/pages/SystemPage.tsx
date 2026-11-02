// The System screen (F18): the service and its log, the e-mail intake and its non-bank senders, the queue, the
// backups, the exports, the disk and how each reader is doing. Every number comes from /api/system; the event stream
// keeps it current.

import { type FormEvent, useId, useState } from "react";
import { useTranslation } from "react-i18next";

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
import { PageHeader } from "../components/ui/PageHeader";
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

export default function SystemPage() {
  const { t } = useTranslation("system");
  const system = useSystem();
  const labels = useLabels();
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={t("title")} description={t("description")} />
      {system.isPending ? <Loading /> : null}
      {system.isError ? <Failure error={system.error} onRetry={() => void system.refetch()} /> : null}
      {system.data ? <SystemCards status={system.data} labels={labels.data ?? {}} /> : null}
    </div>
  );
}

function SystemCards({ status, labels }: { status: SystemStatus; labels: Labels }) {
  const { t } = useTranslation("system");
  const documentLabels = labels["DocumentStatus"] ?? {};
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card
        title={t("service.title")}
        action={
          <a href="/api/system/log" download className={LINK_BUTTON}>
            {t("service.log")}
          </a>
        }
      >
        <div className="flex flex-col gap-3">
          <Facts
            items={[
              [t("service.version"), status.service.version],
              [t("service.started"), formatTime(status.service.started_at)],
              [t("service.process"), String(status.service.pid)],
              [t("service.home"), <code key="home">{status.service.home}</code>],
            ]}
          />
          <p className={SMALL}>{t("service.logNote")}</p>
        </div>
      </Card>
      <MailCard status={status} />
      <OtherSendersCard />
      <QueueCard status={status} jobKinds={labels["JobKind"] ?? {}} />
      <BackupCard status={status} />
      <ExportsCard />
      <Card title={t("documents.title")}>
        <Facts
          items={Object.entries(status.documents)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([code, count]) => [documentLabels[code] ?? code, String(count)])}
        />
      </Card>
      <Card title={t("disk.title")}>
        <Facts
          items={[
            [t("disk.vault"), formatSize(status.disk.vault)],
            [t("disk.database"), formatSize(status.disk.database)],
            [t("disk.free"), formatSize(status.disk.free)],
          ]}
        />
      </Card>
      <ReadersCard status={status} />
    </div>
  );
}

function MailCard({ status }: { status: SystemStatus }) {
  const { t } = useTranslation("system");
  const mail = status.mail;
  const bridges = useBridges();
  const byExtension = mail.connector === "browser_bridge";
  return (
    <Card title={t("mail.title")}>
      <div className="flex flex-col gap-3">
        <Facts
          items={[
            [t("mail.connector"), byExtension ? t("mail.byExtension") : t("mail.imap")],
            [t("mail.state"), <MailBadge key="state" status={status} />],
            [t("mail.lastRun"), mail.last_run ? formatTime(mail.last_run) : t("mail.none")],
            [t("mail.startDay"), formatDay(mail.start_day)],
          ]}
        />
        {mail.coverage.total > 0 ? <MailCoverageFacts coverage={mail.coverage} /> : null}
        {mail.history_due ? <HistoryDue startDay={mail.start_day} /> : null}
        {mail.refused.length > 0 ? <RefusedList refused={mail.refused} /> : null}
        {mail.stopped ? (
          <Alert tone="critical" title={t("mail.stoppedTitle")}>
            <p>{t("mail.stoppedText")}</p>
          </Alert>
        ) : null}
        {mail.last_error && !mail.stopped ? (
          <Alert tone="warning" title={t("mail.errorTitle")}>
            <p>{mail.last_error}</p>
          </Alert>
        ) : null}
        {byExtension && bridges.data ? <BridgeSeen bridges={bridges.data} /> : null}
      </div>
    </Card>
  );
}

function MailBadge({ status: { mail } }: { status: SystemStatus }) {
  const { t } = useTranslation("system");
  if (mail.stopped) {
    return <Badge tone="critical">{t("mail.badge.stopped")}</Badge>;
  }
  if (!mail.configured) {
    return <Badge tone="neutral">{t("mail.badge.unconfigured")}</Badge>;
  }
  return mail.last_error ? (
    <Badge tone="warning">{t("mail.badge.troubled")}</Badge>
  ) : (
    <Badge tone="good">{t("mail.badge.working")}</Badge>
  );
}

// F01: at least this share of the bank messages is read or knowingly classified as moving no money.
const COVERAGE_TARGET = 0.9;

/** How much of the bank mail was read or knowingly classified (F01), and the kinds of message nothing knows yet. */
function MailCoverageFacts({ coverage }: { coverage: MailCoverage }) {
  const { t } = useTranslation("system");
  // Rounded down, so that a share just under the target never shows as the target itself.
  const percent = Math.floor(coverage.share * 100);
  const onTarget = coverage.share >= COVERAGE_TARGET;
  return (
    <div className="flex flex-col gap-1 text-sm">
      <p className="font-medium">
        {t("mail.coverage", { percent })}{" "}
        <Badge tone={onTarget ? "good" : "warning"}>{onTarget ? t("mail.onTarget") : t("mail.belowTarget")}</Badge>
      </p>
      <ul className="list-disc pl-5 text-zinc-700 dark:text-zinc-300">
        <li>{t("mail.total", { count: coverage.total })}</li>
        <li>{t("mail.read", { count: coverage.read })}</li>
        <li>{t("mail.attached", { count: coverage.attached })}</li>
        <li>{t("mail.noMoney", { count: coverage.no_money })}</li>
        <li>{t("mail.business", { count: coverage.business })}</li>
        <li>{t("mail.unknown", { count: coverage.unknown })}</li>
      </ul>
      {coverage.left.length > 0 ? (
        <details>
          <summary className="cursor-pointer">{t("mail.left")}</summary>
          <ul className="list-disc pl-5 text-zinc-700 dark:text-zinc-300">
            {coverage.left.map((kind) => (
              <li key={`${kind.domain}|${kind.template}`}>
                {kind.domain} · {kind.template || t("mail.noSubject")} ({kind.count})
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
  const { t } = useTranslation("system");
  const total = refused.reduce((sum, r) => sum + r.count, 0);
  return (
    <div className="flex flex-col gap-1 text-sm">
      <p className="font-medium">{t("mail.refused", { count: total })}</p>
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
  const { t } = useTranslation("system");
  const active = bridges.filter((b) => b.active);
  if (active.length === 0) {
    return <p className="text-sm text-zinc-600 dark:text-zinc-300">{t("mail.noBridge")}</p>;
  }
  const name = (b: Bridge): string => b.name || t("mail.bridgeName");
  // Two browsers of the same kind carry the same name: their pairing time tells them apart.
  const shared = (b: Bridge): boolean => active.filter((other) => name(other) === name(b)).length > 1;
  return (
    <ul className="text-sm">
      {active.map((b) => (
        <li key={b.id}>
          {name(b)}
          {shared(b) ? t("mail.pairedAt", { time: formatTime(b.created_at) }) : ""}
          {t("mail.seen")} {b.last_seen ? formatTime(b.last_seen) : t("mail.notSeen")}
        </li>
      ))}
    </ul>
  );
}

const FIELD = "min-h-11 rounded-md border border-zinc-300 bg-white px-3 dark:border-zinc-600 dark:bg-zinc-900";

/**
 * The non-bank senders (F14): the domains whose bills and receipts are taken in beside the banks' messages. The
 * service checks each domain and refuses a bank's; its message is shown as it says it. The setup wizard shows it too.
 */
export function OtherSendersCard() {
  const { t } = useTranslation("system");
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
    <Card title={t("senders.title")}>
      <div className="flex flex-col gap-3">
        <p id={aboutId} className="text-sm text-zinc-700 dark:text-zinc-300">
          {t("senders.about")}
        </p>
        {senders.isPending ? <Loading /> : null}
        {senders.isError ? <Failure error={senders.error} onRetry={() => void senders.refetch()} /> : null}
        {senders.data && domains.length === 0 ? (
          <p className="text-sm text-zinc-600 dark:text-zinc-300">{t("senders.empty")}</p>
        ) : null}
        {domains.length > 0 ? (
          <ul aria-label={t("senders.list")} className="flex flex-col gap-1">
            {domains.map((domain) => (
              <li key={domain} className="flex items-center justify-between gap-2 text-sm">
                <code className="break-all">{domain}</code>
                <Button
                  variant="secondary"
                  aria-label={t("senders.removeNamed", { domain })}
                  disabled={save.isPending}
                  onClick={() => save.mutate(domains.filter((d) => d !== domain))}
                >
                  {t("senders.remove")}
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
        {senders.data ? (
          <form onSubmit={add} className="flex flex-wrap items-end gap-2">
            <label className="flex flex-col gap-1 text-sm">
              <span>{t("senders.domain")}</span>
              <input
                type="text"
                value={draft}
                onChange={(e) => {
                  setDraft(e.target.value);
                  if (save.isError) {
                    save.reset();
                  }
                }}
                placeholder={t("senders.placeholder")}
                autoComplete="off"
                spellCheck={false}
                inputMode="url"
                aria-describedby={addFailed ? `${aboutId} ${errorId}` : aboutId}
                aria-invalid={addFailed ? true : undefined}
                className={FIELD}
              />
            </label>
            <Button type="submit" disabled={save.isPending || draft.trim() === ""}>
              {t("senders.add")}
            </Button>
          </form>
        ) : null}
        {save.isError ? (
          <div id={errorId}>
            <Alert tone="critical" title={t("senders.failed")} live>
              <p>{save.error.message}</p>
            </Alert>
          </div>
        ) : null}
        {save.isSuccess ? <Alert tone="good" title={t("senders.saved")} live /> : null}
      </div>
    </Card>
  );
}

function QueueCard({ status, jobKinds }: { status: SystemStatus; jobKinds: Record<string, string> }) {
  const { t } = useTranslation("system");
  const { counts, failures, next_run: nextRun } = status.queue;
  return (
    <Card title={t("queue.title")}>
      <div className="flex flex-col gap-3">
        <Facts
          items={[
            [t("queue.queued"), String(counts["queued"] ?? 0)],
            [t("queue.running"), String(counts["running"] ?? 0)],
            [t("queue.failed"), String(counts["failed"] ?? 0)],
            [t("queue.next"), nextRun ? formatTime(nextRun) : t("queue.none")],
          ]}
        />
        {failures.length > 0 ? (
          <ul className="flex flex-col gap-1 text-sm">
            {failures.map((job) => (
              <li key={job.id}>
                <Badge tone="critical">{jobKinds[job.kind] ?? job.kind}</Badge>{" "}
                <span className="text-zinc-600 dark:text-zinc-300">
                  {t("queue.failure", { time: formatTime(job.finished_at), attempts: job.attempts, error: job.error })}
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
  const { t } = useTranslation("system");
  const backup = status.backup;
  const now = useBackupNow();
  const rehearsal =
    backup.rehearsal_ok === null ? (
      t("backup.notYet")
    ) : (
      <span className="inline-flex flex-wrap items-center gap-2">
        {formatTime(backup.rehearsal)}
        {backup.rehearsal_ok ? (
          <Badge tone="good">{t("backup.passed")}</Badge>
        ) : (
          <Badge tone="critical">{t("backup.problem")}</Badge>
        )}
      </span>
    );
  return (
    <Card
      title={t("backup.title")}
      action={
        <Button variant="secondary" onClick={() => now.mutate()} disabled={now.isPending}>
          {now.isPending ? t("backup.asking") : t("backup.now")}
        </Button>
      }
    >
      <div className="flex flex-col gap-3">
        <Facts
          items={[
            [t("backup.last"), backup.last ? formatTime(backup.last) : t("backup.none")],
            [t("backup.next"), formatTime(backup.next)],
            [t("backup.kept"), t("backup.keptValue", { count: backup.count, size: formatSize(backup.size) })],
            [t("backup.rehearsal"), rehearsal],
          ]}
        />
        {now.isSuccess ? (
          <Alert tone="good" title={t("backup.askedTitle")} live>
            <p>{t("backup.askedText")}</p>
          </Alert>
        ) : null}
        {now.isError ? (
          <Alert tone="critical" title={t("backup.failed")} live>
            <p>{now.error.message}</p>
          </Alert>
        ) : null}
      </div>
    </Card>
  );
}

function ExportsCard() {
  const { t } = useTranslation("system");
  const exports = useExports();
  const again = useExportsAgain();
  const name = (kind: ExportKind): string => t(`exports.kind.${kind}`);
  return (
    <Card
      title={t("exports.title")}
      action={
        <Button variant="secondary" onClick={() => again.mutate()} disabled={again.isPending}>
          {again.isPending ? t("exports.asking") : t("exports.again")}
        </Button>
      }
    >
      <div className="flex flex-col gap-3">
        {exports.isPending ? <Loading /> : null}
        {exports.isError ? <Failure error={exports.error} onRetry={() => void exports.refetch()} /> : null}
        {exports.data?.length === 0 ? (
          <p className={SMALL}>{t("exports.empty")}</p>
        ) : null}
        {exports.data?.length ? (
          <ul className="flex flex-col gap-3">
            {exports.data.map((item) => (
              <li key={item.kind} className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  <span className="block font-medium">{name(item.kind)}</span>
                  <span className={SMALL}>
                    {t("exports.made", { time: formatTime(item.made_at), size: formatSize(item.size) })}
                  </span>
                </span>
                <a
                  href={`/api/exports/${item.kind}`}
                  download
                  className={LINK_BUTTON}
                  aria-label={t("exports.downloadNamed", { name: name(item.kind) })}
                >
                  {t("exports.download")}
                </a>
              </li>
            ))}
          </ul>
        ) : null}
        {again.isSuccess ? (
          <Alert tone="good" title={t("exports.askedTitle")} live>
            <p>{t("exports.askedText")}</p>
          </Alert>
        ) : null}
        {again.isError ? (
          <Alert tone="critical" title={t("exports.failed")} live>
            <p>{again.error.message}</p>
          </Alert>
        ) : null}
      </div>
    </Card>
  );
}

function ReadersCard({ status }: { status: SystemStatus }) {
  const { t } = useTranslation("system");
  const used = status.readers.filter((r) => r.documents > 0 || r.alarms > 0);
  return (
    <Card title={t("readers.title")} className="md:col-span-2">
      {used.length === 0 ? (
        <p className="text-sm text-zinc-600 dark:text-zinc-300">{t("readers.none", { count: status.readers.length })}</p>
      ) : (
        <Table>
          <thead>
            <tr>
              <Th>{t("readers.reader")}</Th>
              <Th>{t("readers.version")}</Th>
              <Th>{t("readers.documents")}</Th>
              <Th>{t("readers.verified")}</Th>
              <Th>{t("readers.lastRead")}</Th>
              <Th>{t("readers.alarm")}</Th>
            </tr>
          </thead>
          <tbody>
            {used.map((r) => (
              <tr key={r.parser}>
                <Td>{r.name}</Td>
                <Td>{r.version}</Td>
                <Td>{r.documents}</Td>
                <Td>{r.statements ? `${r.verified}/${r.statements}` : t("readers.empty")}</Td>
                <Td>{r.last_read ? formatTime(r.last_read) : t("readers.empty")}</Td>
                <Td>{r.alarms ? <Badge tone="warning">{String(r.alarms)}</Badge> : t("readers.empty")}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

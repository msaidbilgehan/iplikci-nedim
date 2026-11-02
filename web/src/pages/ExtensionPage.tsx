// The browser extension (ADR-0016, F01): installing it from the folder the service keeps (K20), then pairing. This
// page asks the service for a one-time code, the user types it into the extension's window, and the extension becomes
// the e-mail connector. Paired extensions can be revoked.

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { useBridges, useRevokeBridge, useStartPairing, useSystem } from "../api/queries";
import type { Bridge } from "../api/types";
import { InstallCard } from "../components/extension/InstallCard";
import { HistoryDue } from "../components/HistoryDue";
import { Empty, Failure, Loading } from "../components/QueryState";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { Table, Td, Th } from "../components/ui/Table";
import { formatCode, formatTime } from "../lib/format";

export default function ExtensionPage() {
  const { t } = useTranslation("extension");
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={t("page.title")} description={t("page.description")} />
      <InstallCard />
      <PairingCard />
      <PairedCard />
    </div>
  );
}

/** A one-time pairing code for the extension's window; the setup wizard shows it too. */
export function PairingCard() {
  const { t } = useTranslation("extension");
  const pairing = useStartPairing();
  const left = useCountdown(pairing.data?.expires_in, pairing.submittedAt);
  const live = pairing.data !== undefined && left > 0;
  return (
    <Card title={t("pairing.title")}>
      <div className="flex flex-col gap-3">
        <ol className="list-decimal pl-5 text-sm">
          <li>{t("pairing.stepInstall")}</li>
          <li>{t("pairing.stepCode")}</li>
          <li>{t("pairing.stepEnter")}</li>
        </ol>
        {live ? (
          <div role="status" aria-live="polite" className="flex flex-col gap-1">
            <span className="text-sm text-zinc-600 dark:text-zinc-300">{t("pairing.code")}</span>
            <span className="font-mono text-3xl tracking-widest">{formatCode(pairing.data.code)}</span>
            <span className="text-sm text-zinc-600 dark:text-zinc-300">
              {t("pairing.left", { minutes: Math.ceil(left / 60) })}
            </span>
          </div>
        ) : null}
        {pairing.data !== undefined && !live ? (
          <Alert tone="warning" title={t("pairing.expiredTitle")}>
            <p>{t("pairing.expiredText")}</p>
          </Alert>
        ) : null}
        {pairing.isError ? <Failure error={pairing.error} onRetry={() => pairing.mutate()} /> : null}
        <Button className="self-start" onClick={() => pairing.mutate()} disabled={pairing.isPending}>
          {live ? t("pairing.again") : t("pairing.get")}
        </Button>
      </div>
    </Card>
  );
}

/** Seconds left of a code that lives `seconds` from `since` (ms); ticks every second while it lives. */
function useCountdown(seconds: number | undefined, since: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (seconds === undefined) {
      return undefined;
    }
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [seconds, since]);
  if (seconds === undefined) {
    return 0;
  }
  return Math.max(0, seconds - Math.floor((now - since) / 1000));
}

/** The paired extensions, each revocable; the setup wizard shows it too. */
export function PairedCard() {
  const { t } = useTranslation("extension");
  const bridges = useBridges();
  const mail = useSystem().data?.mail;
  return (
    <Card title={t("paired.title")}>
      {bridges.isPending ? <Loading /> : null}
      {bridges.isError ? <Failure error={bridges.error} onRetry={() => void bridges.refetch()} /> : null}
      {bridges.data?.length === 0 ? <Empty title={t("paired.emptyTitle")}>{t("paired.emptyText")}</Empty> : null}
      {bridges.data && bridges.data.length > 0 ? (
        <div className="flex flex-col gap-3">
          {mail?.history_due ? <HistoryDue startDay={mail.start_day} /> : null}
          <BridgeTable bridges={bridges.data} />
        </div>
      ) : null}
    </Card>
  );
}

function BridgeTable({ bridges }: { bridges: Bridge[] }) {
  const { t } = useTranslation("extension");
  const revoke = useRevokeBridge();
  return (
    <div className="flex flex-col gap-2">
      <Table>
        <thead>
          <tr>
            <Th>{t("paired.browser")}</Th>
            <Th>{t("paired.created")}</Th>
            <Th>{t("paired.seen")}</Th>
            <Th>{t("paired.state")}</Th>
            <Th>
              <span className="sr-only">{t("paired.action")}</span>
            </Th>
          </tr>
        </thead>
        <tbody>
          {bridges.map((b) => (
            <tr key={b.id}>
              <Td>{b.name || t("paired.name")}</Td>
              <Td>{formatTime(b.created_at)}</Td>
              <Td>{b.last_seen ? formatTime(b.last_seen) : t("paired.notSeen")}</Td>
              <Td>
                {b.active ? (
                  <Badge tone="good">{t("paired.active")}</Badge>
                ) : (
                  <Badge tone="neutral">{t("paired.revoked")}</Badge>
                )}
              </Td>
              <Td>
                {b.active ? (
                  <Button
                    variant="danger"
                    onClick={() => {
                      if (window.confirm(t("paired.confirm"))) {
                        revoke.mutate(b.id);
                      }
                    }}
                    disabled={revoke.isPending}
                  >
                    {t("paired.revoke")}
                  </Button>
                ) : null}
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
      {revoke.isError ? (
        <Alert tone="critical" title={t("paired.failed")} live>
          <p>{revoke.error.message}</p>
        </Alert>
      ) : null}
    </div>
  );
}

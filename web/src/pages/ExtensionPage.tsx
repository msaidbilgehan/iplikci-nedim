// The browser extension (ADR-0016, F01): installing it from the folder the service keeps (K20), then pairing. This
// page asks the service for a one-time code, the user types it into the extension's window, and the extension becomes
// the e-mail connector. Paired extensions can be revoked.

import { useEffect, useState } from "react";

import { useBridges, useRevokeBridge, useStartPairing, useSystem } from "../api/queries";
import type { Bridge } from "../api/types";
import { InstallCard } from "../components/extension/InstallCard";
import { HistoryDue } from "../components/HistoryDue";
import { Empty, Failure, Loading } from "../components/QueryState";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Table, Td, Th } from "../components/ui/Table";
import { formatCode, formatTime } from "../lib/format";

export default function ExtensionPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Tarayıcı eklentisi</h1>
      <p className="max-w-3xl text-sm text-zinc-700 dark:text-zinc-300">
        İplikçi Nedim Köprüsü, açık Gmail oturumunuzdaki banka iletilerini bu bilgisayardaki İplikçi Nedim'e taşır.
        Gmail'de hiçbir şeyi değiştirmez: iletiler okunmamış kalır, taşınmaz, silinmez. Yalnızca mail.google.com'a ve
        bu bilgisayara bağlanır; şifre istemez.
      </p>
      <InstallCard />
      <PairingCard />
      <PairedCard />
    </div>
  );
}

function PairingCard() {
  const pairing = useStartPairing();
  const left = useCountdown(pairing.data?.expires_in, pairing.submittedAt);
  const live = pairing.data !== undefined && left > 0;
  return (
    <Card title="Eşleştir">
      <div className="flex flex-col gap-3">
        <ol className="list-decimal pl-5 text-sm">
          <li>Eklentiyi “Kur” kartındaki adımlarla Chrome, Edge ya da Brave'e kurun.</li>
          <li>Aşağıdan bir eşleştirme kodu alın.</li>
          <li>Eklentinin penceresinde kodu girin; eşleşme bu sayfadan da görünür.</li>
        </ol>
        {live ? (
          <div role="status" aria-live="polite" className="flex flex-col gap-1">
            <span className="text-sm text-zinc-600 dark:text-zinc-300">Eşleştirme kodu</span>
            <span className="font-mono text-3xl tracking-widest">{formatCode(pairing.data.code)}</span>
            <span className="text-sm text-zinc-600 dark:text-zinc-300">
              Tek kullanımlık; {Math.ceil(left / 60)} dakika içinde girin.
            </span>
          </div>
        ) : null}
        {pairing.data !== undefined && !live ? (
          <Alert tone="warning" title="Kodun süresi doldu">
            <p>Yeni bir kod alın.</p>
          </Alert>
        ) : null}
        {pairing.isError ? <Failure error={pairing.error} onRetry={() => pairing.mutate()} /> : null}
        <Button className="self-start" onClick={() => pairing.mutate()} disabled={pairing.isPending}>
          {live ? "Yeni kod al" : "Eşleştirme kodu al"}
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

function PairedCard() {
  const bridges = useBridges();
  const mail = useSystem().data?.mail;
  return (
    <Card title="Eşleşmiş eklentiler">
      {bridges.isPending ? <Loading /> : null}
      {bridges.isError ? <Failure error={bridges.error} onRetry={() => void bridges.refetch()} /> : null}
      {bridges.data?.length === 0 ? (
        <Empty title="Henüz eşleşmiş bir eklenti yok">Eşleşince e-postalar eklentiyle gelir.</Empty>
      ) : null}
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
  const revoke = useRevokeBridge();
  return (
    <div className="flex flex-col gap-2">
      <Table>
        <thead>
          <tr>
            <Th>Tarayıcı</Th>
            <Th>Eşleşme</Th>
            <Th>Son görülme</Th>
            <Th>Durum</Th>
            <Th>
              <span className="sr-only">İşlem</span>
            </Th>
          </tr>
        </thead>
        <tbody>
          {bridges.map((b) => (
            <tr key={b.id}>
              <Td>{b.name || "Tarayıcı eklentisi"}</Td>
              <Td>{formatTime(b.created_at)}</Td>
              <Td>{b.last_seen ? formatTime(b.last_seen) : "Henüz yok"}</Td>
              <Td>{b.active ? <Badge tone="good">Etkin</Badge> : <Badge tone="neutral">İptal edildi</Badge>}</Td>
              <Td>
                {b.active ? (
                  <Button
                    variant="danger"
                    onClick={() => {
                      if (window.confirm("Bu eklentinin eşleşmesi iptal edilsin mi? E-postalar artık gelmez.")) {
                        revoke.mutate(b.id);
                      }
                    }}
                    disabled={revoke.isPending}
                  >
                    İptal et
                  </Button>
                ) : null}
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
      {revoke.isError ? (
        <Alert tone="critical" title="İptal edilemedi" live>
          <p>{revoke.error.message}</p>
        </Alert>
      ) : null}
    </div>
  );
}

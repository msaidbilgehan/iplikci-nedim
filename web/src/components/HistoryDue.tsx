// The browser extension has not scanned Gmail for the start day and the senders set now (ADR-0016): it scans after
// pairing, and again when either changes.

import { formatDay } from "../lib/format";
import { Alert } from "./ui/Alert";

export function HistoryDue({ startDay }: { startDay: string }) {
  return (
    <Alert tone="neutral" title="Geçmiş iletilerin taraması tamamlanmadı">
      <p>
        Eklenti eşleşince Gmail'i bir sekmede açar ve listedeki bankaların iletilerini arar (başlangıç günü:{" "}
        {formatDay(startDay)}). Tarama sürmüyorsa eklentinin penceresinde "Gmail'de eksikleri tara"ya basın.
      </p>
    </Alert>
  );
}

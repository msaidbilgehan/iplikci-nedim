// How the interface writes dates, times and sizes: 31.10.2026, 31.10.2026 14:03, 1,5 MB (features.md, shared rules).
// Times are shown in the computer's own time zone.

const DAY = new Intl.DateTimeFormat("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric" });
const MINUTE = new Intl.DateTimeFormat("tr-TR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});
const ONE_DECIMAL = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const UNITS = ["B", "KB", "MB", "GB", "TB"] as const;

/** "2026-10-31" (a calendar day) → "31.10.2026"; "" stays "". */
export function formatDay(iso: string): string {
  if (!iso) {
    return "";
  }
  const [year, month, day] = iso.slice(0, 10).split("-");
  return year && month && day ? `${day}.${month}.${year}` : iso;
}

/** An ISO time → "31.10.2026 14:03" in the local time zone; "" stays "". */
export function formatTime(iso: string): string {
  if (!iso) {
    return "";
  }
  const at = new Date(iso);
  return Number.isNaN(at.getTime()) ? iso : MINUTE.format(at).replace(",", "");
}

/** An ISO time → its local calendar day, "31.10.2026". */
export function formatDate(iso: string): string {
  const at = new Date(iso);
  return Number.isNaN(at.getTime()) ? iso : DAY.format(at);
}

/** Bytes in the largest unit under 1024 of it: 1536 → "1,5 KB". */
export function formatSize(bytes: number): string {
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return unit === 0 ? `${value} B` : `${ONE_DECIMAL.format(value)} ${UNITS[unit]}`;
}

/** A period of two calendar days: "01.02.2026 – 28.02.2026", or the one that is known. */
export function formatPeriod(start: string, end: string): string {
  if (start && end) {
    return `${formatDay(start)} – ${formatDay(end)}`;
  }
  return formatDay(start || end);
}

/** A pairing code as people type it: "ABCD-EFGH". */
export function formatCode(code: string): string {
  return code.length === 8 ? `${code.slice(0, 4)}-${code.slice(4)}` : code;
}

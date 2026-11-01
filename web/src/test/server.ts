// The service as the interface's tests see it: MSW answers the API with synthetic data, nothing leaves the process.

import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import type {
  Bridge,
  Calendar,
  CalendarItem,
  DocumentPage,
  Forecast,
  Labels,
  Money,
  Series,
  Subscriptions,
  SystemStatus,
} from "../api/types";

export const LABELS: Labels = {
  DocumentStatus: { processed: "İşlendi", unprocessed: "İşlenmedi", unreadable: "Okunamadı", removed: "Kaldırıldı" },
  DocumentKind: { account_statement: "Hesap dökümü", card_statement: "Kart ekstresi", receipt: "Dekont" },
  SourceKind: { email: "E-posta", upload: "Yükleme", inbox: "Gelen klasörü", import: "İçe aktarma" },
  SeriesStatus: {
    active: "Devam ediyor",
    ended: "Bitti",
    cancelled: "İptal edildi",
    paid_after_cancel: "İptalden sonra ödeme var",
  },
  SeriesPeriod: { month: "Ayda bir", half_year: "Altı ayda bir", year: "Yılda bir" },
  PaymentKind: {
    regular: "Düzenli ödeme",
    periodic: "Dönemsel ödeme",
    income: "Düzenli gelir",
    installment: "Kart taksiti",
    loan: "Kredi taksiti",
    card_due: "Kart son ödemesi",
  },
  Certainty: { confirmed: "Kesin", provisional: "Geçici", excluded: "Toplama girmez", info: "Bilgi" },
};

/** An amount in TL from its kuruş. */
export function tl(minor: number): Money {
  return { minor, currency: "TRY" };
}

const CASH = { id: "teb-123456789", label: "Örnek Vadesiz TL" };
const CARD = { id: "teb-1234", label: "Örnek Kart •1234" };

export function series(overrides: Partial<Series> = {}): Series {
  return {
    id: "fp-kira",
    payee: "Ev kirası",
    period: "month",
    status: "active",
    note: "",
    category: "Kira",
    necessity: "required",
    kind: "purchase",
    account: CASH,
    amount: tl(1500000),
    last_day: "2026-10-03",
    last_amount: tl(1500000),
    next_day: "2026-11-03",
    price_change: { before: tl(1400000), after: tl(1500000), since: "2026-07-03" },
    listed: true,
    payments: [
      {
        fingerprint: "fp-kira-10",
        day: "2026-10-03",
        amount: tl(1500000),
        document: "TEB Hesap Dökümü Ekim 2026.xls",
        certainty: "confirmed",
      },
      {
        fingerprint: "fp-kira-11",
        day: "2026-11-03",
        amount: tl(1500000),
        document: "TEB Dekont 03.11.2026.pdf",
        certainty: "provisional",
      },
    ],
    ...overrides,
  };
}

export const SUBSCRIPTIONS: Subscriptions = {
  window: ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"],
  as_of: "2026-10-31",
  series: [
    series(),
    series({
      id: "fp-muzik",
      payee: "Örnek Müzik",
      category: "Dijital Abonelikler",
      necessity: "optional",
      account: CARD,
      amount: tl(9999),
      last_day: "2026-10-09",
      last_amount: tl(9999),
      next_day: "2026-11-09",
      price_change: null,
    }),
    series({
      id: "fp-sigorta",
      payee: "Örnek Sigorta",
      period: "year",
      category: "Sigorta",
      amount: tl(480000),
      last_day: "2026-01-10",
      last_amount: tl(480000),
      next_day: "2027-01-08",
      price_change: { before: tl(400000), after: tl(480000), since: "2026-01-10" },
    }),
    series({
      id: "fp-su",
      payee: "Su faturası",
      status: "ended",
      note: "Belgelerde yok: belgesi olmayan bir hesaptan ödeniyor olabilir.",
      category: "Elektrik, Su & Doğalgaz",
      amount: tl(25000),
      last_day: "2026-05-20",
      last_amount: tl(25000),
      next_day: null,
      price_change: null,
    }),
    series({ id: "fp-eski", payee: "Eski Dergi", status: "ended", listed: false, next_day: null }),
  ],
  income: [
    series({
      id: "fp-maas",
      payee: "Örnek İşveren A.Ş.",
      category: "Maaş",
      necessity: null,
      kind: "income",
      amount: tl(4000000),
      last_day: "2026-10-01",
      last_amount: tl(4150000),
      next_day: "2026-11-01",
      price_change: null,
    }),
  ],
  installments: [
    {
      card: CARD,
      title: "Örnek Elektronik",
      number: 8,
      count: 12,
      amount: tl(50000),
      left: 4,
      remaining: tl(200000),
      last_day: "2027-02-15",
      fingerprint: "fp-elektronik",
    },
  ],
};

function item(overrides: Partial<CalendarItem>): CalendarItem {
  return {
    day: "2026-12-03",
    kind: "regular",
    title: "Ev kirası",
    account: CASH,
    direction: "out",
    amount: tl(1500000),
    minimum: null,
    basis: "son ödeme 03.10.2026: 15.000,00 TL",
    series: "fp-kira",
    fingerprints: ["fp-kira-10"],
    ...overrides,
  };
}

export const CALENDAR: Calendar = {
  today: "2026-11-15",
  end: "2027-01-13",
  items: [
    item({
      day: "2026-11-25",
      kind: "card_due",
      title: "Örnek Kart •1234",
      account: CARD,
      amount: tl(900000),
      minimum: tl(180000),
      basis: "ekstrenin dönem borcu 9.000,00 TL, asgari ödeme 1.800,00 TL",
      series: "",
      fingerprints: [],
    }),
    item({
      day: "2026-12-01",
      kind: "income",
      title: "Örnek İşveren A.Ş.",
      direction: "in",
      amount: tl(4000000),
      basis: "son üç tutarın medyanı (Ağustos 2026 – Ekim 2026)",
      series: "fp-maas",
    }),
    item({}),
  ],
};

// From 15 November: 1.000 TL, 1 TL a day of other spending, and the rent of 15.000 TL on 3 December.
const DAYS = Array.from({ length: 60 }, (_, i) => ({
  day: new Date(Date.UTC(2026, 10, 15 + i)).toISOString().slice(0, 10),
  balance: tl(100000 - (i + 1) * 100 - (i >= 18 ? 1500000 : 0)),
}));

export const FORECAST: Forecast = {
  label: "tahmin",
  today: "2026-11-15",
  end: "2027-01-13",
  accounts: [
    {
      account: CASH,
      start: {
        balance: tl(100000),
        stated: tl(250000),
        day: "2026-10-31",
        source: "statement",
        moves: 2,
        through: "2026-11-04",
      },
      end_balance: DAYS[59]!.balance,
      lowest: DAYS[59]!,
      negative: DAYS[18]!,
      spend: { monthly: tl(3000), months: SUBSCRIPTIONS.window, after: null },
      cards: null,
      interest: null,
      items: CALENDAR.items.slice(2),
      days: DAYS,
      notes: [
        "Başlangıç: 31.10.2026 tarihli hesap dökümünün kapanış bakiyesi 2.500,00 TL; sonraki 2 dekont ve bildirimle " +
          "−1.500,00 TL; 04.11.2026 sonrasının hareketleri belgelerde yok.",
        "Seri dışı çıkışlar: Nisan 2026 – Eylül 2026 arasındaki 6 tam ayın medyanı, ayda 30,00 TL, günlere yayıldı.",
        "KMH faiz oranı belgelerde yazmadığı için faiz tahmin edilmedi.",
      ],
    },
  ],
  elsewhere: [item({ day: "2026-12-09", title: "Örnek Müzik", account: CARD, amount: tl(9999), series: "fp-muzik" })],
  skipped: [
    { account: { id: "garanti-1234567", label: "Garanti Vadesiz TL" }, reason: "bakiyesi hiçbir belgede yazmıyor" },
  ],
  notes: ["Bu bir tahmindir: belgelerdeki son bakiyeden ve geçmiş ödemelerden çıkarıldı."],
};

export function systemStatus(overrides: Partial<SystemStatus> = {}): SystemStatus {
  return {
    service: { version: "0.4.0", started_at: "2026-11-01T07:30:00+00:00", pid: 4242, home: "/veri/iplikci" },
    documents: { processed: 3, unreadable: 1 },
    readers: [
      {
        parser: "teb.account_html",
        name: "TEB hesap hareketleri",
        version: "1.1",
        documents: 3,
        statements: 3,
        verified: 2,
        last_read: "2026-11-01T07:31:00+00:00",
        alarms: 0,
      },
    ],
    disk: { vault: 1536, database: 2 * 1024 * 1024, free: 50 * 1024 ** 3 },
    queue: { counts: { queued: 1, done: 9 }, next_run: "", failures: [] },
    mail: {
      connector: "imap",
      configured: true,
      last_run: "2026-11-01T07:45:00+00:00",
      last_error: "",
      stopped: false,
      start_day: "2024-01-01",
      history_due: false,
      refused: [],
      coverage: {
        total: 200,
        read: 30,
        attached: 40,
        no_money: 100,
        business: 12,
        unknown: 18,
        share: 0.91,
        left: [{ domain: "banka.example", template: "Haftalık bildiriminiz", count: 18 }],
      },
    },
    backup: {
      last: "2026-11-01T00:30:00+00:00",
      next: "2026-11-02T00:30:00+00:00",
      count: 3,
      size: 10 * 1024 * 1024,
      rehearsal: "",
      rehearsal_ok: null,
    },
    ...overrides,
  };
}

export const FIRST_PAGE: DocumentPage = {
  items: [
    {
      sha256: "a".repeat(64),
      name: "TEB Hesap Dökümü Şubat 2026",
      file: "subat.xls",
      kind: "account_statement",
      parser: "teb.account_html",
      reader: "TEB hesap hareketleri",
      status: "processed",
      reason: "",
      verified: true,
      period_start: "2026-02-01",
      period_end: "2026-02-28",
      sources: ["upload"],
      added_at: "2026-11-01T07:31:00+00:00",
      size: 2048,
    },
    {
      sha256: "b".repeat(64),
      name: "sifreli.pdf",
      file: "sifreli.pdf",
      kind: "",
      parser: "",
      reader: "",
      status: "unreadable",
      reason: "PDF şifreli",
      verified: null,
      period_start: "",
      period_end: "",
      sources: ["email"],
      added_at: "2026-10-30T09:00:00+00:00",
      size: 4096,
    },
  ],
  next: "imlec-2",
};

export const SECOND_PAGE: DocumentPage = {
  items: [{ ...FIRST_PAGE.items[0]!, sha256: "c".repeat(64), name: "TEB Hesap Dökümü Ocak 2026", file: "ocak.xls" }],
  next: "",
};

export const BRIDGES: Bridge[] = [
  { id: "k1", name: "Chrome 140, macOS", created_at: "2026-11-01T08:00:00+00:00", last_seen: "", active: true },
];

export const handlers = [
  http.get("/api/labels", () => HttpResponse.json(LABELS)),
  http.get("/api/subscriptions", () => HttpResponse.json(SUBSCRIPTIONS)),
  http.get("/api/calendar", () => HttpResponse.json(CALENDAR)),
  http.get("/api/forecast", () => HttpResponse.json(FORECAST)),
  http.get("/api/system", () => HttpResponse.json(systemStatus())),
  http.get("/api/bridge", () => HttpResponse.json(BRIDGES)),
  http.get("/api/documents", ({ request }) => {
    const url = new URL(request.url);
    if (url.searchParams.get("cursor") === "imlec-2") {
      return HttpResponse.json(SECOND_PAGE);
    }
    if (url.searchParams.getAll("status").includes("unreadable")) {
      return HttpResponse.json({ items: [FIRST_PAGE.items[1]], next: "" });
    }
    return HttpResponse.json(FIRST_PAGE);
  }),
];

export const server = setupServer(...handlers);

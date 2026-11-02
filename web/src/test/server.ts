// The service as the interface's tests see it: MSW answers the API with synthetic data, nothing leaves the process.

import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import type {
  AccountItem,
  Accounts,
  AlertEvent,
  AlertRule,
  AlertRules,
  Bridge,
  Calendar,
  CalendarItem,
  ChannelState,
  DocumentPage,
  FeedDetail,
  FeedItem,
  FeedPage,
  Forecast,
  InvoiceItem,
  Invoices,
  Labels,
  Money,
  NotificationItem,
  Notifications,
  NotifySettings,
  Now,
  OtherSenders,
  Row,
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
    bill: "Fatura",
  },
  Certainty: { confirmed: "Kesin", provisional: "Geçici", excluded: "Ekstrede yok", info: "Yalnızca bilgi" },
  InvoiceKind: { bill: "Fatura", receipt: "Makbuz" },
  InvoiceStatus: { matched: "Eşleşti", pending: "Bekliyor", unmatched: "Eşleşmedi" },
  Channel: { in_app: "Uygulama içi", desktop: "Masaüstü", email: "E-posta", telegram: "Telegram" },
  DetailLevel: { full: "Tam", summary: "Özet", minimal: "Asgari" },
  DeliveryStatus: {
    pending: "Gönderilecek",
    sent: "Gönderildi",
    held: "Özete kaldı",
    digested: "Özetle gönderildi",
    failed: "Gönderilemedi",
  },
  ChannelStage: {
    ready: "Hazır",
    stopped: "Durdu",
    unavailable: "Kullanılamıyor",
    no_bot: "Kurulmadı",
    token_lost: "Belirteç gerekli",
    not_paired: "Eşleşmedi",
  },
  EventKind: {
    "document.received": "Belge geldi",
    "document.processed": "Belge okundu",
    "document.unreadable": "Belge okunamadı",
    "transaction.large": "Büyük harcama",
    "invoice.unmatched": "Fatura eşleşmedi",
    "payment.due_soon": "Son ödeme yaklaşıyor",
    "balance.forecast_negative": "Hesap eksiye düşecek",
    "month.closed": "Ay kapandı",
    "backup.failed": "Yedek alınamadı",
  },
  AccountType: { credit_card: "Kredi kartı", current: "Vadesiz hesap", fx: "Döviz hesabı" },
  MonthStatus: { closed: "Kapandı", waiting: "Ekstre bekleniyor", missing: "Belge eksik", running: "Ay sürüyor" },
  TransactionKind: { purchase: "Harcama", income: "Gelir", interest_fee: "Faiz & banka ücreti" },
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

function invoice(overrides: Partial<InvoiceItem>): InvoiceItem {
  return {
    key: `${"a".repeat(64)}:0`,
    kind: "bill",
    status: "pending",
    seller: "Örnekenerji Elektrik Perakende Satış A.Ş.",
    number: "OE2026000000045",
    issued: "2026-11-05",
    due: "2026-11-25",
    total: tl(64250),
    lines: [],
    window: { start: "2026-11-05", end: "2026-11-28" },
    document: "Örnekenerji faturası.xml",
    sha256: "a".repeat(64),
    row: null,
    reasons: [],
    ...overrides,
  };
}

// As /api/invoices orders them: pending by the last day their row is looked for, then unmatched, then matched.
export const INVOICES: Invoices = {
  items: [
    invoice({
      key: `${"d".repeat(64)}:0`,
      kind: "receipt",
      seller: "Örnekflix International B.V.",
      number: "",
      issued: "2026-11-12",
      due: null,
      total: { minor: 999, currency: "USD" },
      window: { start: "2026-11-11", end: "2026-11-15" },
      document: "Örnekflix makbuzu.eml",
      sha256: "d".repeat(64),
    }),
    invoice({}),
    invoice({
      key: `${"b".repeat(64)}:0`,
      status: "unmatched",
      seller: "ÖRNEKCELL İLETİŞİM HİZMETLERİ A.Ş.",
      number: "OC2026000000101",
      issued: "2026-10-03",
      due: "2026-10-20",
      total: tl(41290),
      lines: [
        { description: "Aylık paket", amount: tl(40000), quantity: "1" },
        { description: "Ek internet", amount: tl(1290), quantity: null },
      ],
      window: { start: "2026-10-03", end: "2026-10-23" },
      document: "Örnekcell faturası.xml",
      sha256: "b".repeat(64),
      reasons: [
        "Başkası ödemiş olabilir.",
        "Belgesi olmayan bir hesaptan ya da nakit ödenmiş olabilir.",
        "Henüz ödenmemiş olabilir.",
      ],
    }),
    invoice({
      key: `${"c".repeat(64)}:0`,
      kind: "receipt",
      status: "matched",
      seller: "Örnek Uygulama Mağazası",
      number: "R-1",
      issued: "2026-10-10",
      due: null,
      total: tl(5999),
      window: { start: "2026-10-09", end: "2026-10-13" },
      document: "Örnek Uygulama Mağazası makbuzu.eml",
      sha256: "c".repeat(64),
      row: {
        fingerprint: "fp-uygulama",
        day: "2026-10-11",
        account: CARD,
        amount: tl(5999),
        description: "ORNEKUYGULAMA.COM/BILL",
      },
    }),
  ],
  counts: { pending: 2, unmatched: 1, matched: 1 },
};

export const OTHER_SENDERS: OtherSenders = { domains: ["ornekcell.example", "fatura.example"] };

// --- what stands now and the feed (F05) -----------------------------------------------------------------------------

const FX = { id: "teb-eur-1", label: "Örnek Döviz EUR" };
const UNKNOWN = { id: "garanti-1234567", label: "Garanti Vadesiz TL" };

export function row(overrides: Partial<Row> = {}): Row {
  return {
    fingerprint: "0123456789abcdef0123",
    day: "2026-11-15",
    account: CARD,
    title: "Örnek Elektronik",
    description: "ORNEK ELEKTRONIK ISTANBUL",
    merchant: "Örnek Elektronik",
    counterparty: "",
    amount: tl(1250000),
    direction: "out",
    kind: "purchase",
    category: "Elektronik",
    group: "Alışveriş",
    necessity: "optional",
    counted: true,
    expense: true,
    certainty: "provisional",
    original: "",
    installment: "",
    note: "",
    tags: [],
    invoice: "",
    document: "e".repeat(64),
    ...overrides,
  };
}

// From 15 November: two balances (one moved by receipts since its statement, one in euros), one account no document
// gives a balance for, a card with its statement and its period, the month's pace and the next 14 days.
export const NOW: Now = {
  today: "2026-11-15",
  balances: [
    {
      account: CASH,
      type: "current",
      balance: tl(100000),
      value: tl(100000),
      rate: null,
      rate_day: null,
      stated: tl(250000),
      on: "2026-10-31",
      source: "statement",
      moves: 2,
      through: "2026-11-04",
      certainty: "provisional",
      note: "31.10.2026 dökümünde 2.500,00 TL; sonraki 2 dekont ve bildirimle −1.500,00 TL",
    },
    {
      account: FX,
      type: "fx",
      balance: { minor: 50000, currency: "EUR" },
      value: tl(1850000),
      rate: "37.0000",
      rate_day: "2026-10-31",
      stated: { minor: 50000, currency: "EUR" },
      on: "2026-10-31",
      source: "statement",
      moves: 0,
      through: "2026-10-31",
      certainty: "confirmed",
      note: "31.10.2026 dökümünde 500,00 EUR",
    },
  ],
  unknown: [{ account: UNKNOWN, reason: "bakiyesi hiçbir belgede yazmıyor" }],
  cards: [
    {
      account: CARD,
      type: "credit_card",
      cut: "2026-10-28",
      total: tl(900000),
      due: "2026-11-25",
      minimum: tl(180000),
      limit: tl(5000000),
      paid: tl(200000),
      debt: tl(700000),
      last: { start: "2026-09-29", end: "2026-10-28", spent: tl(900000), rows: 14 },
      current: { start: "2026-10-29", end: "2026-11-28", spent: tl(320000), rows: 5 },
      certainty: "provisional",
      note: "28.10.2026 ekstresi; kesimden sonra 2.000,00 TL ödendi",
    },
  ],
  pace: {
    month: "2026-11",
    partial: true,
    day: 15,
    days: 30,
    spent: tl(420000),
    provisional: tl(120000),
    typical: tl(2015299),
    by_day: tl(980000),
    months: ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"],
    covered: 0.6,
    note: "Kasım 2026 sürüyor: rakamlar bugüne kadar gelen belgelerden. Tipik ay: Mayıs 2026 – Ekim 2026 arasındaki 6 tam ayın medyanı.",
  },
  upcoming: [
    item({ day: "2026-11-15", title: "Örnek Müzik", account: CARD, amount: tl(9999), series: "fp-muzik" }),
    item({
      day: "2026-11-16",
      kind: "income",
      title: "Örnek İşveren A.Ş.",
      direction: "in",
      amount: tl(4000000),
      basis: "son üç tutarın medyanı (Ağustos 2026 – Ekim 2026)",
      series: "fp-maas",
    }),
    CALENDAR.items[0]!,
  ],
  end: "2026-11-28",
};

const NO_DETAIL: FeedDetail = {
  title: "",
  amount: null,
  minimum: null,
  balance: null,
  old: null,
  new: null,
  day: null,
  days: null,
  payment: null,
  period: null,
  cancelled: "",
  status: null,
  count: null,
  first: null,
  last: null,
  provisional: null,
  source: null,
  document_kind: null,
  parser: "",
  reader: "",
  version: "",
  reason: "",
  stage: "",
  unverified: [],
};

export function feedItem(overrides: Omit<Partial<FeedItem>, "detail"> & { detail?: Partial<FeedDetail> } = {}): FeedItem {
  const { detail, ...rest } = overrides;
  return {
    id: 1,
    at: "2026-11-15T12:00:00+00:00",
    kind: "document.received",
    label: "Belge geldi",
    text: "Yeni bir belge geldi.",
    target: "",
    account: null,
    certainty: null,
    row: null,
    document: null,
    link: null,
    ...rest,
    detail: { ...NO_DETAIL, ...detail },
  };
}

// The newest page of the log: a large purchase and an unreadable document today, a month closed and a due date
// coming yesterday, a statement read five days ago; one older page holds a failed backup.
export const FEED_FIRST: FeedPage = {
  items: [
    feedItem({
      id: 31,
      at: "2026-11-15T12:30:00+00:00",
      kind: "transaction.large",
      label: "Büyük harcama",
      text: "Örnek Elektronik: 12.500,00 TL (•1234, 15.11.2026).",
      target: "0123456789abcdef0123",
      account: CARD,
      certainty: "provisional",
      row: row(),
      link: { screen: "transaction", id: "0123456789abcdef0123", query: {} },
      detail: { title: "Örnek Elektronik", amount: tl(1250000), day: "2026-11-15" },
    }),
    feedItem({
      id: 30,
      at: "2026-11-15T11:00:00+00:00",
      kind: "document.unreadable",
      label: "Belge okunamadı",
      text: "Bir belge okunamadı; Belgeler ekranına bakın.",
      target: "b".repeat(64),
      document: { sha256: "b".repeat(64), name: "sifreli.pdf", kind: null, status: "unreadable" },
      link: { screen: "document", id: "b".repeat(64), query: {} },
      detail: { reason: "PDF şifreli" },
    }),
    feedItem({
      id: 29,
      at: "2026-11-14T12:00:00+00:00",
      kind: "month.closed",
      label: "Ay kapandı",
      text: "Ekim 2026 kapandı: bütün belgeleri geldi ve doğrulandı.",
      target: "2026-10",
      link: { screen: "month", id: "2026-10", query: {} },
      detail: { status: "closed" },
    }),
    feedItem({
      id: 28,
      at: "2026-11-14T11:00:00+00:00",
      kind: "payment.due_soon",
      label: "Son ödeme yaklaşıyor",
      text: "Örnek Kart •1234 · Kart son ödemesi: 10 gün sonra (25.11.2026), 9.000,00 TL.",
      target: "card_due|teb-1234|Örnek Kart •1234|2026-11-25",
      account: CARD,
      link: { screen: "calendar", id: "2026-11-25", query: {} },
      detail: {
        title: "Örnek Kart •1234",
        amount: tl(900000),
        minimum: tl(180000),
        day: "2026-11-25",
        days: 10,
        payment: "card_due",
      },
    }),
    feedItem({
      id: 27,
      at: "2026-11-10T12:00:00+00:00",
      kind: "document.processed",
      label: "Belge okundu",
      text: "Bir belge okundu.",
      target: "e".repeat(64),
      account: CARD,
      document: { sha256: "e".repeat(64), name: "Örnek Kart Ekstresi Ekim 2026.pdf", kind: "card_statement", status: "processed" },
      link: { screen: "document", id: "e".repeat(64), query: {} },
      detail: { document_kind: "card_statement", parser: "ornek.card", reader: "Örnek kart ekstresi", version: "1.2" },
    }),
  ],
  next: 27,
};

export const FEED_OLDER: FeedPage = {
  items: [
    feedItem({
      id: 12,
      at: "2026-11-01T12:00:00+00:00",
      kind: "backup.failed",
      label: "Yedek alınamadı",
      text: "Gece yedeği alınamadı: disk dolu.",
      link: { screen: "system", id: "", query: {} },
      detail: { stage: "backup", reason: "disk dolu" },
    }),
  ],
  next: null,
};

function accountItem(overrides: Partial<AccountItem> = {}): AccountItem {
  return {
    account: CASH,
    label: CASH.label,
    alias: "",
    bank: "Örnek Bank",
    type: "current",
    group: "current",
    balance: tl(100000),
    value: tl(100000),
    day: "2026-11-04",
    certainty: "provisional",
    note: "",
    freshness: null,
    month: { month: "2026-11", money_in: tl(0), money_out: tl(150000), rows: 2, provisional: 2, note: "" },
    closed: false,
    link: { screen: "account", id: CASH.id, query: {} },
    ...overrides,
  };
}

export const ACCOUNTS: Accounts = {
  today: "2026-11-15",
  groups: [
    {
      group: "cards",
      assets: tl(0),
      debts: tl(700000),
      total: tl(-700000),
      unvalued: 0,
      accounts: [accountItem({ account: CARD, label: CARD.label, type: "credit_card", group: "cards" })],
    },
    {
      group: "current",
      assets: tl(100000),
      debts: tl(0),
      total: tl(100000),
      unvalued: 1,
      accounts: [
        accountItem(),
        accountItem({ account: UNKNOWN, label: UNKNOWN.label, bank: "Garanti BBVA", balance: null, value: null }),
      ],
    },
    {
      group: "fx",
      assets: tl(1850000),
      debts: tl(0),
      total: tl(1850000),
      unvalued: 0,
      accounts: [accountItem({ account: FX, label: FX.label, type: "fx", group: "fx" })],
    },
  ],
  closed: [],
  assets: tl(1950000),
  debts: tl(700000),
  total: tl(1250000),
  note: "",
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
      accounts: [{ id: "teb-123456789", label: "TEB Vadesiz TL 123456789", bank: "TEB" }],
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
      accounts: [],
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

export function notification(overrides: Partial<NotificationItem> = {}): NotificationItem {
  return {
    id: 4,
    created_at: "2026-11-01T09:00:00+00:00",
    rule: "Ay kapandı",
    kind: "month.closed",
    target: "2026-10",
    channel: "in_app",
    detail: "full",
    title: "Ay kapandı",
    body: "Ekim 2026 kapandı: bütün belgeleri geldi ve doğrulandı.",
    status: "sent",
    attempts: 0,
    sent_at: "2026-11-01T09:00:00+00:00",
    error: "",
    read: true,
    ...overrides,
  };
}

const DUE = {
  rule: "Son ödemeye 3 gün",
  kind: "payment.due_soon",
  target: "card_due|teb-1234|Örnek Kart •1234|2026-11-05",
  title: "Son ödeme yaklaşıyor",
};
const LARGE = { rule: "Büyük harcama", kind: "transaction.large", target: "3f9a2c7d1e5b4a60", title: "Büyük harcama" };

// The box as /api/notifications?channel=in_app gives it: newest first, two not seen yet.
export const BOX: Notifications = {
  items: [
    notification({
      ...DUE,
      id: 12,
      created_at: "2026-11-02T08:15:00+00:00",
      sent_at: "2026-11-02T08:15:00+00:00",
      body: "Örnek Kart •1234 · Kart son ödemesi: 3 gün sonra (05.11.2026), 9.000,00 TL.",
      read: false,
    }),
    notification({
      ...LARGE,
      id: 9,
      created_at: "2026-11-01T21:40:00+00:00",
      sent_at: "2026-11-01T21:40:00+00:00",
      body: "Örnek Elektronik: 12.500,00 TL (•1234, 01.11.2026).",
      read: false,
    }),
    notification(),
  ],
  unread: 2,
};

// Every channel's notifications, newest first: one given up after its attempts with the last error, one kept back
// for the digest, one sent within a digest, one sent by e-mail and one of the box.
export const LOG: Notifications = {
  items: [
    notification({
      ...DUE,
      id: 13,
      created_at: "2026-11-02T08:15:00+00:00",
      channel: "telegram",
      detail: "summary",
      body: "Kart son ödemesi 3 gün sonra: 9.000,00 TL.",
      status: "failed",
      attempts: 8,
      sent_at: "",
      error: "Telegram'a ulaşılamadı: zaman aşımı.",
      read: false,
    }),
    notification({
      ...LARGE,
      id: 10,
      created_at: "2026-11-01T23:40:00+00:00",
      channel: "desktop",
      detail: "summary",
      body: "Büyük harcama: 12.500,00 TL.",
      status: "held",
      sent_at: "",
      read: false,
    }),
    notification({
      id: 7,
      rule: "Fatura eşleşmedi",
      kind: "invoice.unmatched",
      target: `${"b".repeat(64)}:0`,
      channel: "desktop",
      detail: "summary",
      title: "Fatura eşleşmedi",
      body: "Bir fatura hiçbir banka satırıyla eşleşmedi; yalnızca bilgi.",
      status: "digested",
      sent_at: "2026-11-01T08:00:00+00:00",
      created_at: "2026-10-31T23:30:00+00:00",
      read: false,
    }),
    notification({
      id: 6,
      rule: "Belge okunamadı",
      kind: "document.unreadable",
      target: "a".repeat(64),
      channel: "email",
      title: "Belge okunamadı",
      body: "Bir belge okunamadı; Belgeler ekranına bakın.",
      read: false,
    }),
    notification(),
  ],
  unread: 2,
};

// What the service says of the Telegram channel at each stage of its setup (app/notify.py).
export const TELEGRAM_NOTES = {
  none: "Bot belirteci girilmedi: BotFather'da bir bot oluşturup belirtecini girin.",
  unpaired: "Botla sohbet eşleşmedi: eşleştirme kodunu bota gönderin.",
  paired: "@ornek_bot botuyla eşleşti.",
};

export function telegramState(overrides: Partial<ChannelState> = {}): ChannelState {
  return { channel: "telegram", on: true, ready: false, stage: "no_bot", note: TELEGRAM_NOTES.none, ...overrides };
}

export const TELEGRAM_UNPAIRED = telegramState({ stage: "not_paired", note: TELEGRAM_NOTES.unpaired });
export const TELEGRAM_PAIRED = telegramState({ stage: "ready", ready: true, note: TELEGRAM_NOTES.paired });

export const EMAIL_NOTE =
  "E-posta kanalı, e-postası uygulama şifresiyle (IMAP) bağlı bir hesap ister. Bu hesap tarayıcı eklentisiyle bağlı " +
  "(Gelişmiş Koruma'da uygulama şifresi yok); Telegram ve masaüstü kullanılabilir.";

export function notifySettings(telegram: ChannelState = telegramState()): NotifySettings {
  return {
    quiet_hours: "23:00-08:00",
    detail: { desktop: "summary", telegram: "summary", email: "full" },
    channels: [
      { channel: "in_app", on: true, ready: true, stage: "ready", note: "Arayüzdeki bildirim kutusu; her zaman açık." },
      { channel: "desktop", on: true, ready: true, stage: "ready", note: "Bu bilgisayarın bildirim merkezi." },
      telegram,
      { channel: "email", on: false, ready: false, stage: "unavailable", note: EMAIL_NOTE },
    ],
    counts: { pending: 0, sent: 3, held: 1, digested: 1, failed: 1 },
    unread: 2,
  };
}

export const ALERT_EVENTS: AlertEvent[] = [
  { kind: "payment.due_soon", label: "Son ödeme yaklaşıyor", days: true, amount: true, text: true },
  { kind: "balance.forecast_negative", label: "Hesap eksiye düşecek", days: true, amount: true, text: true },
  { kind: "transaction.large", label: "Büyük harcama", days: false, amount: true, text: true },
  { kind: "month.closed", label: "Ay kapandı", days: false, amount: false, text: false },
];

export function alertRule(overrides: Partial<AlertRule> = {}): AlertRule {
  return {
    name: "Son ödemeye 3 gün",
    event: "payment.due_soon",
    condition: { days: 3, amount: null, text: "" },
    channels: ["desktop", "telegram"],
    detail: null,
    enabled: true,
    quiet: true,
    ...overrides,
  };
}

// The user's rules/alerts.yaml as the service reads it back.
export const ALERT_RULES: AlertRules = {
  rules: [
    alertRule(),
    alertRule({
      name: "Büyük harcama",
      event: "transaction.large",
      condition: { days: null, amount: 750000, text: "" },
      channels: ["telegram"],
      detail: "minimal",
      quiet: false,
    }),
    alertRule({
      name: "Ay kapandı",
      event: "month.closed",
      condition: { days: null, amount: null, text: "" },
      channels: [],
      enabled: false,
    }),
  ],
  own: true,
  problem: "",
  events: ALERT_EVENTS,
};

export const handlers = [
  http.get("/api/labels", () => HttpResponse.json(LABELS)),
  http.get("/api/feed", ({ request }) =>
    HttpResponse.json(new URL(request.url).searchParams.get("before") === "27" ? FEED_OLDER : FEED_FIRST),
  ),
  http.get("/api/feed/now", () => HttpResponse.json(NOW)),
  http.get("/api/accounts", () => HttpResponse.json(ACCOUNTS)),
  http.get("/api/subscriptions", () => HttpResponse.json(SUBSCRIPTIONS)),
  http.get("/api/calendar", () => HttpResponse.json(CALENDAR)),
  http.get("/api/forecast", () => HttpResponse.json(FORECAST)),
  http.get("/api/invoices", () => HttpResponse.json(INVOICES)),
  http.get("/api/settings/mail/other-senders", () => HttpResponse.json(OTHER_SENDERS)),
  http.get("/api/system", () => HttpResponse.json(systemStatus())),
  http.get("/api/bridge", () => HttpResponse.json(BRIDGES)),
  http.get("/api/notifications", ({ request }) =>
    HttpResponse.json(new URL(request.url).searchParams.get("channel") === "in_app" ? BOX : LOG),
  ),
  http.get("/api/notify/settings", () => HttpResponse.json(notifySettings())),
  http.get("/api/rules/alerts", () => HttpResponse.json(ALERT_RULES)),
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

// The service as the interface's tests see it: MSW answers the API with synthetic data, nothing leaves the process.

import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import type {
  AccountItem,
  AccountPage,
  Accounts,
  AlertEvent,
  AlertRule,
  AlertRules,
  BackupItem,
  Bridge,
  Calendar,
  CalendarItem,
  Category,
  CategoryRules,
  ChannelState,
  Coverage,
  Dashboard,
  DocumentDetail,
  DocumentPage,
  DocumentView,
  ExportItem,
  ExtensionInfo,
  FeedDetail,
  FeedItem,
  FeedPage,
  Flows,
  Forecast,
  FxRates,
  Holdings,
  Insights,
  InvoiceItem,
  Invoices,
  Labels,
  Money,
  MonthClosing,
  MonthEnd,
  MonthEndAccount,
  MonthEndDetail,
  MonthEndList,
  MonthStatus,
  NotificationItem,
  Notifications,
  NotifySettings,
  Now,
  OtherSenders,
  Row,
  RuleChange,
  Series,
  ServiceState,
  Settings,
  Setup,
  Spending,
  Subscriptions,
  SystemStatus,
  TodoItem,
  Todos,
  TransactionDetail,
  TransactionPage,
} from "../api/types";

export const LABELS: Labels = {
  DocumentStatus: { processed: "İşlendi", unprocessed: "İşlenmedi", unreadable: "Okunamadı", removed: "Kaldırıldı" },
  DocumentKind: {
    account_statement: "Hesap dökümü",
    card_statement: "Kart ekstresi",
    receipt: "Dekont",
    notice: "Banka bildirimi",
    invoice: "Fatura ya da makbuz",
  },
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
  AccountType: {
    credit_card: "Kredi kartı",
    debit_card: "Banka kartı",
    current: "Vadesiz hesap",
    deposit: "Vadeli hesap",
    overdraft: "Kredili mevduat",
    fx: "Döviz hesabı",
    gold: "Altın hesabı",
    brokerage: "Yatırım hesabı",
    loan: "Kredi",
  },
  AccountGroup: {
    cards: "Kredi kartları",
    current: "Vadesiz",
    deposit: "Vadeli",
    overdraft: "KMH",
    fx: "Döviz",
    gold: "Altın",
    brokerage: "Yatırım",
    loan: "Krediler",
  },
  RateSource: { document: "Belgedeki kur" },
  PaidStatus: {
    full: "Tamamı ödendi",
    minimum: "Asgarisi ödendi",
    partial: "Bir kısmı ödendi",
    unpaid: "Ödenmedi",
    open: "Son ödeme günü gelmedi",
    nothing_due: "Borç yoktu",
  },
  FlowKind: {
    account: "Hesap",
    income: "Gelir",
    spending: "Harcama",
    people: "Kişiler",
    saving: "Birikim ve yatırım",
    loan: "Kredi",
    cash: "Nakit",
    elsewhere: "Başka bir yer",
  },
  StatementCheck: { verified: "Tutarlı", failed: "Tutmuyor", nothing: "Denetlenecek satır yok" },
  TodoKind: {
    uncategorized: "Kategorisiz işlemler",
    missing_documents: "Eksik belge",
    unprocessed_document: "İşlenmeyen belge",
    split_dropped: "Uygulanamayan bölme",
  },
  TodoAction: {
    add_rule: "Kural ekle",
    upload: "Belge yükle",
    reparse: "Yeniden oku",
    open: "Göster",
    ask_claude: "Claude'a ver",
    ignore: "Yok say",
  },
  SetupStep: {
    data_folder: "Veri klasörü",
    names: "Adınız",
    business_names: "Şirket adları",
    mail: "E-posta",
    senders: "Bankalar ve göndericiler",
    documents: "Eski belgeler",
    notifications: "Bildirimler",
    service: "Servis",
    remote: "Uzaktan erişim",
  },
  MonthStatus: {
    closed: "Kapandı",
    waiting: "Ekstre bekleniyor",
    missing: "Belge eksik",
    check: "Kontrol gerekli",
    running: "Ay sürüyor",
  },
  TransactionKind: {
    purchase: "Harcama",
    refund: "İade / indirim",
    income: "Gelir",
    interest_fee: "Faiz & banka ücreti",
    own_transfer: "Kendi hesapları arası",
    p2p_transfer: "Kişilere gönderilen para",
    loan_principal: "Kredi & borç anapara ödemesi",
    cash_advance: "Nakit avans / çekim",
    card_payment_no_statement: "Ekstresi olmayan kart ödemesi",
  },
  Necessity: { required: "Gerekli", optional: "İsteğe bağlı", unnecessary: "Gereksiz", unknown: "Belirsiz" },
  Tone: { attention: "Dikkat", info: "Bilgi", good: "İyi" },
  HabitStatus: {
    monthly: "Her ay",
    new: "Yeni alışkanlık",
    occasional: "Ara sıra",
    stopped: "Durdu",
    one_off: "Tek seferlik",
  },
  UnusualKind: {
    unusual_amount: "Alışılmadık tutar",
    possible_duplicate: "Olası çift çekim",
    new_large: "Yeni bir yerde büyük tutar",
    unexpected_fee: "Beklenmedik ücret",
  },
  ForecastPart: { regular: "Düzenli ödemeler", installments: "Kalan taksitler", variable: "Değişken harcamalar" },
  CategoryReason: {
    rule: "Kategori kuralı",
    own_transfer: "Kendi hesaplarınız arası",
    user: "Sizin düzeltmeniz",
    split: "Sizin bölmeniz",
  },
  NecessityReason: {
    user: "Sizin düzeltmeniz",
    merchant: "İşyerinin kendi düzeyi",
    category: "Kategorisinin düzeyi",
    default: "Kural yok: belirsiz",
  },
  RuleLayer: { own: "Sizin kurallarınız", shipped: "Hazır kurallar" },
  TransferStep: { paired: "Başka bir hesabınızda karşılığı var" },
  EvidenceStatus: {
    matched: "Ekstreyle eşleşti",
    provisional: "Geçici — ekstre bekleniyor",
    unmatched: "Ekstrede görünmüyor",
  },
  BackupReason: { daily: "Günlük", manual: "Elle", before_restore: "Geri yükleme öncesi" },
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
        sha256: "1".repeat(64),
        certainty: "confirmed",
      },
      {
        fingerprint: "fp-kira-11",
        day: "2026-11-03",
        amount: tl(1500000),
        document: "TEB Dekont 03.11.2026.pdf",
        sha256: "2".repeat(64),
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
      payments: ["08", "09", "10"].map((month) => ({
        fingerprint: `fp-muzik-${month}`,
        day: `2026-${month}-09`,
        amount: tl(9999),
        document: `Kart Ekstresi 2026-${month}.pdf`,
        sha256: month.padStart(64, "3"),
        certainty: "confirmed" as const,
      })),
    }),
    // A bill whose amount moves: the next one is expected at the median of the last three.
    series({
      id: "fp-elektrik",
      payee: "Örnek Elektrik",
      category: "Elektrik, Su & Doğalgaz",
      amount: tl(70000),
      last_day: "2026-10-20",
      last_amount: tl(82000),
      next_day: "2026-11-20",
      price_change: null,
    }),
    // Paid on after the month the user's rules give as its last ("ORNEK VIDEO: 2026-09" in CATEGORY_RULES).
    series({
      id: "fp-video",
      payee: "Örnek Video",
      status: "paid_after_cancel",
      note: "Kişisel kurallarınızda son ödeme ayı Eylül 2026, ama sonrasında da ödendi: aboneliği kontrol edin.",
      category: "Dijital Abonelikler",
      necessity: "optional",
      account: CARD,
      amount: tl(14999),
      last_day: "2026-10-12",
      last_amount: tl(14999),
      next_day: "2026-11-12",
      price_change: null,
      payments: ["09", "10"].map((month) => ({
        fingerprint: `fp-video-${month}`,
        day: `2026-${month}-12`,
        amount: tl(14999),
        document: `Kart Ekstresi 2026-${month}.pdf`,
        sha256: month.padStart(64, "3"),
        certainty: "confirmed" as const,
      })),
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
    // Cancelled by the user ("Örnek Dergi: 2026-08" in CATEGORY_RULES), and no payment since.
    series({
      id: "fp-dergi",
      payee: "Örnek Dergi",
      status: "cancelled",
      note: "Kişisel kurallarınızda son ödeme ayı Ağustos 2026.",
      category: "Dijital Abonelikler",
      necessity: "optional",
      account: CARD,
      amount: tl(5000),
      last_day: "2026-08-15",
      last_amount: tl(5000),
      next_day: null,
      price_change: null,
      payments: [
        {
          fingerprint: "fp-dergi-08",
          day: "2026-08-15",
          amount: tl(5000),
          document: "Kart Ekstresi 2026-08.pdf",
          sha256: "08".padStart(64, "3"),
          certainty: "confirmed",
        },
      ],
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

const TL_ACCOUNT = { id: "teb-1", label: "TEB Vadesiz TL" };
const EUR_ACCOUNT = { id: "garanti-eur", label: "Garanti BBVA Döviz EUR" };
const GOLD_ACCOUNT = { id: "vakif-altin", label: "VakıfBank Altın" };
const CARD_DEBT = { id: "teb-kart", label: "TEB Bonus ••4321" };

export const HOLDINGS: Holdings = {
  today: "2026-11-02",
  worth: {
    total: { minor: 23800000, currency: "TRY" },
    assets: { minor: 25000000, currency: "TRY" },
    debts: { minor: 1200000, currency: "TRY" },
    certainty: "provisional",
    parts: [
      { account: TL_ACCOUNT, value: { minor: 17700000, currency: "TRY" }, certainty: "confirmed" },
      { account: EUR_ACCOUNT, value: { minor: 7300000, currency: "TRY" }, certainty: "confirmed" },
      { account: CARD_DEBT, value: { minor: -1200000, currency: "TRY" }, certainty: "provisional" },
    ],
    left_out: [{ account: { id: "garanti-1", label: "Garanti BBVA Vadesiz TL" }, reason: "bakiyesi hiçbir belgede yazmıyor" }],
    currencies: [
      { currency: "EUR", amount: { minor: 652055, currency: "EUR" }, rate: "36.50", rate_day: "2026-10-30", note: "" },
      { currency: "USD", amount: null, rate: null, rate_day: null, note: "belgelerde USD kuru yok" },
      { currency: "GR", amount: null, rate: null, rate_day: null, note: "gram altının TL fiyatı belgelerde yok" },
    ],
    note: "Hesapların son belgelerindeki bakiyeler; değeri bilinmeyenler toplama girmedi.",
  },
  holdings: [
    {
      account: TL_ACCOUNT,
      group: "current",
      amount: { minor: 17700000, currency: "TRY" },
      value: { minor: 17700000, currency: "TRY" },
      rate: null,
      rate_day: null,
      cost: null,
      gain: null,
      day: "2026-10-31",
      certainty: "confirmed",
      note: "31.10.2026 dökümünde 177.000,00 TL",
    },
    {
      account: EUR_ACCOUNT,
      group: "fx",
      amount: { minor: 200000, currency: "EUR" },
      value: { minor: 7300000, currency: "TRY" },
      rate: "36.50",
      rate_day: "2026-10-30",
      cost: { minor: 7000000, currency: "TRY" },
      gain: { minor: 300000, currency: "TRY" },
      day: "2026-10-30",
      certainty: "confirmed",
      note: "30.10.2026 dökümünde 2.000,00 EUR",
    },
    {
      account: GOLD_ACCOUNT,
      group: "gold",
      amount: { minor: 1250, currency: "GR" },
      value: null,
      rate: null,
      rate_day: null,
      cost: null,
      gain: null,
      day: "2026-10-28",
      certainty: "confirmed",
      note: "28.10.2026 cüzdanında 12,50 gr",
    },
    {
      account: CARD_DEBT,
      group: "cards",
      amount: { minor: -1200000, currency: "TRY" },
      value: { minor: -1200000, currency: "TRY" },
      rate: null,
      rate_day: null,
      cost: null,
      gain: null,
      day: "2026-10-18",
      certainty: "provisional",
      note: "son ekstrenin borcu, kesimden sonraki ödemeler düşülerek",
    },
  ],
  spread: [
    {
      currency: "TRY",
      amount: { minor: 17700000, currency: "TRY" },
      value: { minor: 17700000, currency: "TRY" },
      share: 0.708,
      accounts: [TL_ACCOUNT],
    },
    {
      currency: "EUR",
      amount: { minor: 200000, currency: "EUR" },
      value: { minor: 7300000, currency: "TRY" },
      share: 0.292,
      accounts: [EUR_ACCOUNT],
    },
    { currency: "GR", amount: { minor: 1250, currency: "GR" }, value: null, share: null, accounts: [GOLD_ACCOUNT] },
  ],
  note: "Kurlar belgelerdeki döviz işlemlerinden, en yenisiyle; ağdan kur alınmıyor.",
};

export const FX_RATES: FxRates = {
  currencies: [
    {
      currency: "EUR",
      newest: { day: "2026-10-30", rate: "36.50", source: "document" },
      history: [
        { day: "2026-09-15", rate: "35.8012", source: "document" },
        { day: "2026-10-30", rate: "36.50", source: "document" },
      ],
    },
  ],
  missing: ["GR"],
  note: "Kurlar bankaların belgelerindeki döviz alım-satım satırlarından. TCMB ve ECB kurları henüz alınmıyor.",
};

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
    split_of: "",
    split_parts: 0,
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

export function accountItem(overrides: Partial<AccountItem> = {}): AccountItem {
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
    freshness: {
      account: CASH,
      kind: "account_statement",
      document: "a".repeat(64),
      name: "Örnek Vadesiz TL Ekim 2026",
      last: "2026-10-31",
      behind: 15,
      expected: null,
      late: false,
      missing: [],
      note: "son döküm 31.10.2026",
      link: { screen: "account", id: CASH.id, query: {} },
    },
    month: { month: "2026-11", money_in: tl(0), money_out: tl(150000), rows: 2, provisional: 2, note: "" },
    closed: false,
    link: { screen: "account", id: CASH.id, query: {} },
    ...overrides,
  };
}

const CLOSED = { id: "ornek-999", label: "Örnek Eski Hesap" };

// A card in debt, a TL account moved by receipts since its statement, one no document gives a balance for, a euro
// account valued at the documents' rate, and an account whose documents stopped long ago.
export const ACCOUNTS: Accounts = {
  today: "2026-11-15",
  groups: [
    {
      group: "cards",
      assets: tl(0),
      debts: tl(700000),
      total: tl(-700000),
      unvalued: 0,
      accounts: [
        accountItem({
          account: CARD,
          label: CARD.label,
          type: "credit_card",
          group: "cards",
          balance: tl(-700000),
          value: tl(-700000),
          day: "2026-11-15",
          certainty: "confirmed",
          freshness: null,
          month: { month: "2026-11", money_in: tl(200000), money_out: tl(320000), rows: 6, provisional: 0, note: "" },
          link: { screen: "account", id: CARD.id, query: {} },
        }),
      ],
    },
    {
      group: "current",
      assets: tl(100000),
      debts: tl(0),
      total: tl(100000),
      unvalued: 1,
      accounts: [
        accountItem(),
        accountItem({
          account: UNKNOWN,
          label: UNKNOWN.label,
          bank: "Garanti BBVA",
          balance: null,
          value: null,
          day: null,
          certainty: null,
          note: "Bakiyesi hiçbir belgede yazmıyor.",
          freshness: null,
          month: { month: "2026-11", money_in: tl(0), money_out: tl(0), rows: 0, provisional: 0, note: "" },
          link: { screen: "account", id: UNKNOWN.id, query: {} },
        }),
      ],
    },
    {
      group: "fx",
      assets: tl(1850000),
      debts: tl(0),
      total: tl(1850000),
      unvalued: 0,
      accounts: [
        accountItem({
          account: FX,
          label: FX.label,
          type: "fx",
          group: "fx",
          balance: { minor: 50000, currency: "EUR" },
          value: tl(1850000),
          certainty: "confirmed",
          freshness: null,
          month: { month: "2026-11", money_in: tl(0), money_out: tl(0), rows: 0, provisional: 0, note: "" },
          link: { screen: "account", id: FX.id, query: {} },
        }),
      ],
    },
  ],
  closed: [
    accountItem({
      account: CLOSED,
      label: CLOSED.label,
      value: null,
      balance: tl(0),
      day: "2026-02-28",
      certainty: "confirmed",
      freshness: null,
      month: { month: "2026-11", money_in: tl(0), money_out: tl(0), rows: 0, provisional: 0, note: "" },
      closed: true,
      link: { screen: "account", id: CLOSED.id, query: {} },
    }),
  ],
  assets: tl(1950000),
  debts: tl(700000),
  total: tl(1250000),
  note: "",
};

/** What the last analysis wrote: the report and the rows; the month-end pages wait for a closed month. */
export const EXPORTS: ExportItem[] = [
  { kind: "report", name: "iplikci-rapor-2026-11-15.html", size: 412_000, made_at: "2026-11-15T06:00:00+00:00" },
  { kind: "csv", name: "iplikci-islemler-2026-11-15.csv", size: 18_500, made_at: "2026-11-15T06:00:00+00:00" },
  { kind: "xlsx", name: "iplikci-islemler-2026-11-15.xlsx", size: 52_300, made_at: "2026-11-15T06:00:00+00:00" },
];

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

export const EXTENSION_FOLDER = "/Users/deneme/Library/Application Support/iplikci/extension";
export const EXTENSION: ExtensionInfo = { available: true, version: "0.4.0", folder: "", current: false };

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

// --- the dashboard (F06) ----------------------------------------------------------------------------------------------

function closing(month: string, status: MonthClosing["status"], overrides: Partial<MonthClosing> = {}): MonthClosing {
  return {
    month,
    status,
    summary: "Bütün hesapların belgeleri ayın tamamını kapsıyor ve tutarlı.",
    expense: tl(1997799),
    income: tl(4000000),
    left: tl(2002201),
    provisional: 0,
    unmatched: 0,
    waiting: [],
    link: { screen: "month", id: month, query: {} },
    ...overrides,
  };
}

// On 15 November: a provisional net worth with one account left out, the month's pace, a card's due date within the
// week, a critical and a plain alert, seven months of closing with July missing a document, three accounts' freshness
// and three things to see to.
export const DASHBOARD: Dashboard = {
  today: "2026-11-15",
  as_of: "2026-10-31",
  net_worth: {
    total: tl(1250000),
    assets: tl(1950000),
    debts: tl(700000),
    certainty: "provisional",
    parts: [
      { account: FX, value: tl(1850000), certainty: "confirmed" },
      { account: CARD, value: tl(-700000), certainty: "provisional" },
      { account: CASH, value: tl(100000), certainty: "provisional" },
    ],
    left_out: [{ account: UNKNOWN, reason: "bakiyesi hiçbir belgede yazmıyor" }],
    currencies: [
      {
        currency: "EUR",
        amount: { minor: 33784, currency: "EUR" },
        rate: "37.0000",
        rate_day: "2026-10-31",
        note: "31.10.2026 belgesindeki kurla",
      },
      { currency: "USD", amount: null, rate: null, rate_day: null, note: "belgelerde USD kuru yok" },
      { currency: "GR", amount: null, rate: null, rate_day: null, note: "gram altının TL fiyatı belgelerde yok" },
    ],
    note: "Hesapların son belgelerindeki bakiyeler, sonraki dekont ve bildirimlerle. Değeri bilinmeyenler toplama girmedi.",
    say: "Net varlığınız 12.500,00 TL (geçici); 1 hesabın TL değeri bilinmediği için toplama girmedi.",
    link: { screen: "accounts", id: "", query: {} },
  },
  month: {
    pace: NOW.pace,
    say: "Gelen belgelere göre bu ay 4.200,00 TL harcandı (1.200,00 TL geçici); tipik ayın aynı günlerinden (9.800,00 TL) %57 az.",
    link: { screen: "month", id: "2026-11", query: {} },
  },
  due: {
    items: [
      item({
        day: "2026-11-20",
        kind: "card_due",
        title: "Örnek Kart •1234",
        account: CARD,
        amount: tl(900000),
        minimum: tl(180000),
        basis: "ekstrenin dönem borcu 9.000,00 TL, asgari ödeme 1.800,00 TL",
        series: "",
        fingerprints: [],
      }),
    ],
    total: tl(900000),
    end: "2026-11-21",
    say: "Önümüzdeki 7 günde 1 ödeme var, toplam 9.000,00 TL; ilki 20.11.2026: Örnek Kart •1234.",
    link: { screen: "calendar", id: "", query: {} },
  },
  alerts: {
    items: [
      {
        kind: "negative",
        level: "critical",
        title: "Hesap eksiye düşecek",
        text: "Örnek Vadesiz TL: öngörüye göre bakiye 03.12.2026 günü (18 gün sonra) −14.019,00 TL olacak.",
        count: 1,
        account: CASH,
        link: { screen: "forecast", id: CASH.id, query: {} },
      },
      {
        kind: "unreadable",
        level: "warning",
        title: "Okunamayan belgeler",
        text: "2 belge olduğu gibi okunamadı: şifreli ya da bozuk olabilir. Belgeler ekranında nedenleri var.",
        count: 2,
        account: null,
        link: { screen: "documents", id: "", query: { status: "unreadable" } },
      },
    ],
    say: "2 açık uyarı var, 1 tanesi kritik; ilki: Hesap eksiye düşecek.",
    link: { screen: "notifications", id: "", query: {} },
  },
  closing: {
    months: [
      closing("2026-05", "closed"),
      closing("2026-06", "closed"),
      closing("2026-07", "missing", {
        summary: "Kapanması için eksik belge var: Örnek Vadesiz TL (1–4 Temmuz hesap dökümü eksik).",
        expense: tl(903999),
        income: tl(0),
        left: tl(-903999),
        waiting: [{ account: CASH, waiting_for: "1–4 Temmuz hesap dökümü eksik" }],
      }),
      closing("2026-08", "closed"),
      closing("2026-09", "closed"),
      closing("2026-10", "closed"),
      closing("2026-11", "running", {
        summary: "Rakamlar şimdiye kadar gelen ekstre ve dökümlerden.",
        expense: tl(420000),
        income: null,
        left: null,
        provisional: 2,
      }),
    ],
    say: "Temmuz 2026'da belge eksik; diğer 5 ay kapandı.",
    link: { screen: "month", id: "2026-07", query: {} },
  },
  freshness: {
    accounts: [
      {
        account: UNKNOWN,
        kind: "receipt",
        document: "f".repeat(64),
        name: "Garanti Giden Havale Dekontu 10.09.2026.pdf",
        last: "2026-09-10",
        behind: 66,
        expected: null,
        late: false,
        missing: [],
        note: "yalnızca dekont ve banka bildirimlerinden biliniyor",
        link: { screen: "account", id: UNKNOWN.id, query: {} },
      },
      {
        account: CARD,
        kind: "card_statement",
        document: "e".repeat(64),
        name: "Örnek Kart Ekstresi Ekim 2026.pdf",
        last: "2026-10-28",
        behind: 18,
        expected: "2026-11-28",
        late: false,
        missing: [],
        note: "son ekstre 28.10.2026; sonraki ~28.11.2026",
        link: { screen: "account", id: CARD.id, query: {} },
      },
      {
        account: CASH,
        kind: "account_statement",
        document: "a".repeat(64),
        name: "TEB Hesap Dökümü Ekim 2026",
        last: "2026-10-31",
        behind: 15,
        expected: null,
        late: false,
        missing: ["2026-07"],
        note: "son döküm 31.10.2026",
        link: { screen: "account", id: CASH.id, query: {} },
      },
    ],
    say: "Geciken ekstre yok; en geride kalan Garanti Vadesiz TL, belgeleri 10.09.2026 tarihine kadar.",
    link: { screen: "accounts", id: "", query: {} },
  },
  todo: {
    kinds: [
      { kind: "missing_documents", count: 1, link: { screen: "todo", id: "missing_documents", query: {} } },
      { kind: "unprocessed_document", count: 2, link: { screen: "todo", id: "unprocessed_document", query: {} } },
    ],
    total: 3,
    say: "3 iş bekliyor: Eksik belge (1), İşlenmeyen belge (2).",
    link: { screen: "todo", id: "", query: {} },
  },
};

// --- the Değerlendirme screen (F10) ---------------------------------------------------------------------------------

/** A month table's row: its values in kuruş, one per slice. */
function monthRow(month: string, values: number[], partial = false) {
  return { month, values: values.map(tl), partial };
}

const rowsOf = (query: Record<string, string>) => ({ screen: "transactions" as const, id: "", query });
const SIX = ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"];
const WHOLE_MONTHS = SIX.filter((month) => month !== "2026-07");
const AHEAD = ["2026-11", "2026-12", "2027-01"];
// The spending by necessity level, July covered only partly: the same months for the period and the forecast.
const LEVEL_MONTHS = [
  monthRow("2026-05", [1800000, 199000, 1000]),
  monthRow("2026-06", [1800000, 199000, 1000]),
  monthRow("2026-07", [100000, 850000, 0], true),
  monthRow("2026-08", [1800000, 199000, 1000]),
  monthRow("2026-09", [1800000, 199000, 1000]),
  monthRow("2026-10", [1900000, 216000, 4000]),
];
const LEVELS = [
  { key: "required", slot: 1 },
  { key: "optional", slot: 4 },
  { key: "unnecessary", slot: 5 },
];

function flowMonth(month: string, income: number, expense: number, rest: { people?: number; debt?: number } = {}) {
  const people = rest.people ?? 0;
  const debt = rest.debt ?? 0;
  return {
    month,
    partial: month === "2026-07",
    income: tl(income),
    expense: tl(expense),
    net: tl(income - expense),
    people: tl(people),
    debt: tl(debt),
    saving: tl(0),
    left: tl(income - expense - people - debt),
  };
}

// May to October 2026 with July covered only partly: 110.700,00 TL over 60 rows, 20.240,00 TL a whole month; the
// income known from account lists; four categories and merchants; a forecast whose two market lines share a payee.
export const SPENDING: Spending = {
  period: { start: "2026-05", end: "2026-10", first: "2026-01", last: "2026-10" },
  tiles: {
    total: tl(11070000),
    count: 60,
    average: tl(2024000),
    average_months: 5,
    partial_months: 1,
    income_average: tl(4000000),
    income_months: 5,
    income_share: "0.506",
    unnecessary: tl(8000),
    last_month: "2026-10",
    last_total: tl(2120000),
    last_partial: false,
    last_change: "0.06",
    last_base_months: 3,
  },
  by_group: {
    slices: [
      { key: "Yeme & İçme", slot: 1 },
      { key: "Ev & Faturalar", slot: 3 },
      { key: "Alışveriş", slot: 5 },
    ],
    months: [
      monthRow("2026-05", [400000, 1600000, 0]),
      monthRow("2026-06", [420000, 1580000, 0]),
      monthRow("2026-07", [100000, 0, 850000], true),
      monthRow("2026-08", [400000, 1600000, 0]),
      monthRow("2026-09", [380000, 1620000, 0]),
      monthRow("2026-10", [410000, 1610000, 100000]),
    ],
  },
  by_level: { slices: LEVELS, months: LEVEL_MONTHS },
  categories: [
    { category: "Kira", group: "Ev & Faturalar", slot: 3, total: tl(7500000), share: "0.6775", count: 5 },
    { category: "Market & Gıda", group: "Yeme & İçme", slot: 1, total: tl(2110000), share: "0.1906", count: 40 },
    { category: "Elektronik", group: "Alışveriş", slot: 5, total: tl(950000), share: "0.0858", count: 2 },
    { category: "Elektrik", group: "Ev & Faturalar", slot: 3, total: tl(510000), share: "0.0461", count: 5 },
  ].map((line) => ({
    ...line,
    average: tl(Math.round(line.total.minor / 5)),
    link: rowsOf({ category: line.category }),
  })),
  merchants: [
    ["Ev Sahibi Örnek", "Kira", "Ev & Faturalar", 3, 5, 7500000, "2026-10-03"],
    ["Örnek Market", "Market & Gıda", "Yeme & İçme", 1, 40, 2110000, "2026-10-28"],
    ["Örnek Teknoloji", "Elektronik", "Alışveriş", 5, 2, 950000, "2026-10-12"],
    ["Örnek Elektrik", "Elektrik", "Ev & Faturalar", 3, 5, 510000, "2026-10-20"],
  ].map(([merchant, category, group, slot, count, total, last]) => ({
    merchant: String(merchant),
    category: String(category),
    group: String(group),
    slot: Number(slot),
    count: Number(count),
    last: String(last),
    total: tl(Number(total)),
    per_row: tl(Math.round(Number(total) / Number(count))),
    link: rowsOf({ merchant: String(merchant) }),
  })),
  flow: [
    flowMonth("2026-05", 4000000, 2000000),
    flowMonth("2026-06", 4000000, 2000000, { people: 50000 }),
    flowMonth("2026-07", 0, 950000),
    flowMonth("2026-08", 4000000, 2000000),
    flowMonth("2026-09", 4000000, 2000000, { debt: 100000 }),
    flowMonth("2026-10", 4000000, 2120000),
  ],
  forecast: {
    base: WHOLE_MONTHS,
    months: AHEAD,
    lines: [
      ["regular", "Ev kirası", "Kira · son ödeme 03.10.2026", "required", "Ev & Faturalar", 3, 1500000],
      ["regular", "Örnek Market", "Market & Gıda · son ödeme 12.10.2026", "required", "Yeme & İçme", 1, 200000],
      ["regular", "Örnek Market", "Market & Gıda · son ödeme 28.10.2026", "required", "Yeme & İçme", 1, 180000],
      ["installments", "Örnek Elektronik", "Örnek Kart •1234 · 12 taksit", "optional", "Alışveriş", 5, 50000],
      ["variable", "Gereksiz", "aylık 10,00 TL ile 40,00 TL arasında", "unnecessary", "", 5, 1000],
    ].map(([part, label, note, necessity, group, slot, amount]) => ({
      part: part as "regular" | "installments" | "variable",
      label: String(label),
      note: String(note),
      necessity: necessity as "required" | "optional" | "unnecessary",
      group: String(group),
      slot: Number(slot),
      amounts: AHEAD.map(() => tl(Number(amount))),
      link: group ? rowsOf({ merchant: String(label) }) : rowsOf({ necessity: String(necessity) }),
    })),
    totals: AHEAD.map(() => tl(1931000)),
    by_level: { slices: LEVELS, months: AHEAD.map((month) => monthRow(month, [1880000, 50000, 1000])) },
    actual: { slices: LEVELS, months: LEVEL_MONTHS },
    income: tl(4000000),
    income_names: ["Örnek İşveren A.Ş."],
    saving: tl(0),
    saving_names: [],
    other: tl(25000),
    left: tl(2044000),
  },
};

const DUPLICATE = "c2c2c2c2c2c2c2c2c2c2";
const LARGE_ROW = "b1b1b1b1b1b1b1b1b1b1";

// The interpretation over the five whole months: two highlights (one about the whole picture), a priced and an unpriced
// step, a short budget, three habits (one a one-off), the trend with a large purchase, and a possible double charge.
export const INSIGHTS: Insights = {
  window: { months: WHOLE_MONTHS, as_of: "2026-10-31", last_complete: "2026-10" },
  findings: [
    {
      tone: "attention",
      title: "Faiz ve banka ücretleri",
      text: "5 ayda 80 TL, ayda 16 TL: Kart ücretleri 80 TL. Borç zamanında ve tam ödenince bunların hepsi sıfırlanır.",
      link: rowsOf({ kind: "interest_fee" }),
    },
    {
      tone: "good",
      title: "Gelir ve gider dengesi",
      text: "Mayıs 2026 – Ekim 2026 arasındaki 5 tam ayda ortalama gelir 40.000 TL, gider 20.240 TL (gelirin %51'i).",
      link: { screen: "insights", id: "", query: {} },
    },
  ],
  steps: [
    {
      title: "Abonelikleri gözden geçirin",
      text: "İsteğe bağlı abonelikler ayda 100 TL: Örnek Müzik 100 TL. Kullanmadığınızı iptal edin.",
      monthly: tl(9999),
    },
    {
      title: "Acil durum fonu",
      text: "Zorunlu giderler ayda yaklaşık 18.800 TL; 3 aylık tampon 56.400 TL eder.",
      monthly: null,
    },
  ],
  budget: [
    { label: "Düzenli gelir", now: tl(4000000), plan: tl(4000000), note: "son maaş (Örnek İşveren A.Ş.)" },
    { label: "Sabit ödemeler", now: tl(1880000), plan: tl(1880000), note: "4 düzenli ödeme, son tutarlarıyla" },
    { label: "Faiz ve banka ücretleri", now: tl(1600), plan: tl(0), note: "öneri: borcu tam ödeyerek sıfırlayın" },
    { label: "Ay sonunda kalan", now: tl(2118400), plan: tl(2120000), note: "birikime ve acil durum fonuna" },
  ],
  habits: [
    {
      name: "Kart ücretleri",
      category: "Kart ücretleri",
      necessity: "unnecessary",
      by_category: true,
      status: "monthly",
      pattern: "5 ayın 5 ayında, 5 işlem",
      count: 5,
      months: 5,
      span: 5,
      total: tl(8000),
      recent: tl(1600),
      monthly: tl(1600),
      last: "2026-10-05",
      link: rowsOf({ category: "Kart ücretleri" }),
    },
    {
      name: "Örnek Kahve",
      category: "Kafe & Kahve",
      necessity: "optional",
      by_category: false,
      status: "occasional",
      pattern: "5 ayın 3 ayında, 4 işlem",
      count: 4,
      months: 3,
      span: 5,
      total: tl(60000),
      recent: tl(10000),
      monthly: tl(12000),
      last: "2026-10-18",
      link: rowsOf({ merchant: "Örnek Kahve" }),
    },
    {
      name: "Örnek Teknoloji",
      category: "Elektronik",
      necessity: "optional",
      by_category: false,
      status: "one_off",
      pattern: "1 alışveriş, 15.07.2026",
      count: 1,
      months: 1,
      span: 5,
      total: tl(850000),
      recent: tl(0),
      monthly: tl(0),
      last: "2026-07-15",
      link: rowsOf({ merchant: "Örnek Teknoloji" }),
    },
  ],
  flow: {
    months: WHOLE_MONTHS,
    income: tl(4000000),
    expense: tl(2024000),
    people: tl(10000),
    unnamed_people: tl(0),
    debt: tl(20000),
    saving: tl(0),
    fx: tl(0),
    left: tl(1946000),
    debt_start: tl(0),
    debt_end: tl(0),
    other_typical: tl(25000),
  },
  trend: {
    before: ["2026-05", "2026-06"],
    recent: ["2026-08", "2026-09", "2026-10"],
    before_average: tl(2000000),
    recent_average: tl(2040000),
    usual_before: tl(2000000),
    usual_recent: tl(1823333),
    changes: [
      { category: "Kira", before: tl(1500000), recent: tl(1500000) },
      { category: "Market & Gıda", before: tl(410000), recent: tl(396667) },
      { category: "Elektrik", before: tl(90000), recent: tl(104000) },
    ],
    large: [
      row({
        fingerprint: LARGE_ROW,
        day: "2026-09-21",
        title: "Örnek Mobilya",
        merchant: "Örnek Mobilya",
        amount: tl(650000),
        category: "Mobilya",
        certainty: "confirmed",
      }),
    ],
    threshold: tl(500000),
  },
  income: [{ name: "Örnek İşveren A.Ş.", monthly: tl(4000000), last: "2026-10-01", status: "active" }],
  unusual: [
    {
      kind: "possible_duplicate",
      row: row({
        fingerprint: DUPLICATE,
        day: "2026-10-14",
        title: "Örnek Kafe",
        merchant: "Örnek Kafe",
        amount: tl(9000),
      }),
      text: "Aynı gün aynı tutarda iki çekim: 14.10.2026, 90,00 TL. Biri iade edilmediyse bankaya sorun.",
      link: { screen: "transaction", id: DUPLICATE, query: {} },
    },
  ],
};

// --- the Transactions screen (F04) ----------------------------------------------------------------------------------

export const STATEMENT = "d".repeat(64); // a card statement, a PDF
export const RECEIPT = "f".repeat(64); // a receipt, an e-mail

// A purchase the statement shows, an income, a receipt's row the statements leave out, and a market receipt split in
// two: 93 rows in all, 50 a page.
export const PURCHASE = row({
  fingerprint: "a1a1a1a1a1a1a1a1a1a1",
  day: "2026-11-12",
  title: "Örnek Market",
  description: "ORNEK MARKET KADIKOY",
  merchant: "Örnek Market",
  amount: tl(84050),
  category: "Market",
  group: "Gıda",
  necessity: "required",
  certainty: "confirmed",
  note: "haftalık alışveriş",
  tags: ["ev"],
  document: STATEMENT,
});
export const INCOME = row({
  fingerprint: "b2b2b2b2b2b2b2b2b2b2",
  day: "2026-11-05",
  account: CASH,
  title: "Örnek İşveren A.Ş.",
  description: "MAAS ODEMESI ORNEK ISVEREN",
  merchant: "",
  counterparty: "Örnek İşveren A.Ş.",
  amount: tl(4000000),
  direction: "in",
  kind: "income",
  category: "Maaş",
  group: "Gelir",
  necessity: null,
  expense: false,
  certainty: "confirmed",
  document: "a".repeat(64),
});
export const EXCLUDED = row({
  fingerprint: "c3c3c3c3c3c3c3c3c3c3",
  day: "2026-11-03",
  title: "Örnek Kafe",
  description: "ORNEK KAFE",
  merchant: "Örnek Kafe",
  amount: tl(9000),
  category: "Kafe",
  group: "Yeme içme",
  counted: false,
  expense: false,
  certainty: "excluded",
  document: RECEIPT,
});
const WHOLE = "e4e4e4e4e4e4e4e4e4e4"; // the split row's own fingerprint
export const PARTS = [
  row({
    fingerprint: `${WHOLE}-1`,
    day: "2026-11-01",
    title: "Örnek Süpermarket",
    description: "ORNEK SUPERMARKET",
    merchant: "Örnek Süpermarket",
    amount: tl(100000),
    category: "Market",
    group: "Gıda",
    necessity: "required",
    certainty: "confirmed",
    split_of: WHOLE,
    split_parts: 2,
    document: STATEMENT,
  }),
  row({
    fingerprint: `${WHOLE}-2`,
    day: "2026-11-01",
    title: "Örnek Süpermarket",
    description: "ORNEK SUPERMARKET",
    merchant: "Örnek Süpermarket",
    amount: tl(25000),
    category: "Temizlik",
    group: "Ev",
    necessity: "required",
    certainty: "confirmed",
    split_of: WHOLE,
    split_parts: 2,
    document: STATEMENT,
  }),
];

export const TRANSACTIONS: TransactionPage = {
  rows: [PURCHASE, INCOME, EXCLUDED, ...PARTS],
  totals: {
    count: 93,
    counted: 92,
    spent: tl(1525000),
    money_out: tl(1525000),
    money_in: tl(4000000),
    provisional: 4,
    excluded: 1,
  },
  offset: 0,
  next: 50,
};

export const NEXT_TRANSACTIONS: TransactionPage = {
  rows: [row({ fingerprint: "f5f5f5f5f5f5f5f5f5f5", day: "2026-09-02", title: "Örnek Kitapçı", certainty: "confirmed" })],
  totals: TRANSACTIONS.totals,
  offset: 50,
  next: null,
};

export function category(name: string, group: string, slot: number, overrides: Partial<Category> = {}): Category {
  return { name, group, slot, necessity: "optional", regular: false, own: false, ...overrides };
}

export const CATEGORY_RULES: CategoryRules = {
  content: "",
  categories: [
    category("Market", "Gıda", 1, { necessity: "required" }),
    category("Kafe", "Yeme içme", 2),
    category("Elektronik", "Alışveriş", 3),
    category("Temizlik", "Ev", 4, { necessity: "required" }),
    category("Maaş", "Gelir", 5, { necessity: null }),
  ],
  // The user's own, written as they like: the service finds a payee by its folded name ("Örnek Video").
  ended: [
    { merchant: "ORNEK VIDEO", month: "2026-09", own: true },
    { merchant: "Örnek Dergi", month: "2026-08", own: true },
  ],
  merchant_necessity: [],
  history: [],
};

/** A document's place with no page, line, sheet or row: a receipt or a notice found as a whole. */
export const NOWHERE = { page: null, line: null, sheet: null, row: null } as const;

export function transactionDetail(overrides: Partial<TransactionDetail> = {}): TransactionDetail {
  return {
    row: PURCHASE,
    printed: {
      document: STATEMENT,
      name: "Örnek Kart Ekstresi Kasım 2026",
      kind: "card_statement",
      page: 2,
      line: 14,
      sheet: null,
      row: null,
    },
    why: {
      category: "rule",
      rule: "ORNEK MARKET",
      layer: "shipped",
      necessity: "category",
      necessity_layer: "shipped",
      transfer: null,
      pair: null,
      rate: null,
      rate_day: null,
    },
    told: [
      {
        fingerprint: "a9a9a9a9a9a9a9a9a9a9",
        status: "matched",
        day: "2026-11-12",
        amount: tl(84050),
        printed: { ...NOWHERE, document: RECEIPT, name: "Örnek Banka dekontu", kind: "receipt" },
      },
    ],
    bill: null,
    annotation: {
      note: "haftalık alışveriş",
      tags: ["ev"],
      category: "",
      necessity: null,
      parts: [],
      updated_at: "2026-11-13T09:00:00+00:00",
    },
    correctable: true,
    parts: [],
    splittable: true,
    split_dropped: false,
    ...overrides,
  };
}

/** The split row's detail: the whole row, with the category it had before, and its parts in order. */
export const SPLIT_DETAIL = transactionDetail({
  row: { ...PARTS[0]!, fingerprint: WHOLE, amount: tl(125000), category: "Market", split_of: "", split_parts: 2 },
  why: { ...transactionDetail().why, rule: "ORNEK SUPERMARKET" },
  told: [],
  annotation: {
    note: "",
    tags: [],
    category: "",
    necessity: null,
    parts: [
      { minor: 100000, category: "Market", necessity: null },
      { minor: 25000, category: "Temizlik", necessity: null },
    ],
    updated_at: "2026-11-02T09:00:00+00:00",
  },
  parts: PARTS,
});

export const PAGE_SIZES = [
  { width: 595, height: 842 },
  { width: 595, height: 842 },
];

// The statement's second page as text, line by line: line 14 is the purchase's.
export const STATEMENT_LINES = Array.from({ length: 20 }, (_, index) =>
  index === 13 ? "12.11.2026 ORNEK MARKET KADIKOY 840,50" : `Satır ${index + 1}`,
);

export const STATEMENT_VIEW: DocumentView = {
  kind: "pdf",
  pages: PAGE_SIZES,
  table: null,
  mail: null,
  text: "",
  has_html: false,
};

export const STATEMENT_DETAIL: DocumentDetail = {
  document: {
    sha256: STATEMENT,
    name: "Örnek Kart Ekstresi Kasım 2026",
    file: "ekstre.pdf",
    kind: "card_statement",
    parser: "ornek.card_pdf",
    reader: "Örnek kart ekstresi",
    status: "processed",
    reason: "",
    verified: true,
    period_start: "2026-10-16",
    period_end: "2026-11-15",
    sources: ["email"],
    added_at: "2026-11-16T08:00:00+00:00",
    size: 81920,
    accounts: [{ id: CARD.id, label: CARD.label, bank: "TEB" }],
  },
  parser_version: "1.0",
  view: "pdf",
  arrivals: [],
  checks: [],
  rows: [
    {
      fingerprint: PURCHASE.fingerprint,
      day: PURCHASE.day,
      description: PURCHASE.description,
      amount: PURCHASE.amount,
      kind: "purchase",
      account: CARD.label, // the account as the screens name it
      category: "Market",
      provisional: false,
      counted: true,
      evidence: "matched",
      ref: { page: 2, box: [40, 300, 555, 312], line: 14, sheet: null, row: null, span: null },
    },
  ],
  more_rows: false,
  parent: "",
  attachments: [],
};

// --- the Belgeler screens (F03) -------------------------------------------------------------------------------------

export const ACCOUNT_LIST = "a".repeat(64); // FIRST_PAGE's account list, a sheet
export const LOCKED = "b".repeat(64); // FIRST_PAGE's encrypted PDF, which no reader could open

/** The account list's sheet as the viewer shows it: row 3 is the salary's. */
export const LIST_VIEW: DocumentView = {
  kind: "table",
  pages: [],
  table: {
    name: "Hesap Hareketleri",
    rows: [
      ["Tarih", "Açıklama", "Tutar", "Bakiye"],
      ["01.02.2026", "DEVIR", "", "1.000,00"],
      ["05.02.2026", "MAAS ODEMESI ORNEK ISVEREN", "40.000,00", "41.000,00"],
    ],
    more: false,
  },
  mail: null,
  text: "",
  has_html: false,
};

export const LIST_DETAIL: DocumentDetail = {
  document: FIRST_PAGE.items[0]!,
  parser_version: "2.1",
  view: "table",
  arrivals: [
    {
      kind: "upload",
      name: "subat.xls",
      origin: "",
      sender: "",
      subject: "",
      sent_at: "",
      received_at: "2026-11-01T07:31:00+00:00",
      gmail: "",
    },
  ],
  checks: [
    {
      account: "TEB Vadesiz TL 123456789",
      start: "2026-02-01",
      cut: "2026-02-28",
      printed: tl(4100000),
      counted: tl(4100000),
      verified: true,
      balance_checks: [12, 12],
      rows: 12,
    },
  ],
  rows: [
    {
      fingerprint: INCOME.fingerprint,
      day: "2026-02-05",
      description: INCOME.description,
      amount: tl(-4000000),
      kind: "income",
      account: "TEB Vadesiz TL 123456789",
      category: "Maaş",
      provisional: false,
      counted: true,
      evidence: null,
      ref: { page: null, box: null, line: null, sheet: "Hesap Hareketleri", row: 3, span: null },
    },
  ],
  more_rows: false,
  parent: "",
  attachments: [],
};

// The receipt as an e-mail: its body as a browser breaks it, the same text collapsed (a row's span counts in it) and
// an HTML part shown only in a sandbox.
const RECEIPT_TEXT = "Sayın Müşterimiz, 03.11.2026 tarihli işleminiz: ORNEK KAFE 90,00 TL. Bilgilerinize sunarız.";
const KAFE = RECEIPT_TEXT.indexOf("ORNEK KAFE 90,00 TL");

export const RECEIPT_VIEW: DocumentView = {
  kind: "mail",
  pages: [],
  table: null,
  mail: {
    subject: "İşlem bildirimi",
    sender: "ornekbanka.example",
    sent: "2026-11-03T06:15:00+00:00",
    lines: ["Sayın Müşterimiz,", "03.11.2026 tarihli işleminiz: ORNEK KAFE 90,00 TL.", "Bilgilerinize sunarız."],
    text: RECEIPT_TEXT,
  },
  text: "",
  has_html: true,
};

export const RECEIPT_DETAIL: DocumentDetail = {
  document: {
    sha256: RECEIPT,
    name: "Örnek Banka dekontu",
    file: "dekont.eml",
    kind: "receipt",
    parser: "ornek.receipt_mail",
    reader: "Örnek banka dekontu",
    status: "processed",
    reason: "",
    verified: null,
    period_start: "2026-11-03",
    period_end: "2026-11-03",
    sources: ["email"],
    added_at: "2026-11-03T06:20:00+00:00",
    size: 6144,
    accounts: [{ id: CARD.id, label: CARD.label, bank: "Örnek Bank" }],
  },
  parser_version: "1.2",
  view: "mail",
  arrivals: [
    {
      kind: "email",
      name: "dekont.eml",
      origin: "INBOX",
      sender: "bildirim@ornekbanka.example",
      subject: "İşlem bildirimi",
      sent_at: "2026-11-03T06:15:00+00:00",
      received_at: "2026-11-03T06:20:00+00:00",
      gmail: "https://mail.google.com/mail/u/0/#search/rfc822msgid%3Aornek-1%40ornekbanka.example",
    },
  ],
  checks: [],
  rows: [
    {
      fingerprint: EXCLUDED.fingerprint,
      day: "2026-11-03",
      description: "ORNEK KAFE",
      amount: tl(9000),
      kind: "purchase",
      account: CARD.label,
      category: "Kafe",
      provisional: false,
      counted: false,
      evidence: "unmatched",
      ref: { page: null, box: null, line: null, sheet: null, row: null, span: [KAFE, KAFE + 19] },
    },
  ],
  more_rows: false,
  parent: "",
  attachments: [{ sha256: "9".repeat(64), name: "dekont.pdf" }],
};

export const LOCKED_DETAIL: DocumentDetail = {
  document: FIRST_PAGE.items[1]!,
  parser_version: "",
  view: "pdf",
  arrivals: [],
  checks: [],
  rows: [],
  more_rows: false,
  parent: "",
  attachments: [],
};

const DOCUMENT_DETAILS: Record<string, DocumentDetail> = {
  [STATEMENT]: STATEMENT_DETAIL,
  [ACCOUNT_LIST]: LIST_DETAIL,
  [RECEIPT]: RECEIPT_DETAIL,
  [LOCKED]: LOCKED_DETAIL,
};
const DOCUMENT_VIEWS: Record<string, DocumentView> = {
  [STATEMENT]: STATEMENT_VIEW,
  [ACCOUNT_LIST]: LIST_VIEW,
  [RECEIPT]: RECEIPT_VIEW,
};

// --- the Hesaplar screens (F07) -------------------------------------------------------------------------------------

const MONTHS = ["2025-12", ...Array.from({ length: 11 }, (_, i) => `2026-${String(i + 1).padStart(2, "0")}`)];

/** The TL account's page: its rows, a balance curve with days no document covers, its months, fees and series. */
export function accountPage(overrides: Partial<AccountPage> = {}): AccountPage {
  const cash = ACCOUNTS.groups[1]!.accounts[0]!;
  return {
    account: cash,
    rows: [INCOME, row({ fingerprint: "c7c7c7c7c7c7c7c7c7c7", account: CASH, day: "2026-11-03", title: "Ev kirası" })],
    totals: { count: 2, counted: 2, spent: tl(1250000), money_out: tl(1250000), money_in: tl(4000000), provisional: 1, excluded: 0 },
    offset: 0,
    next: null,
    curve: [
      { day: "2026-10-29", balance: tl(250000), certainty: "confirmed" },
      { day: "2026-10-30", balance: tl(-30000), certainty: "confirmed" },
      { day: "2026-10-31", balance: tl(120000), certainty: "confirmed" },
      { day: "2026-11-04", balance: tl(100000), certainty: "provisional" },
    ],
    curve_note: "Gün sonu bakiyeleri hesap dökümlerinden; son dökümden sonrası bildirim ve dekontlardan.",
    months: MONTHS.map((month) => ({
      month,
      money_in: tl(4000000),
      money_out: tl(month === "2026-10" ? 3500000 : 3000000),
      rows: 12,
      complete: month !== "2026-11",
    })),
    fees: {
      months: MONTHS.slice(0, 11),
      total: tl(11250),
      categories: [
        { category: "Hesap işletim ücreti", amount: tl(9000) },
        { category: "EFT ücreti", amount: tl(2250) },
      ],
    },
    payments: [series()],
    income: [
      series({
        id: "fp-maas",
        payee: "Örnek İşveren A.Ş.",
        category: "Maaş",
        kind: "income",
        necessity: null,
        amount: tl(4000000),
        last_amount: tl(4000000),
        price_change: null,
      }),
    ],
    card: null,
    overdraft: {
      limit: null,
      used: tl(0),
      days_below: 1,
      window_start: "2025-11-15",
      window_end: "2026-11-15",
      interest: tl(1250),
      note: "Limit hiçbir belgede yazmıyor.",
    },
    deposit: null,
    holding: null,
    brokerage: null,
    loan: null,
    ...overrides,
  };
}

/** The card's page: its newest statement, three statements with how each was paid, an installment purchase. */
export const CARD_PAGE: AccountPage = accountPage({
  account: ACCOUNTS.groups[0]!.accounts[0]!,
  rows: [PURCHASE],
  curve: [],
  curve_note: "Günlük bakiye TL vadesiz, vadeli ve ek hesaplar için çizilir.",
  payments: [],
  income: [],
  overdraft: null,
  card: {
    statement: NOW.cards[0]!,
    statements: [
      {
        cut: "2026-10-28",
        start: "2026-09-29",
        end: "2026-10-28",
        total: tl(900000),
        due: "2026-11-25",
        minimum: tl(180000),
        limit: tl(5000000),
        rows: 14,
        spent: tl(900000),
        verified: true,
        document: STATEMENT,
        paid: tl(200000),
        status: "open",
      },
      {
        cut: "2026-09-28",
        start: "2026-08-29",
        end: "2026-09-28",
        total: tl(800000),
        due: "2026-10-25",
        minimum: tl(160000),
        limit: null,
        rows: 11,
        spent: tl(800000),
        verified: true,
        document: STATEMENT,
        paid: tl(160000),
        status: "minimum",
      },
      {
        cut: "2026-08-28",
        start: "2026-07-29",
        end: "2026-08-28",
        total: tl(600000),
        due: "2026-09-25",
        minimum: tl(120000),
        limit: tl(5000000),
        rows: 9,
        spent: tl(600000),
        verified: false,
        document: STATEMENT,
        paid: tl(600000),
        status: "full",
      },
    ],
    installments: [
      {
        card: CARD,
        title: "Örnek Elektronik",
        number: 3,
        count: 6,
        amount: tl(250000),
        left: 3,
        remaining: tl(750000),
        last_day: "2027-01-28",
        fingerprint: "0123456789abcdef0123",
      },
    ],
    schedule: [
      { month: "2026-11", amount: tl(250000), count: 1 },
      { month: "2026-12", amount: tl(250000), count: 1 },
      { month: "2027-01", amount: tl(250000), count: 1 },
    ],
    left: tl(750000),
  },
});

/** The euro account's page: its amount and value at the documents' rate; what it cost is printed nowhere. */
export const FX_PAGE: AccountPage = accountPage({
  account: ACCOUNTS.groups[2]!.accounts[0]!,
  rows: [],
  totals: { count: 0, counted: 0, spent: tl(0), money_out: tl(0), money_in: tl(0), provisional: 0, excluded: 0 },
  curve: [],
  curve_note: "Günlük bakiye TL vadesiz, vadeli ve ek hesaplar için çizilir.",
  months: MONTHS.map((month) => ({ month, money_in: tl(0), money_out: tl(0), rows: 0, complete: true })),
  fees: { months: MONTHS.slice(0, 11), total: tl(0), categories: [] },
  payments: [],
  income: [],
  overdraft: null,
  holding: {
    amount: { minor: 50000, currency: "EUR" },
    value: tl(1850000),
    rate: "37.0000",
    rate_day: "2026-10-31",
    cost: null,
    gain: null,
    note: "Ne kadara alındığı hiçbir belgede yazmıyor.",
  },
});

// January to October 2026: the TL account's lists cover every day but most of July; the card's statements start in
// March, the first of them in its middle; a closed account's lists stopped in February.
export const COVERAGE: Coverage = {
  months: Array.from({ length: 10 }, (_, i) => `2026-${String(i + 1).padStart(2, "0")}`),
  accounts: [
    {
      account: CASH,
      closed: false,
      shares: ["1", "1", "1", "1", "1", "1", "0.452", "1", "1", "1"],
      link: { screen: "account", id: CASH.id, query: {} },
    },
    {
      account: CARD,
      closed: false,
      shares: ["0", "0", "0.548", "1", "1", "1", "1", "1", "1", "1"],
      link: { screen: "account", id: CARD.id, query: {} },
    },
    {
      account: { id: "teb-111111111", label: "Eski Vadesiz TL" },
      closed: true,
      shares: ["1", "1", "0", "0", "0", "0", "0", "0", "0", "0"],
      link: { screen: "account", id: "teb-111111111", query: {} },
    },
  ],
};

// From the salary into the TL account, from there to the card and to spending, and from the card to spending.
export const FLOWS: Flows = {
  start: "2026-10-01",
  end: "2026-10-31",
  nodes: [
    { id: "income:Örnek İşveren A.Ş.", kind: "income", name: "Örnek İşveren A.Ş.", account: null },
    { id: CASH.id, kind: "account", name: "", account: CASH },
    { id: CARD.id, kind: "account", name: "", account: CARD },
    { id: "spending:Gıda", kind: "spending", name: "Gıda", account: null },
    { id: "spending:Ev", kind: "spending", name: "Ev", account: null },
    { id: "people", kind: "people", name: "", account: null },
  ],
  edges: [
    edge("income:Örnek İşveren A.Ş.", CASH.id, 4000000, 1, ["income"], { account: CASH.id, kind: "income" }),
    edge(CASH.id, "spending:Ev", 1500000, 1, ["purchase"], { account: CASH.id, group: "Ev" }),
    edge(CASH.id, CARD.id, 900000, 1, ["card_payment"], { account: CASH.id, kind: "card_payment" }),
    edge(CARD.id, "spending:Gıda", 840050, 6, ["purchase", "refund"], { account: CARD.id, group: "Gıda" }),
    edge(CASH.id, "people", 250000, 2, ["p2p_transfer"], { account: CASH.id, kind: "p2p_transfer" }),
  ],
  note: "",
};

type Band = Flows["edges"][number];

/** A band of the flow, its rows on the Transactions screen narrowed to the flow's month. */
function edge(source: string, target: string, minor: number, rows: number, kinds: Band["kinds"], query: Band["link"]["query"]) {
  const link = { screen: "transactions" as const, id: "", query: { ...query, from: "2026-10-01", to: "2026-10-31" } };
  return { source, target, amount: tl(minor), rows, kinds, link };
}

// --- the month-end closing (F11) --------------------------------------------------------------------------------------

const MONTH_NAMES = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım"];
const BROKER = { id: "ornek-yatirim-1", label: "Örnek Yatırım Hesabı" };

/** "2026-10" moved by some months: ("2026-01", -1) → "2025-12". */
function shiftMonth(month: string, by: number): string {
  const [year = 2026, number = 1] = month.split("-").map(Number);
  const index = year * 12 + number - 1 + by;
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`;
}

function monthEnd(month: string, status: MonthStatus, overrides: Partial<MonthEnd> = {}): MonthEnd {
  const [year, number = 1] = month.split("-");
  return {
    month,
    name: `${MONTH_NAMES[Number(number) - 1] ?? "Aralık"} ${year}`,
    status,
    summary: "Bütün hesapların belgeleri ayın tamamını kapsıyor ve tutarlı.",
    totals: {
      expense: tl(2032799),
      income: tl(4000000),
      people: tl(0),
      debt: tl(0),
      saving: tl(0),
      fees: tl(800),
      left: tl(1967201),
    },
    provisional: 0,
    unmatched: 0,
    income_note: "hesap dökümlerindeki gelen para",
    link: { screen: "month", id: month, query: {} },
    ...overrides,
  };
}

// On 15 November: November runs, October waits for a card's statement, September and August closed, July misses a
// list's first days and June has a statement that does not add up.
export const MONTH_ENDS: MonthEndList = {
  today: "2026-11-15",
  months: [
    monthEnd("2026-11", "running", {
      summary: "Rakamlar şimdiye kadar gelen ekstre ve dökümlerden.",
      totals: { ...monthEnd("2026-11", "running").totals, expense: tl(84050), income: null, left: null },
      provisional: 2,
      income_note: "bu ay için hesap dökümü yok: gelir bilinmiyor",
    }),
    monthEnd("2026-10", "waiting", {
      summary: "Ekstresi beklenen hesap var: Örnek Kart •1234 (19–31 Ekim ekstresi, kesim ~18.11).",
      provisional: 2,
      unmatched: 1,
    }),
    monthEnd("2026-09", "closed", { totals: { ...monthEnd("2026-09", "closed").totals, expense: tl(2118242) } }),
    monthEnd("2026-08", "closed"),
    monthEnd("2026-07", "missing", {
      summary: "Kapanması için eksik belge var: Örnek Vadesiz TL (1–4 Temmuz hesap dökümü eksik).",
    }),
    monthEnd("2026-06", "check", { summary: "Kontrol edilecek belge var: Örnek Kart •1234 ekstresi tutmuyor." }),
  ],
  export: "month_end",
};

const RENT = row({
  fingerprint: "c1c1c1c1c1c1c1c1c1c1",
  day: "2026-10-03",
  account: CASH,
  title: "Örnek Ev Sahibi",
  description: "KIRA ODEMESI ORNEK",
  merchant: "Örnek Ev Sahibi",
  amount: tl(1500000),
  category: "Kira",
  group: "Ev",
  necessity: "required",
  certainty: "confirmed",
});
const MARKET = row({
  fingerprint: "c2c2c2c2c2c2c2c2c2c2",
  day: "2026-10-12",
  title: "Örnek Market",
  description: "ORNEK MARKET KADIKOY",
  merchant: "Örnek Market",
  amount: tl(215000),
  category: "Market",
  group: "Gıda",
  necessity: "required",
  certainty: "confirmed",
});
const CAFE = row({
  fingerprint: "c3c3c3c3c3c3c3c3c3c3",
  day: "2026-10-25",
  title: "Örnek Kafe",
  description: "ORNEK KAFE MODA",
  merchant: "Örnek Kafe",
  amount: tl(9000),
  category: "Kafe",
  group: "Gıda",
  necessity: "optional",
  certainty: "provisional",
  document: RECEIPT,
});
const UNSEEN = row({
  fingerprint: "c4c4c4c4c4c4c4c4c4c4",
  day: "2026-10-09",
  title: "Örnek Kitapçı",
  description: "ORNEK KITAPCI",
  merchant: "Örnek Kitapçı",
  amount: tl(32000),
  category: "Kitap",
  group: "Eğlence",
  necessity: "optional",
  counted: false,
  certainty: "excluded",
  document: RECEIPT,
});

function closedAccount(account: { id: string; label: string }, overrides: Partial<MonthEndAccount> = {}) {
  return {
    account,
    status: "closed" as const,
    label: "Kapandı",
    blocking: true,
    needed: 31,
    covered: 31,
    open: [],
    statements: [
      {
        start: "2026-10-01",
        end: "2026-10-31",
        cut: "2026-10-31",
        card: false,
        check: "verified",
        document: ACCOUNT_LIST,
      },
    ],
    receipts: { matched: 0, provisional: 0, unmatched: 0, no_statement: 0 },
    balance: tl(18438010),
    last: "2026-10-31",
    next_cut: null,
    late: false,
    untracked: false,
    waiting_for: "",
    note: "ayın tamamı belgelerle kapsandı ve tutarlı",
    ...overrides,
  } satisfies MonthEndAccount;
}

function regular(payee: string, category: string, paid: Row[], expected: string | null, now: number, monthly: number) {
  return { payee, category, paid, expected, this_month: tl(now), monthly: tl(monthly) };
}

/** A month in full, October by default: a list closes it, a card waits for its statement, a brokerage never holds
 * it. */
export function monthEndDetail(month = "2026-10", overrides: Partial<MonthEndDetail> = {}): MonthEndDetail {
  const listed = MONTH_ENDS.months.find((m) => m.month === month) ?? monthEnd(month, "closed");
  const before = MONTH_ENDS.months.find((m) => m.month === shiftMonth(month, -1));
  return {
    month: listed,
    previous: before ? before.totals : monthEnd(month, "closed").totals,
    typical: tl(2030299),
    typical_months: 6,
    accounts: [
      closedAccount(CARD, {
        status: "waiting",
        label: "Bekleniyor",
        covered: 18,
        open: [{ start: "2026-10-19", end: "2026-10-31" }],
        statements: [
          {
            start: "2026-10-01",
            end: "2026-10-18",
            cut: "2026-10-18",
            card: true,
            check: "verified",
            document: STATEMENT,
          },
        ],
        receipts: { matched: 3, provisional: 2, unmatched: 1, no_statement: 0 },
        balance: null,
        last: "2026-10-18",
        next_cut: "2026-11-18",
        late: true,
        waiting_for: "19–31 Ekim ekstresi, kesim ~18.11",
        note: "19–31 Ekim ekstresi e-postayla bekleniyor",
      }),
      closedAccount(CASH),
      closedAccount(BROKER, { blocking: false, balance: tl(134200) }),
    ],
    groups: [
      { name: "Ev", slot: 3, amount: tl(1605000), count: null, code: "" },
      { name: "Gıda", slot: 1, amount: tl(417000), count: null, code: "" },
      { name: "Abonelikler", slot: 4, amount: tl(9999), count: null, code: "" },
      { name: "Banka", slot: 8, amount: tl(800), count: null, code: "" },
    ],
    levels: [
      { name: "Gerekli", slot: 1, amount: tl(2004000), count: null, code: "required" },
      { name: "İsteğe bağlı", slot: 4, amount: tl(27999), count: null, code: "optional" },
      { name: "Gereksiz", slot: 5, amount: tl(800), count: null, code: "unnecessary" },
    ],
    categories: [
      { name: "Kira", slot: 3, amount: tl(1500000), count: 1, code: "" },
      { name: "Market", slot: 1, amount: tl(399000), count: 2, code: "" },
      { name: "Faturalar", slot: 3, amount: tl(105000), count: 2, code: "" },
      { name: "Kafe", slot: 1, amount: tl(18000), count: 2, code: "" },
      { name: "Dijital Abonelikler", slot: 4, amount: tl(9999), count: 1, code: "" },
      { name: "Banka ücretleri", slot: 8, amount: tl(800), count: 1, code: "" },
    ],
    merchants: [
      { name: "Örnek Ev Sahibi", slot: 3, amount: tl(1500000), count: 1, code: "" },
      { name: "Örnek Market", slot: 1, amount: tl(399000), count: 2, code: "" },
      { name: "Örnek Enerji", slot: 3, amount: tl(60000), count: 1, code: "" },
      { name: "Örnek İletişim", slot: 3, amount: tl(45000), count: 1, code: "" },
      { name: "Örnek Kafe", slot: 1, amount: tl(18000), count: 2, code: "" },
      { name: "Örnek Müzik", slot: 4, amount: tl(9999), count: 1, code: "" },
    ],
    regular: [
      regular("Örnek Ev Sahibi", "Kira", [RENT], null, 1500000, 1500000),
      regular("Örnek Market", "Market", [MARKET], null, 215000, 215000),
      regular("Örnek Market", "Market", [], "2026-10-22", 0, 184000), // the chain's other shop: not seen yet
    ],
    big: [RENT],
    provisional: [CAFE],
    unmatched: [UNSEEN],
    count: 8,
    trend: [
      { month: "2025-11", expense: tl(0) },
      { month: "2025-12", expense: tl(0) },
      ...[2122799, 2228242, 2062799, 2872799, 1997799, 1987799, 903999, 1984799, 2118242, 2032799].map((minor, i) => ({
        month: `2026-${String(i + 1).padStart(2, "0")}`,
        expense: tl(minor),
      })),
    ],
    debt_end: tl(84050),
    previous_month: shiftMonth(month, -1),
    next_month: shiftMonth(month, 1),
    export: "month_end",
    ...overrides,
  };
}
// --- the Rules screen (F15) -----------------------------------------------------------------------------------------

/** Rules with a file of the user's own: their categories, two payments ended (one shipped), a merchant on its own. */
export const OWN_RULES: CategoryRules = {
  content: "Gıda:\n  Market:\n    Örnek Market: [ORNEK MARKET]\n\n_biten:\n  Örnek Dergi: 2026-09\n",
  categories: [
    category("Market", "Gıda", 1, { necessity: "required", own: true }),
    category("Kafe", "Yeme içme", 2),
    category("Kira", "Ev", 3, { necessity: "required", regular: true, own: true }),
    category("Dijital Abonelikler", "Abonelikler", 4, { regular: true }),
    category("Maaş", "Gelir", 5, { necessity: null }),
  ],
  ended: [
    { merchant: "Örnek Dergi", month: "2026-09", own: true },
    { merchant: "Eski Spor Salonu", month: "2025-12", own: false },
  ],
  merchant_necessity: [{ merchant: "Örnek Kafe", necessity: "unnecessary" }],
  history: ["personal 2026-11-02 10.00.00.yaml", "personal 2026-10-20 08.30.00.yaml"],
};

/** A change's preview: three market rows become café rows, and the file gains the merchant. */
export const RULE_CHANGE: RuleChange = {
  content: `${OWN_RULES.content}Yeme içme:\n  Kafe:\n    Örnek Kafe: [ORNEK KAFE]\n`,
  diff: "--- personal.yaml\n+++ personal.yaml\n@@ -5,0 +6,3 @@\n+Yeme içme:\n+  Kafe:\n+    Örnek Kafe: [ORNEK KAFE]\n",
  changed: 3,
  moves: [{ before: "Market", after: "Kafe", count: 3, total: tl(252150) }],
  examples: [
    {
      fingerprint: "a7a7a7a7a7a7a7a7a7a7",
      day: "2026-11-12",
      description: "ORNEK KAFE KADIKOY",
      amount: tl(84050),
      before: { merchant: "Örnek Kafe", category: "Market", necessity: "required", kind: "purchase" },
      after: { merchant: "Örnek Kafe", category: "Kafe", necessity: "optional", kind: "purchase" },
    },
  ],
  saved: false,
  backup: "",
};

// --- the to-do list (F19) -------------------------------------------------------------------------------------------

export const TALIMAT = "b".repeat(64); // a document no reader takes

export function todo(overrides: Partial<TodoItem> = {}): TodoItem {
  return {
    key: "uncategorized:ornek kafe",
    kind: "uncategorized",
    title: "Örnek Kafe",
    detail: "5 işlem, toplam 2.521,50 TL; sonuncusu 12.11.2026. Hiçbir kural adlandırmıyor.",
    count: 5,
    amount: tl(252150),
    target: "Örnek Kafe",
    link: { screen: "transactions", id: "", query: { category: "Diğer Harcamalar", q: "Örnek Kafe" } },
    actions: ["add_rule", "ask_claude", "ignore"],
    prompt: "İplikçi Nedim'de 'Örnek Kafe' adlı işyerinin 5 işlemi kategorisiz.",
    ignored: false,
    ...overrides,
  };
}

/** A merchant no rule names, an account behind, a document no reader takes and a split the row no longer takes. */
export const TODOS: Todos = {
  items: [
    todo(),
    todo({
      key: "gap:Örnek Vadesiz TL:2026-10-31:2026-07",
      kind: "missing_documents",
      title: "Örnek Vadesiz TL",
      detail: "Son hesap hareketleri 31.10.2026 tarihli, 15 gün önce; eksik aylar: 2026-07.",
      count: 1,
      amount: null,
      target: "Örnek Vadesiz TL",
      link: { screen: "documents", id: "", query: {} },
      actions: ["upload", "ignore"],
      prompt: "",
    }),
    todo({
      key: `document:${TALIMAT}`,
      kind: "unprocessed_document",
      title: "TalimatFormu.pdf",
      detail: "Belge işlenmedi: talimat formu.",
      count: 1,
      amount: null,
      target: TALIMAT,
      link: { screen: "document", id: TALIMAT, query: {} },
      actions: ["open", "reparse", "ask_claude", "ignore"],
      prompt: "İplikçi Nedim'de 'TalimatFormu.pdf' belgesi işlenmedi (talimat formu).",
    }),
    todo({
      key: `split:${WHOLE}`,
      kind: "split_dropped",
      title: "Örnek Süpermarket",
      detail: "01.11.2026 günlü 1.250,00 TL tutarındaki satırı 2 parçaya bölmüştünüz; satır bütün olarak sayılıyor.",
      count: 1,
      amount: tl(125000),
      target: WHOLE,
      link: { screen: "transaction", id: WHOLE, query: {} },
      actions: ["open", "ignore"],
      prompt: "",
    }),
  ],
  counts: {
    uncategorized: 1,
    unmatched_evidence: 0,
    unmatched_invoice: 0,
    unverified_statement: 0,
    missing_documents: 1,
    unprocessed_document: 1,
    orphan_annotation: 0,
    split_dropped: 1,
    format_alarm: 0,
  },
  ignored: 1,
};

/** What the user took off the list, listed when asked for. */
export const IGNORED_TODO = todo({
  key: "uncategorized:eski kitapci",
  title: "Eski Kitapçı",
  detail: "2 işlem, toplam 340,00 TL; sonuncusu 02.09.2026. Hiçbir kural adlandırmıyor.",
  count: 2,
  amount: tl(34000),
  target: "Eski Kitapçı",
  ignored: true,
});

// --- the setup wizard and the Settings screen (F17) -----------------------------------------------------------------

/** A computer where only the data folder, the senders and the service stand: names, e-mail and documents to do. */
export const SETUP: Setup = {
  steps: [
    { step: "data_folder", done: true, optional: false, note: "/veri/iplikci" },
    { step: "names", done: false, optional: false, note: "Henüz ad yok." },
    { step: "business_names", done: false, optional: true, note: "Yok." },
    { step: "mail", done: false, optional: false, note: "E-posta bağlantısı kurulmadı." },
    { step: "senders", done: true, optional: true, note: "3 banka adresi, 1 banka dışı gönderici" },
    { step: "documents", done: false, optional: false, note: "Henüz belge yok." },
    { step: "notifications", done: false, optional: true, note: "Yalnızca uygulama içi." },
    { step: "service", done: true, optional: false, note: "Bilgisayar açılınca kendiliğinden başlar." },
    { step: "remote", done: false, optional: true, note: "Kapalı: yalnızca bu bilgisayardan." },
  ],
  first_run: false,
};

export function settings(overrides: Partial<Settings> = {}): Settings {
  return {
    home: "/veri/iplikci",
    port: 8643,
    names: [],
    business_names: [],
    mail: {
      connector: "imap",
      configured: false,
      address: "",
      start: "2026-01-01",
      server: "",
      stopped: false,
      last_error: "",
    },
    bank_senders: ["garanti.com.tr", "teb.com.tr", "vakifbank.com.tr"],
    backup_days: 30,
    ...overrides,
  };
}

// --- the service's own life (ADR-0017) -------------------------------------------------------------------------------

/** The service as GET /api/service gives it: registered for this data folder with launchd, able to end itself. */
export function serviceState(overrides: Partial<ServiceState> = {}): ServiceState {
  return {
    version: "0.7.0",
    started_at: "2026-11-15T08:00:00+00:00",
    registered: true,
    manager: "launchd",
    can_end: true,
    restore: null,
    ...overrides,
  };
}

function backupItem(name: string, created_at: string, reason: string, overrides: Partial<BackupItem> = {}): BackupItem {
  return {
    name,
    created_at,
    reason,
    app: "0.7.0",
    documents: 42,
    annotations: 3,
    size: 4_718_592,
    damaged: 0,
    ...overrides,
  };
}

// The backups, newest first: a daily one, one asked for, and an older daily one with a file that no longer matches.
export const BACKUPS: BackupItem[] = [
  backupItem("2026-11-15 03.00.00", "2026-11-15T00:00:00+00:00", "daily"),
  backupItem("2026-11-14 18.30.00", "2026-11-14T15:30:00+00:00", "manual", { documents: 41 }),
  backupItem("2026-11-01 03.00.00", "2026-11-01T00:00:00+00:00", "daily", { documents: 30, damaged: 1 }),
];

export const handlers = [
  http.get("/api/labels", () => HttpResponse.json(LABELS)),
  http.get("/api/dashboard", () => HttpResponse.json(DASHBOARD)),
  http.get("/api/spending", () => HttpResponse.json(SPENDING)),
  http.get("/api/insights", () => HttpResponse.json(INSIGHTS)),
  http.get("/api/feed", ({ request }) =>
    HttpResponse.json(new URL(request.url).searchParams.get("before") === "27" ? FEED_OLDER : FEED_FIRST),
  ),
  http.get("/api/feed/now", () => HttpResponse.json(NOW)),
  http.get("/api/accounts", () => HttpResponse.json(ACCOUNTS)),
  http.get("/api/accounts/flows", () => HttpResponse.json(FLOWS)), // before the pages: "flows" is no account
  http.get("/api/accounts/coverage", () => HttpResponse.json(COVERAGE)),
  http.get("/api/accounts/:id", ({ params }) => {
    const pages: Record<string, AccountPage> = { [CARD.id]: CARD_PAGE, [FX.id]: FX_PAGE };
    return HttpResponse.json(pages[String(params["id"])] ?? accountPage());
  }),
  http.get("/api/transactions", ({ request }) =>
    HttpResponse.json(new URL(request.url).searchParams.get("offset") === "50" ? NEXT_TRANSACTIONS : TRANSACTIONS),
  ),
  http.get("/api/transactions/views", () => HttpResponse.json([])), // before the rows: "views" is no fingerprint
  http.get("/api/transactions/:fingerprint", ({ params }) =>
    HttpResponse.json(String(params["fingerprint"]).startsWith(WHOLE) ? SPLIT_DETAIL : transactionDetail()),
  ),
  http.get("/api/rules/categories", () => HttpResponse.json(CATEGORY_RULES)),
  http.get("/api/documents/:sha256/view", ({ params }) =>
    String(params["sha256"]) === LOCKED
      ? HttpResponse.json({ code: "document_unshown", title: "Belge gösterilemiyor: PDF şifreli" }, { status: 422 })
      : HttpResponse.json(DOCUMENT_VIEWS[String(params["sha256"])] ?? STATEMENT_VIEW),
  ),
  http.get("/api/documents/:sha256/pages/:page/lines", () => HttpResponse.json({ lines: STATEMENT_LINES })),
  http.get("/api/documents/:sha256", ({ params }) =>
    HttpResponse.json(DOCUMENT_DETAILS[String(params["sha256"])] ?? STATEMENT_DETAIL),
  ),
  http.get("/api/subscriptions", () => HttpResponse.json(SUBSCRIPTIONS)),
  http.get("/api/calendar", () => HttpResponse.json(CALENDAR)),
  http.get("/api/forecast", () => HttpResponse.json(FORECAST)),
  http.get("/api/holdings", () => HttpResponse.json(HOLDINGS)),
  http.get("/api/fx", () => HttpResponse.json(FX_RATES)),
  http.get("/api/invoices", () => HttpResponse.json(INVOICES)),
  http.get("/api/settings/mail/other-senders", () => HttpResponse.json(OTHER_SENDERS)),
  http.get("/api/system", () => HttpResponse.json(systemStatus())),
  http.get("/api/exports", () => HttpResponse.json(EXPORTS)),
  http.get("/api/bridge", () => HttpResponse.json(BRIDGES)),
  http.get("/api/extension", () => HttpResponse.json(EXTENSION)),
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
  // the month-end closing (F11)
  http.get("/api/month-end", () => HttpResponse.json(MONTH_ENDS)),
  http.get("/api/month-end/:month", ({ params }) => HttpResponse.json(monthEndDetail(String(params["month"])))),
  // the Rules screen (F15)
  http.post("/api/rules/categories/preview", () => HttpResponse.json(RULE_CHANGE)),
  http.put("/api/rules/categories", () =>
    HttpResponse.json({ ...RULE_CHANGE, saved: true, backup: "personal 2026-11-15 09.00.00.yaml" }),
  ),
  // the to-do list (F19)
  http.get("/api/todos", ({ request }) =>
    HttpResponse.json(
      new URL(request.url).searchParams.get("with_ignored") === "true"
        ? { ...TODOS, items: [...TODOS.items, IGNORED_TODO] }
        : TODOS,
    ),
  ),
  http.post("/api/todos/ignored", () => new HttpResponse(null, { status: 204 })),
  http.post("/api/documents/:sha256/reparse", () => HttpResponse.json({ status: "processed" })),
  // the setup wizard and the Settings screen (F17)
  http.get("/api/setup", () => HttpResponse.json(SETUP)),
  http.get("/api/settings", () => HttpResponse.json(settings())),
  http.put("/api/settings/identity", async ({ request }) =>
    HttpResponse.json(settings((await request.json()) as Pick<Settings, "names" | "business_names">)),
  ),
  http.put("/api/settings/mail", async ({ request }) => {
    const change = (await request.json()) as { connector?: "imap" | "browser_bridge"; start?: string };
    const mail = settings().mail;
    return HttpResponse.json(settings({ mail: { ...mail, ...change } }));
  }),
  http.put("/api/settings/backup", async ({ request }) =>
    HttpResponse.json(settings({ backup_days: ((await request.json()) as { keep_days: number }).keep_days })),
  ),
  http.post("/api/settings/mail/imap", () => HttpResponse.json({ folder: "INBOX", in_keyring: true })),
  http.delete("/api/settings/mail/imap", () => new HttpResponse(null, { status: 204 })),
  // the service's own life (ADR-0017)
  http.get("/api/service", () => HttpResponse.json(serviceState())),
  http.get("/api/backups", () => HttpResponse.json(BACKUPS)),
];

export const server = setupServer(...handlers);

// The service's API types, generated from its OpenAPI document by `iplikci dev api-tipleri` (ADR-0007).
// Do not edit by hand: change the API's models and generate again; a test keeps this file current.

export interface AccountForecastOut {
  account: AccountRefOut;
  start: StartOut;
  end_balance: MoneyOut;
  lowest: BalanceOut;
  negative: BalanceOut | null;
  spend: SpreadOut | null;
  cards: SpreadOut | null;
  interest: MoneyOut | null;
  items: CalendarItemOut[];
  days: BalanceOut[];
  notes: string[];
}

export interface AccountRefOut {
  id: string;
  label: string;
}

export type AccountType = "credit_card" | "debit_card" | "current" | "deposit" | "overdraft" | "fx" | "gold" | "brokerage" | "loan";

export interface AlarmIn {
  layer: number;
  version?: string;
  page?: AlarmPageIn | null;
}

export interface AlarmOut {
  news: boolean;
}

/** What a "Show original" page without the message showed: never its text, only its masked title. */
export interface AlarmPageIn {
  length: number;
  title?: string;
  download: boolean;
  raw_id: boolean;
}

export interface AlertConditionModel {
  days?: number | null;
  amount?: number | null;
  text?: string;
}

export interface AlertPreviewIn {
  rule: AlertRuleModel;
}

export interface AlertPreviewOut {
  count: number;
  days: number;
  examples: NotifyMessageOut[];
}

/** An alert rule (architecture §14); rules/alerts.yaml writes it with Turkish keys. */
export interface AlertRuleModel {
  name: string;
  event: EventKind;
  condition?: AlertConditionModel;
  channels: Channel[];
  detail?: DetailLevel | null;
  enabled?: boolean;
  quiet?: boolean;
}

export interface AlertRulesIn {
  rules: AlertRuleModel[];
}

export interface AlertRulesOut {
  rules: AlertRuleModel[];
  own: boolean;
  problem: string;
  events: EventInfoOut[];
}

export interface AppliedOut {
  stored: number;
  counts: Record<string, number>;
  trash: string | null;
}

export interface ApplyIn {
  plan_id: string;
}

export interface ArrivalOut {
  kind: string;
  name: string;
  origin: string;
  sender: string;
  subject: string;
  sent_at: string;
  received_at: string;
  gmail: string;
}

export interface AttachmentOut {
  sha256: string;
  name: string;
}

export interface BackupHealthOut {
  last: string;
  next: string;
  count: number;
  size: number;
  rehearsal: string;
  rehearsal_ok: boolean | null;
}

export interface BackupOut {
  name: string;
  created_at: string;
  reason: string;
  app: string;
  documents: number;
  annotations: number;
  size: number;
  damaged: number;
}

export interface BalanceOut {
  day: string;
  balance: MoneyOut;
}

/** What printed the balance an estimate starts from. */
export type BalanceSource = "statement" | "notice" | "portfolio";

/** The bank row that paid a bill or a receipt. */
export interface BankRowOut {
  fingerprint: string;
  day: string;
  account: AccountRefOut;
  amount: MoneyOut;
  description: string;
}

export interface BridgeOut {
  id: string;
  name: string;
  created_at: string;
  last_seen: string;
  active: boolean;
}

/** A payment or an income expected on a day, with what the day and the amount rest on. */
export interface CalendarItemOut {
  day: string;
  kind: PaymentKind;
  title: string;
  account: AccountRefOut;
  direction: "out" | "in";
  amount: MoneyOut;
  minimum: MoneyOut | null;
  basis: string;
  series: string;
  fingerprints: string[];
}

export interface CalendarOut {
  today: string;
  end: string;
  items: CalendarItemOut[];
}

/** A card's statement period and its spending (purchases, refunds, interest and fees). */
export interface CardPeriodOut {
  start: string;
  end: string;
  spent: MoneyOut;
  rows: number;
}

export interface CategoryMoveOut {
  before: string;
  after: string;
  count: number;
  total: MoneyOut;
}

export interface CategoryOut {
  name: string;
  group: string;
  slot: number;
  necessity: Necessity | null;
  regular: boolean;
  own: boolean;
}

export interface CategoryRulesOut {
  content: string;
  categories: CategoryOut[];
  ended: EndedOut[];
  merchant_necessity: MerchantNecessityOut[];
  history: string[];
}

/** How sure a row or a total is, and whether it counts (architecture §8). */
export type Certainty = "confirmed" | "provisional" | "excluded" | "info";

export interface ChangedRowOut {
  fingerprint: string;
  day: string;
  description: string;
  amount: MoneyOut;
  before: RowLabelsOut;
  after: RowLabelsOut;
}

/** Where a notification goes (ADR-0010). */
export type Channel = "in_app" | "desktop" | "email" | "telegram";

/**
 * What stands between a notification channel and the next notification besides its being turned off: the interface
 * names the user's next step by it (ADR-0010).
 */
export type ChannelStage = "ready" | "stopped" | "unavailable" | "no_bot" | "token_lost" | "not_paired";

export interface ChannelStateOut {
  channel: Channel;
  on: boolean;
  ready: boolean;
  stage: ChannelStage;
  note: string;
}

/** A category of commitments (its payments are regular even when the amount changes), or no longer. */
export interface CommitmentIn {
  action: "commitment";
  category: string;
  on: boolean;
}

export interface CursorOut {
  last_id: string;
  last_date: string;
  start_day: string;
  senders: string[];
  history_due: boolean;
}

export interface DeliveredOut {
  taken: string;
  documents: number;
}

/** Where a notification stands on its channel (ADR-0010). */
export type DeliveryStatus = "pending" | "sent" | "held" | "digested" | "failed";

/** How much a notification says (ADR-0010). */
export type DetailLevel = "full" | "summary" | "minimal";

/** Which way a row's money goes: the screens say it in words, never by a sign (architecture §16). */
export type Direction = "out" | "in";

export interface DiskOut {
  vault: number;
  database: number;
  free: number;
}

export interface DocumentDetailOut {
  document: DocumentOut;
  parser_version: string;
  view: ViewKind;
  arrivals: ArrivalOut[];
  checks: StatementCheckOut[];
  rows: DocumentRowOut[];
  more_rows: boolean;
  parent: string;
  attachments: AttachmentOut[];
}

export type DocumentKind = "card_statement" | "account_statement" | "receipt" | "notice" | "invoice";

export interface DocumentOut {
  sha256: string;
  name: string;
  file: string;
  kind: string;
  parser: string;
  reader: string;
  status: "processed" | "unprocessed" | "unreadable";
  reason: string;
  verified: boolean | null;
  period_start: string;
  period_end: string;
  sources: string[];
  added_at: string;
  size: number;
}

export interface DocumentPageOut {
  items: DocumentOut[];
  next: string;
}

export interface DocumentRowOut {
  fingerprint: string;
  day: string;
  description: string;
  amount: MoneyOut;
  kind: TransactionKind;
  account: string;
  category: string;
  provisional: boolean;
  counted: boolean;
  evidence: EvidenceStatus | null;
  ref: SourceRefOut | null;
}

/** Where a stored document stands (ADR-0003). */
export type DocumentStatus = "processed" | "unprocessed" | "unreadable" | "removed";

export interface DocumentViewOut {
  kind: ViewKind;
  pages: PageSizeOut[];
  table: TableOut | null;
  mail: iplikci__api__routes__documents__MailOut | null;
  text: string;
  has_html: boolean;
}

/** A payment the user ended ("İptal ettim"): none is expected after month. */
export interface EndedIn {
  action: "ended";
  merchant: string;
  month: string;
  note?: string;
}

export interface EndedOut {
  merchant: string;
  month: string;
  own: boolean;
}

/** An event a rule may watch, and the conditions it allows. */
export interface EventInfoOut {
  kind: EventKind;
  label: string;
  days: boolean;
  amount: boolean;
  text: boolean;
}

/** What the event log records (architecture §13); the alert rules name these (architecture §14). */
export type EventKind = "document.received" | "document.processed" | "document.unprocessed" | "document.unreadable" | "transaction.created" | "transaction.confirmed" | "transaction.large" | "evidence.unmatched" | "invoice.matched" | "invoice.pending" | "invoice.unmatched" | "payment.due_soon" | "expected_payment.missing" | "balance.forecast_negative" | "subscription.price_changed" | "subscription.paid_after_cancel" | "income.received" | "income.late" | "month.ended" | "month.closed" | "month.needs_check" | "parser.format_alarm" | "mail.auth_failed" | "mail.bridge_alarm" | "mail.bridge_silent" | "backup.failed" | "bridge.paired" | "bridge.revoked";

export interface EventOut {
  id: number;
  at: string;
  kind: string;
  target: string;
  detail: Record<string, unknown>;
}

/** What the statements say about a receipt's or a bank notice's row (docs/domain/ledger.md). */
export type EvidenceStatus = "matched" | "provisional" | "unmatched" | "no_statement";

export type ExportKind = "report" | "csv" | "xlsx" | "month_end";

export interface ExportOut {
  kind: ExportKind;
  name: string;
  size: number;
  made_at: string;
}

export interface ExportsQueuedOut {
  queued: boolean;
}

export interface FailedJobOut {
  id: number;
  kind: string;
  attempts: number;
  finished_at: string;
  error: string;
}

/** What an event's detail says (architecture §13); a field the event does not carry is null or empty. */
export interface FeedDetailOut {
  title: string;
  amount: MoneyOut | null;
  minimum: MoneyOut | null;
  balance: MoneyOut | null;
  old: MoneyOut | null;
  new: MoneyOut | null;
  day: string | null;
  days: number | null;
  payment: PaymentKind | null;
  period: SeriesPeriod | null;
  cancelled: string;
  status: MonthStatus | null;
  count: number | null;
  first: string | null;
  last: string | null;
  provisional: boolean | null;
  source: SourceKind | null;
  document_kind: DocumentKind | null;
  parser: string;
  reader: string;
  version: string;
  reason: string;
  stage: string;
  unverified: AccountRefOut[];
}

/** A document an event concerns, as the archive keeps it now. */
export interface FeedDocumentOut {
  sha256: string;
  name: string;
  kind: DocumentKind | null;
  status: DocumentStatus;
}

/** An event of the log, with what it concerns now and where it leads. */
export interface FeedItemOut {
  id: number;
  at: string;
  kind: string;
  label: string;
  text: string;
  target: string;
  account: AccountRefOut | null;
  certainty: Certainty | null;
  detail: FeedDetailOut;
  row: RowOut | null;
  document: FeedDocumentOut | null;
  link: LinkOut | null;
}

export interface FeedOut {
  items: FeedItemOut[];
  next: number | null;
}

export interface FetchQueuedOut {
  queued: boolean;
}

export interface ForecastOut {
  label: string;
  today: string;
  end: string;
  accounts: AccountForecastOut[];
  elsewhere: CalendarItemOut[];
  skipped: SkippedOut[];
  notes: string[];
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

/** A card purchase in installments with some still to come: the card's newest statement billed `number`. */
export interface InstallmentOut {
  card: AccountRefOut;
  title: string;
  number: number;
  count: number;
  amount: MoneyOut;
  left: number;
  remaining: MoneyOut;
  last_day: string;
  fingerprint: string;
}

export interface InvoiceCountsOut {
  pending: number;
  unmatched: number;
  matched: number;
}

/** What a non-bank document asks for (F14): it sets the days its bank row is looked for in. */
export type InvoiceKind = "bill" | "receipt";

/** An item of a bill or a receipt, as it prints it. */
export interface InvoiceLineOut {
  description: string;
  amount: MoneyOut;
  quantity: string | null;
}

/**
 * A non-bank sender's bill or receipt and what the bank's rows say of it. None changes a total: the bank row that paid
 * it is what counts.
 */
export interface InvoiceOut {
  key: string;
  kind: InvoiceKind;
  status: InvoiceStatus;
  seller: string;
  number: string;
  issued: string;
  due: string | null;
  total: MoneyOut;
  lines: InvoiceLineOut[];
  window: WindowOut;
  document: string;
  sha256: string;
  row: BankRowOut | null;
  reasons: string[];
}

/** What the bank's rows say of a non-bank document (docs/domain/ledger.md, "Banka dışı faturalar"). */
export type InvoiceStatus = "matched" | "pending" | "unmatched";

export interface InvoicesOut {
  items: InvoiceOut[];
  counts: InvoiceCountsOut;
}

export interface KnownIn {
  ids: string[];
}

export interface KnownOut {
  missing: string[];
}

/** The Turkish label of every code, by code type (DocumentStatus, JobKind, …). */
export type LabelsOut = Record<string, Record<string, string>>;

/** Where an item leads in the interface: a screen and what to open there (Screen names what id holds for each). */
export interface LinkOut {
  screen: Screen;
  id: string;
  query: Record<string, string>;
}

export interface LoginLink {
  url: string;
}

/** F01's measure: the kept bank messages read or knowingly classified as moving no money. */
export interface MailCoverageOut {
  total: number;
  read: number;
  attached: number;
  no_money: number;
  business: number;
  unknown: number;
  share: number;
  left: UnknownMailOut[];
}

/** A merchant's own level of necessity; null takes it back to its category's. */
export interface MerchantNecessityIn {
  action: "necessity";
  merchant: string;
  necessity: Necessity | null;
}

export interface MerchantNecessityOut {
  merchant: string;
  necessity: Necessity;
}

/** A named merchant under a category: its rows get the category ("bu işyerini her zaman X say"). */
export interface MerchantRuleIn {
  action: "merchant";
  category: string;
  merchant: string;
  patterns: string[];
  necessity?: Necessity | null;
}

/**
 * An amount in its currency's smallest unit: {"minor": 123456, "currency": "TRY"} is 1.234,56 TL. The interface formats
 * it (architecture §16).
 */
export interface MoneyOut {
  minor: number;
  currency: string;
}

/** Month-end closing: of a month, and of each account within it. */
export type MonthStatus = "closed" | "waiting" | "missing" | "check" | "running";

export type Necessity = "required" | "optional" | "unnecessary" | "unknown";

/** A payment expected again. */
export interface NotEndedIn {
  action: "not_ended";
  merchant: string;
}

/** A notification as it was sent on its channel. */
export interface NotificationOut {
  id: number;
  created_at: string;
  rule: string;
  kind: string;
  target: string;
  channel: Channel;
  detail: DetailLevel;
  title: string;
  body: string;
  status: DeliveryStatus;
  attempts: number;
  sent_at: string;
  error: string;
  read: boolean;
}

export interface NotificationsOut {
  items: NotificationOut[];
  unread: number;
  next?: number | null;
}

export interface NotificationsReadIn {
  up_to?: number | null;
}

export interface NotificationsReadOut {
  marked: number;
}

export interface NotifyMessageOut {
  title: string;
  body: string;
}

export interface NotifySettingsIn {
  quiet_hours: string;
  detail: Record<string, DetailLevel>;
  channels: Channel[];
}

export interface NotifySettingsOut {
  quiet_hours: string;
  detail: Record<string, DetailLevel>;
  channels: ChannelStateOut[];
  counts: Record<string, number>;
  unread: number;
}

export interface NotifyTestIn {
  channel: Channel;
}

/**
 * An account's balance today as far as the documents tell: the newest balance a document prints, moved by the receipt
 * and notice rows after it.
 */
export interface NowBalanceOut {
  account: AccountRefOut;
  type: AccountType;
  balance: MoneyOut;
  value: MoneyOut | null;
  rate: string | null;
  rate_day: string | null;
  stated: MoneyOut;
  on: string;
  source: BalanceSource;
  moves: number;
  through: string;
  certainty: Certainty;
  note: string;
}

/** A card's newest statement, what it still asks, and the period the card is in now. */
export interface NowCardOut {
  account: AccountRefOut;
  type: AccountType;
  cut: string;
  total: MoneyOut | null;
  due: string | null;
  minimum: MoneyOut | null;
  limit: MoneyOut | null;
  paid: MoneyOut;
  debt: MoneyOut | null;
  last: CardPeriodOut;
  current: CardPeriodOut;
  certainty: Certainty;
  note: string;
}

/** What stands now (F05's "Şu an" and "Yaklaşanlar"). */
export interface NowOut {
  today: string;
  balances: NowBalanceOut[];
  unknown: UnknownOut[];
  cards: NowCardOut[];
  pace: PaceOut;
  upcoming: CalendarItemOut[];
  end: string;
}

export interface OtherSendersIn {
  domains: string[];
}

/** The domains whose bills and receipts are taken in beside the banks' messages (settings: mail.other_senders). */
export interface OtherSendersOut {
  domains: string[];
}

/**
 * The month's spending so far (purchases, refunds, interest and fees) against the typical month. The month is partial:
 * card spending comes with the statements after their cut dates; the typical month comes from complete months only.
 */
export interface PaceOut {
  month: string;
  partial: boolean;
  day: number;
  days: number;
  spent: MoneyOut;
  provisional: MoneyOut;
  typical: MoneyOut | null;
  by_day: MoneyOut | null;
  months: string[];
  covered: number;
  note: string;
}

export interface PageLinesOut {
  lines: string[];
}

export interface PageSizeOut {
  width: number;
  height: number;
}

export interface PairIn {
  code: string;
  name?: string;
}

export interface PairedOut {
  id: string;
  token: string;
}

export interface PairingOut {
  code: string;
  expires_in: number;
}

/** What an item of the calendar is (F09). */
export type PaymentKind = "regular" | "periodic" | "income" | "installment" | "loan" | "card_due" | "bill";

/** A row a series rests on, and the document it is printed in. */
export interface PaymentOut {
  fingerprint: string;
  day: string;
  amount: MoneyOut;
  document: string;
  certainty: Certainty;
}

/** The document a plan item would add: a statement, an account statement or a receipt, and its check. */
export interface PlanDocumentOut {
  kind: string;
  account: string;
  start: string | null;
  end: string;
  rows: number;
  verified: boolean | null;
  check: string;
}

export interface PlanIn {
  upload?: string;
}

/**
 * One file of a plan (intake.describe): what it is and what happens to it. The MCP client reads the same keys, so two
 * keep their camelCase names.
 */
export interface PlanItemOut {
  action: string;
  label: string;
  name: string;
  source: string;
  reason: string;
  copyOf: string | null;
  target: string | null;
  fromInbox: boolean;
  document?: PlanDocumentOut | null;
}

export interface PlanOut {
  plan_id: string;
  changes: number;
  by_action: Record<string, number>;
  items: PlanItemOut[];
}

export interface PriceChangeOut {
  before: MoneyOut;
  after: MoneyOut;
  since: string;
}

export interface ProofOut {
  proof: string;
}

export interface QueueOut {
  counts: Record<string, number>;
  next_run: string;
  failures: FailedJobOut[];
}

export interface QueuedOut {
  queued: boolean;
}

export interface ReaderHealthOut {
  parser: string;
  name: string;
  version: string;
  documents: number;
  statements: number;
  verified: number;
  last_read: string;
  alarms: number;
}

export interface RefusedMailOut {
  taken: "unlisted" | "unverified" | "business";
  reason: string;
  domain: string;
  count: number;
  label: string;
}

export interface RemovedOut {
  trash: string;
}

export interface ReparsedOut {
  status: string;
}

export interface RowLabelsOut {
  merchant: string;
  category: string;
  necessity: Necessity | null;
  kind: TransactionKind;
}

/** A row of the ledger as the screens list it. */
export interface RowOut {
  fingerprint: string;
  day: string;
  account: AccountRefOut;
  title: string;
  description: string;
  merchant: string;
  counterparty: string;
  amount: MoneyOut;
  direction: Direction;
  kind: TransactionKind;
  category: string;
  group: string;
  necessity: Necessity | null;
  counted: boolean;
  expense: boolean;
  certainty: Certainty;
  original: string;
  installment: string;
  note: string;
  tags: string[];
  invoice: string;
  document: string;
}

export interface RuleChangeOut {
  content: string;
  diff: string;
  changed: number;
  moves: CategoryMoveOut[];
  examples: ChangedRowOut[];
  saved: boolean;
  backup: string;
}

/** What a finished scan of Gmail searched, as the cursor said when it began. */
export interface ScannedIn {
  start_day: string;
  senders: string[];
}

export interface ScannedOut {
  history_due: boolean;
}

/**
 * A screen of the interface, as a link names it, and what the link's id holds there: document (a document's sha256, its
 * query's "satir" a row's fingerprint to open it at), documents, transaction (a row's fingerprint), transactions,
 * account (an account's id), accounts, month (YYYY-MM), invoice (a bill's or a receipt's key), invoices, subscription
 * (a series' id), calendar (a day, YYYY-MM-DD, or "" for the days from today on), forecast (an account's id), insights,
 * fx, todo (a kind of item to see to), system, notifications. A list screen opens with the link's query as its filters.
 */
export type Screen = "document" | "documents" | "transaction" | "transactions" | "account" | "accounts" | "month" | "invoice" | "invoices" | "subscription" | "calendar" | "forecast" | "insights" | "fx" | "todo" | "system" | "notifications";

export interface SeriesOut {
  id: string;
  payee: string;
  period: SeriesPeriod;
  status: SeriesStatus;
  note: string;
  category: string;
  necessity: Necessity | null;
  kind: TransactionKind;
  account: AccountRefOut;
  amount: MoneyOut;
  last_day: string;
  last_amount: MoneyOut;
  next_day: string | null;
  price_change: PriceChangeOut | null;
  listed: boolean;
  payments: PaymentOut[];
}

/** How far apart a series' payments are: about a month, half a year or a year. */
export type SeriesPeriod = "month" | "half_year" | "year";

/** Whether a regular or periodic payment still runs (docs/domain/interpretation.md, "Düzenli ödemeler"). */
export type SeriesStatus = "active" | "ended" | "cancelled" | "paid_after_cancel";

export interface ServiceOut {
  version: string;
  started_at: string;
  pid: number;
  home: string;
}

export interface SkippedOut {
  account: AccountRefOut;
  reason: string;
}

/** How a document reached the archive. */
export type SourceKind = "email" | "upload" | "inbox" | "import";

/**
 * Where a row is printed: a PDF page with the line's box (points from the page's top left) or its line in the page's
 * text, a spreadsheet's sheet and row, or a span of an e-mail's or HTML document's collapsed text.
 */
export interface SourceRefOut {
  page: number | null;
  box: number[] | null;
  line: number | null;
  sheet: string | null;
  row: number | null;
  span: number[] | null;
}

/** Money out tied to no day: the median month of the complete months named, spread over each month's days. */
export interface SpreadOut {
  monthly: MoneyOut;
  months: string[];
  after: string | null;
}

/** Where an account's forecast starts: the newest balance a document prints, moved by the evidence after it. */
export interface StartOut {
  balance: MoneyOut;
  stated: MoneyOut;
  day: string;
  source: "statement" | "notice";
  moves: number;
  through: string;
}

export interface StatementCheckOut {
  account: string;
  start: string | null;
  cut: string;
  printed: MoneyOut | null;
  counted: MoneyOut;
  verified: boolean;
  balance_checks: number[] | null;
  rows: number;
}

export interface SubscriptionsOut {
  window: string[];
  as_of: string;
  series: SeriesOut[];
  income: SeriesOut[];
  installments: InstallmentOut[];
}

export interface SystemOut {
  service: ServiceOut;
  documents: Record<string, number>;
  readers: ReaderHealthOut[];
  disk: DiskOut;
  queue: QueueOut;
  mail: iplikci__api__models__MailOut;
  backup: BackupHealthOut;
}

export interface TableOut {
  name: string;
  rows: string[][];
  more: boolean;
}

export interface TelegramCheckOut {
  paired: boolean;
}

export interface TelegramPairingOut {
  code: string;
  expires: string;
  bot: string;
  link: string;
}

export interface TelegramTokenIn {
  token: string;
}

export interface TelegramTokenOut {
  bot: string;
  in_keyring: boolean;
}

/** The steps a to-do offers (F19). */
export type TodoAction = "add_rule" | "upload" | "reparse" | "open" | "ask_claude" | "ignore";

export interface TodoIgnoredIn {
  key: string;
  ignored: boolean;
}

/** What keeps the data from being complete and right (F19): each a to-do with the step that settles it. */
export type TodoKind = "uncategorized" | "unmatched_evidence" | "unmatched_invoice" | "unverified_statement" | "missing_documents" | "unprocessed_document" | "orphan_annotation" | "format_alarm";

export interface TodoOut {
  key: string;
  kind: TodoKind;
  title: string;
  detail: string;
  count: number;
  amount: MoneyOut | null;
  target: string;
  link: LinkOut | null;
  actions: TodoAction[];
  prompt: string;
  ignored: boolean;
}

export interface TodosOut {
  items: TodoOut[];
  counts: Record<string, number>;
  ignored: number;
}

/**
 * What a row is. For every kind, an amount above zero is money leaving the user and below zero money coming in (a
 * refund, income, a transfer in).
 */
export type TransactionKind = "purchase" | "refund" | "interest_fee" | "p2p_transfer" | "loan_principal" | "cash_advance" | "investment" | "income" | "card_payment_no_statement" | "card_payment" | "own_transfer" | "transfer_candidate";

export interface UnknownMailOut {
  domain: string;
  template: string;
  count: number;
}

/** An account with no balance or statement to show, and why. */
export interface UnknownOut {
  account: AccountRefOut;
  reason: string;
}

export interface UploadOut {
  batch: string;
  status: "eklendi" | "zaten-var" | "reddedildi";
  name: string;
  reason: string;
}

export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}

export type ViewKind = "pdf" | "table" | "mail" | "html" | "text" | "none";

/** The days a document's bank row is looked for in. */
export interface WindowOut {
  start: string;
  end: string;
}

/** The whole rule file, as the user edited it. */
export interface WriteRulesIn {
  action: "write";
  content: string;
}

export interface iplikci__api__models__MailOut {
  connector: "imap" | "browser_bridge";
  configured: boolean;
  last_run: string;
  last_error: string;
  stopped: boolean;
  start_day: string;
  history_due: boolean;
  refused: RefusedMailOut[];
  coverage: MailCoverageOut;
}

export interface iplikci__api__routes__documents__MailOut {
  subject: string;
  sender: string;
  sent: string;
  lines: string[];
  text: string;
}

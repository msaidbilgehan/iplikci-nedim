// The service's API types, generated from its OpenAPI document by `iplikci dev api-tipleri` (ADR-0007).
// Do not edit by hand: change the API's models and generate again; a test keeps this file current.

/** An account's page (F07). */
export interface AccountDetailOut {
  account: AccountOut;
  rows: RowOut[];
  totals: TotalsOut;
  offset: number;
  next: number | null;
  curve: CurvePointOut[];
  curve_note: string;
  months: MonthTotalsOut[];
  fees: FeesOut;
  payments: SeriesOut[];
  income: SeriesOut[];
  card: CardPageOut | null;
  overdraft: OverdraftOut | null;
  deposit: DepositOut | null;
  holding: HoldingOut | null;
  brokerage: BrokerageOut | null;
  loan: LoanOut | null;
}

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

/**
 * The Accounts screen's groups (F07), in its order: a card of either kind is a card, every other account is grouped by
 * its type.
 */
export type AccountGroup = "cards" | "current" | "deposit" | "overdraft" | "fx" | "gold" | "brokerage" | "loan";

export interface AccountOut {
  account: AccountRefOut;
  label: string;
  alias: string;
  bank: string;
  type: AccountType;
  group: AccountGroup;
  balance: MoneyOut | null;
  value: MoneyOut | null;
  day: string | null;
  certainty: Certainty | null;
  note: string;
  freshness: FreshnessOut | null;
  month: MonthFlowOut;
  closed: boolean;
  link: LinkOut;
}

export interface AccountRefOut {
  id: string;
  label: string;
}

export type AccountType = "credit_card" | "debit_card" | "current" | "deposit" | "overdraft" | "fx" | "gold" | "brokerage" | "loan";

export interface AccountsOut {
  today: string;
  groups: GroupOut[];
  closed: AccountOut[];
  assets: MoneyOut;
  debts: MoneyOut;
  total: MoneyOut;
  note: string;
}

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

/** What an open alert is about. */
export type AlertKind = "finding" | "negative" | "unreadable" | "format_alarm" | "mail_stopped" | "bridge_silent" | "backup_failed";

export type AlertLevel = "warning" | "critical";

/** Something that asks for attention now. */
export interface AlertOut {
  kind: AlertKind;
  level: AlertLevel;
  title: string;
  text: string;
  count: number;
  account: AccountRefOut | null;
  link: LinkOut;
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

export interface AliasIn {
  alias: string;
}

export interface AliasOut {
  account: AccountRefOut;
  alias: string;
}

export interface AnnotationOut {
  note: string;
  tags: string[];
  category: string;
  necessity: Necessity | null;
  parts: SplitPartOut[];
  updated_at: string;
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

/** An asset or a debt. */
export interface AssetOut {
  account: AccountRefOut;
  group: AccountGroup;
  amount: MoneyOut;
  value: MoneyOut | null;
  rate: string | null;
  rate_day: string | null;
  cost: MoneyOut | null;
  gain: MoneyOut | null;
  day: string;
  certainty: Certainty;
  note: string;
  rate_source?: RateSource | null;
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

export interface BackupSettingsIn {
  keep_days: number;
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

export interface BillOut {
  key: string;
  seller: string;
  issued: string;
  total: MoneyOut;
}

export interface BridgeOut {
  id: string;
  name: string;
  created_at: string;
  last_seen: string;
  active: boolean;
}

export interface BrokerageOut {
  as_of: string | null;
  securities: SecurityOut[];
  cash: MoneyOut | null;
  worth: MoneyOut | null;
  dividends: MoneyOut;
  dividend_rows: number;
  note: string;
}

export interface BudgetLineOut {
  label: string;
  now: MoneyOut;
  plan: MoneyOut;
  note: string;
}

export interface BulkIn {
  fingerprints: string[];
  category?: string | null;
  tags?: string[];
}

export interface BulkOut {
  changed: number;
  skipped: string[];
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

export interface CardPageOut {
  statement: NowCardOut | null;
  statements: StatementOut[];
  installments: InstallmentOut[];
  schedule: ScheduleMonthOut[];
  left: MoneyOut;
}

/** A card's statement period and its spending (purchases, refunds, interest and fees). */
export interface CardPeriodOut {
  start: string;
  end: string;
  spent: MoneyOut;
  rows: number;
}

export interface CategoryLineOut {
  category: string;
  group: string;
  slot: number;
  total: MoneyOut;
  share: string | null;
  average: MoneyOut | null;
  count: number;
  link: LinkOut;
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

/** How a row got its category (docs/domain/categorization.md): the Transactions screen's "Neden?" (F04). */
export type CategoryReason = "rule" | "bank_category" | "weak_rule" | "invoice" | "transfer_rule" | "kind" | "fee" | "own_transfer" | "person" | "income" | "uncategorized" | "user" | "split";

export interface CategoryRulesOut {
  content: string;
  categories: CategoryOut[];
  ended: EndedOut[];
  merchant_necessity: MerchantNecessityOut[];
  history: string[];
}

/** How sure a row or a total is, and whether it counts (architecture §8). */
export type Certainty = "confirmed" | "provisional" | "excluded" | "info";

export interface ChangeOut {
  category: string;
  before: MoneyOut;
  recent: MoneyOut;
}

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

/** A month's closing (F11). */
export interface ClosingOut {
  month: string;
  status: MonthStatus;
  summary: string;
  expense: MoneyOut;
  out: MoneyOut;
  people: MoneyOut;
  debt: MoneyOut;
  saving: MoneyOut;
  income: MoneyOut | null;
  left: MoneyOut | null;
  income_note: string;
  provisional: number;
  unmatched: number;
  waiting: WaitingOut[];
  link: LinkOut;
}

/** A category of commitments (its payments are regular even when the amount changes), or no longer. */
export interface CommitmentIn {
  action: "commitment";
  category: string;
  on: boolean;
}

export interface ConnectionOut {
  address: string;
  name: string;
  helper: string;
  command: string;
  arguments: string[];
  claude_code: Record<string, unknown>;
  claude_desktop: Record<string, unknown>;
  sak_add: string;
  sak_remove: string;
  claude_add: string;
  masking: "off" | "accounts" | "accounts_and_names";
  development: boolean;
}

/**
 * What changes; a field left out stays. "" gives the category or the necessity back to the rules; [] joins a split row
 * again.
 */
export interface CorrectionIn {
  note?: string | null;
  tags?: string[] | null;
  category?: string | null;
  necessity?: Necessity | "" | null;
  parts?: PartIn[] | null;
}

export interface CoverOut {
  account: AccountRefOut;
  closed: boolean;
  shares: string[];
  link: LinkOut;
}

/** How much of each month each account's statements and account lists cover: the MVP report's coverage grid. */
export interface CoverageOut {
  months: string[];
  accounts: CoverOut[];
}

/** The assets held in one currency. */
export interface CurrencyShareOut {
  currency: string;
  amount: MoneyOut;
  value: MoneyOut | null;
  share: number | null;
  accounts: AccountRefOut[];
}

export interface CursorOut {
  last_id: string;
  last_date: string;
  start_day: string;
  senders: string[];
  history_due: boolean;
}

export interface CurvePointOut {
  day: string;
  balance: MoneyOut;
  certainty: Certainty;
}

export interface DashboardOut {
  today: string;
  as_of: string;
  net_worth: NetWorthOut;
  month: ThisMonthOut;
  due: DueSoonOut;
  alerts: OpenAlertsOut;
  closing: LastMonthsOut;
  freshness: DataFreshnessOut;
  todo: TodoSummaryOut;
  sayings: SayingOut[];
}

export interface DataFreshnessOut {
  accounts: FreshnessOut[];
  say: string;
  link: LinkOut;
}

export interface DeliveredOut {
  taken: string;
  documents: number;
}

/** Where a notification stands on its channel (ADR-0010). */
export type DeliveryStatus = "pending" | "sent" | "held" | "digested" | "failed";

export interface DepositOut {
  principal: MoneyOut | null;
  rate: string | null;
  maturity: string | null;
  interest: MoneyOut | null;
  note: string;
}

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

export interface DocumentMailOut {
  subject: string;
  sender: string;
  sent: string;
  lines: string[];
  text: string;
}

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
  accounts: NamedAccountOut[];
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
  mail: DocumentMailOut | null;
  text: string;
  has_html: boolean;
}

/**
 * The calendar's payments within a week that the user sees to: a card's due date, a bill, a loan's installment, a
 * regular or periodic payment made from an account (one a card pays comes with its statement).
 */
export interface DueSoonOut {
  items: CalendarItemOut[];
  total: MoneyOut;
  end: string;
  say: string;
  link: LinkOut;
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

/** The user's own EVDS key, as EVDS's profile page copies it; tried once, then kept in the keychain only. */
export interface EvdsIn {
  key: string;
}

/** Where TÜFE stands: whether a key is kept, the months fetched and the last attempt. The key is never sent back. */
export interface EvdsOut {
  has_key: boolean;
  months: number;
  first: string | null;
  newest: string | null;
  last_run: string;
  last_error: string;
  behind: boolean;
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

export interface ExtensionFolderOut {
  folder: string;
  version: string;
  opened: boolean;
}

export interface ExtensionOut {
  available: boolean;
  version: string;
  folder: string;
  current: boolean;
}

export interface FailedJobOut {
  id: number;
  kind: string;
  attempts: number;
  finished_at: string;
  error: string;
}

export interface FeeOut {
  category: string;
  amount: MoneyOut;
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

export interface FeesOut {
  months: string[];
  total: MoneyOut;
  categories: FeeOut[];
}

export interface FetchQueuedOut {
  queued: boolean;
}

export interface FindingOut {
  tone: Tone;
  title: string;
  text: string;
  link: LinkOut;
}

export interface FlowEdgeOut {
  source: string;
  target: string;
  amount: MoneyOut;
  rows: number;
  kinds: TransactionKind[];
  link: LinkOut;
}

/**
 * What a node of the flow between accounts is (F07's Sankey): one of the user's accounts, or where money came from or
 * went.
 */
export type FlowKind = "account" | "income" | "spending" | "people" | "saving" | "loan" | "cash" | "elsewhere";

export interface FlowMonthOut {
  month: string;
  partial: boolean;
  income: MoneyOut;
  expense: MoneyOut;
  net: MoneyOut;
  people: MoneyOut;
  debt: MoneyOut;
  saving: MoneyOut;
  left: MoneyOut;
}

export interface FlowNodeOut {
  id: string;
  kind: FlowKind;
  name: string;
  account: AccountRefOut | null;
}

/** Each a monthly average over the window's months. */
export interface FlowOut {
  months: string[];
  income: MoneyOut;
  expense: MoneyOut;
  people: MoneyOut;
  unnamed_people: MoneyOut;
  debt: MoneyOut;
  saving: MoneyOut;
  fx: MoneyOut;
  left: MoneyOut;
  debt_start: MoneyOut;
  debt_end: MoneyOut;
  other_typical: MoneyOut;
}

export interface FlowsOut {
  start: string;
  end: string;
  nodes: FlowNodeOut[];
  edges: FlowEdgeOut[];
  note: string;
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

/** The parts of the three-month spending forecast (docs/domain/interpretation.md, "Tahmin"). */
export type ForecastPart = "regular" | "installments" | "variable";

/** How far an account's documents reach. */
export interface FreshnessOut {
  account: AccountRefOut;
  kind: DocumentKind;
  document: string;
  name: string;
  last: string;
  behind: number;
  expected: string | null;
  late: boolean;
  missing: string[];
  note: string;
  link: LinkOut;
}

/** A sale of the currency for TL. */
export interface FxConversionOut {
  fingerprint: string;
  day: string;
  account: AccountRefOut;
  amount: MoneyOut;
  tl: MoneyOut;
  rate: string;
}

export interface FxCurrencyIncomeOut {
  currency: string;
  rate: FxRateOut | null;
  rows: FxIncomeRowOut[];
  received: MoneyOut;
  worth: MoneyOut | null;
  sold: FxConversionOut[];
  sensitivity: FxSensitivityOut | null;
  note: string;
}

export interface FxCurrencyOut {
  currency: string;
  newest: FxRateOut;
  history: FxRateOut[];
}

/** The income that comes in a foreign currency (F12), by currency. */
export interface FxIncomeOut {
  start: string;
  end: string;
  currencies: FxCurrencyIncomeOut[];
  note: string;
}

export interface FxIncomeRowOut {
  fingerprint: string;
  day: string;
  account: AccountRefOut;
  title: string;
  amount: MoneyOut;
  counted: MoneyOut;
  worth: MoneyOut | null;
}

export interface FxOut {
  currencies: FxCurrencyOut[];
  missing: string[];
  note: string;
}

export interface FxRateOut {
  day: string;
  rate: string;
  source: RateSource;
  buying?: string | null;
  selling?: string | null;
}

/** What a 5% move of the rate does to the monthly income: the average of complete months only. */
export interface FxSensitivityOut {
  months: string[];
  received: MoneyOut;
  monthly: MoneyOut;
  monthly_tl: MoneyOut | null;
  change: MoneyOut | null;
  say: string;
}

/** What the banks' rates cost against TCMB's in the last 12 months (F12). */
export interface FxSpreadOut {
  start: string;
  end: string;
  total: MoneyOut;
  trades: FxSpreadRowOut[];
  trades_total: MoneyOut;
  purchases: FxSpreadRowOut[];
  purchases_total: MoneyOut;
  left_out: number;
  note: string;
}

/** A row that shows a bank's rate, against TCMB's of its day in the trade's direction. */
export interface FxSpreadRowOut {
  fingerprint: string;
  day: string;
  account: AccountRefOut;
  title: string;
  side: TradeSide;
  amount: MoneyOut;
  tl: MoneyOut;
  rate: string;
  tcmb_rate: string;
  tcmb_day: string;
  cost: MoneyOut;
}

export interface GroupOut {
  group: AccountGroup;
  assets: MoneyOut;
  debts: MoneyOut;
  total: MoneyOut;
  unvalued: number;
  accounts: AccountOut[];
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

export interface HabitOut {
  name: string;
  category: string;
  necessity: Necessity | null;
  by_category: boolean;
  status: HabitStatus;
  pattern: string;
  count: number;
  months: number;
  span: number;
  total: MoneyOut;
  recent: MoneyOut;
  monthly: MoneyOut;
  last: string;
  link: LinkOut;
}

/** How a discretionary merchant or an avoidable cost goes over the window (docs/domain/interpretation.md). */
export type HabitStatus = "monthly" | "new" | "occasional" | "stopped" | "one_off";

/** A foreign currency or gold account. */
export interface HoldingOut {
  amount: MoneyOut | null;
  value: MoneyOut | null;
  rate: string | null;
  rate_day: string | null;
  cost: MoneyOut | null;
  gain: MoneyOut | null;
  note: string;
  rate_source?: RateSource | null;
}

export interface HoldingsOut {
  today: string;
  worth: WorthOut;
  holdings: AssetOut[];
  spread: CurrencyShareOut[];
  note: string;
}

export interface IdentityIn {
  names: string[];
  business_names: string[];
}

/** An account that allows app passwords: its address and app password, tried once. */
export interface ImapIn {
  address: string;
  password: string;
  start?: string | null;
}

export interface ImapOut {
  folder: string;
  in_keyring: boolean;
}

/**
 * The net worth in another unit: at the providers' newest selling rate (what buying it would cost), else at the newest
 * rate the documents print.
 */
export interface InCurrencyOut {
  currency: string;
  amount: MoneyOut | null;
  rate: string | null;
  rate_day: string | null;
  note: string;
  rate_source?: RateSource | null;
}

export interface IncomeOut {
  name: string;
  monthly: MoneyOut;
  last: string;
  status: SeriesStatus;
}

export interface InsightsOut {
  window: InsightsWindowOut;
  findings: FindingOut[];
  steps: StepOut[];
  budget: BudgetLineOut[];
  habits: HabitOut[];
  flow: FlowOut | null;
  trend: TrendOut | null;
  income: IncomeOut[];
  unusual: UnusualOut[];
}

export interface InsightsWindowOut {
  months: string[];
  as_of: string;
  last_complete: string;
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

export interface LastMonthsOut {
  months: ClosingOut[];
  say: string;
  link: LinkOut;
}

/** Where an item leads in the interface: a screen and what to open there (Screen names what id holds for each). */
export interface LinkOut {
  screen: Screen;
  id: string;
  query: Record<string, string | string[]>;
}

export interface LoanInstallmentOut {
  day: string;
  principal: MoneyOut;
  cost: MoneyOut;
  document: string;
  certainty: Certainty;
}

export interface LoanOut {
  installments: LoanInstallmentOut[];
  principal_paid: MoneyOut;
  interest_paid: MoneyOut;
  next: CalendarItemOut[];
  remaining: MoneyOut | null;
  note: string;
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

export interface MailOut {
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

export interface MailSettingsIn {
  connector?: "imap" | "browser_bridge" | null;
  start?: string | null;
}

export interface MailSettingsOut {
  connector: "imap" | "browser_bridge";
  configured: boolean;
  address: string;
  start: string;
  server: string;
  stopped: boolean;
  last_error: string;
}

export interface MaskingIn {
  masking: "off" | "accounts" | "accounts_and_names";
}

export interface MerchantLineOut {
  merchant: string;
  category: string;
  group: string;
  slot: number;
  count: number;
  total: MoneyOut;
  per_row: MoneyOut;
  last: string;
  link: LinkOut;
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

/** One account in one month. */
export interface MonthEndAccountOut {
  account: AccountRefOut;
  status: MonthStatus;
  label: string;
  blocking: boolean;
  needed: number;
  covered: number;
  open: MonthEndRangeOut[];
  statements: MonthEndStatementOut[];
  receipts: MonthEndReceiptsOut;
  balance: MoneyOut | null;
  last: string;
  next_cut: string | null;
  late: boolean;
  untracked: boolean;
  waiting_for: string;
  note: string;
}

export interface MonthEndDetailOut {
  month: MonthEndOut;
  previous: MonthEndTotalsOut | null;
  typical: MoneyOut | null;
  typical_months: number;
  accounts: MonthEndAccountOut[];
  groups: MonthEndShareOut[];
  levels: MonthEndShareOut[];
  categories: MonthEndShareOut[];
  merchants: MonthEndShareOut[];
  regular: MonthEndRegularOut[];
  big: RowOut[];
  provisional: RowOut[];
  unmatched: RowOut[];
  count: number;
  trend: MonthEndTrendOut[];
  debt_end: MoneyOut | null;
  previous_month: string;
  next_month: string;
  export: ExportKind;
}

export interface MonthEndListOut {
  today: string;
  months: MonthEndOut[];
  export: ExportKind;
}

export interface MonthEndOut {
  month: string;
  name: string;
  status: MonthStatus;
  summary: string;
  totals: MonthEndTotalsOut;
  provisional: number;
  unmatched: number;
  income_note: string;
  link: LinkOut;
}

export interface MonthEndRangeOut {
  start: string;
  end: string;
}

export interface MonthEndReceiptsOut {
  matched: number;
  provisional: number;
  unmatched: number;
  no_statement: number;
}

/** A regular payment this month: paid, or expected and not seen yet. */
export interface MonthEndRegularOut {
  payee: string;
  category: string;
  paid: RowOut[];
  expected: string | null;
  this_month: MoneyOut;
  monthly: MoneyOut;
}

export interface MonthEndShareOut {
  name: string;
  slot: number;
  amount: MoneyOut;
  count: number | null;
  code: string;
}

/** A statement or a list overlapping the month, with the days of the month it covers. */
export interface MonthEndStatementOut {
  start: string;
  end: string;
  cut: string;
  card: boolean;
  check: StatementCheck;
  document: string;
}

/** A month's totals by calendar month (docs/domain/interpretation.md, "Ay sonu kapanışı"). */
export interface MonthEndTotalsOut {
  expense: MoneyOut;
  income: MoneyOut | null;
  people: MoneyOut;
  debt: MoneyOut;
  saving: MoneyOut;
  fees: MoneyOut;
  left: MoneyOut | null;
}

export interface MonthEndTrendOut {
  month: string;
  expense: MoneyOut;
}

/** The money in and out of an account in the current month so far, counted rows only, in TL. */
export interface MonthFlowOut {
  month: string;
  money_in: MoneyOut;
  money_out: MoneyOut;
  rows: number;
  provisional: number;
  note: string;
}

export interface MonthRowOut {
  month: string;
  values: MoneyOut[];
  partial: boolean;
}

/** Month-end closing: of a month, and of each account within it. */
export type MonthStatus = "closed" | "waiting" | "missing" | "check" | "running";

export interface MonthTableOut {
  slices: SliceOut[];
  months: MonthRowOut[];
}

export interface MonthTotalsOut {
  month: string;
  money_in: MoneyOut;
  money_out: MoneyOut;
  rows: number;
  complete: boolean;
}

/** How the situation stands, as the Pano's verdicts colour it; the face takes its colour. */
export type Mood = "good" | "warning" | "critical" | "neutral";

export interface NamedAccountOut {
  id: string;
  label: string;
  bank: string;
}

export type Necessity = "required" | "optional" | "unnecessary" | "unknown";

/** Where a spending row's necessity comes from (docs/domain/categorization.md, "Gereklilik"). */
export type NecessityReason = "user" | "merchant" | "category" | "default";

/** The balances of "Şu an" and the cards' debts, added up: the assets less the debts, of what has a TL value. */
export interface NetWorthOut {
  total: MoneyOut;
  assets: MoneyOut;
  debts: MoneyOut;
  certainty: Certainty;
  parts: PartOut[];
  left_out: UnknownOut[];
  currencies: InCurrencyOut[];
  note: string;
  say: string;
  link: LinkOut;
}

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
  rate_source?: RateSource | null;
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

export interface OpenAlertsOut {
  items: AlertOut[];
  say: string;
  link: LinkOut;
}

export interface OtherSendersIn {
  domains: string[];
}

/** The domains whose bills and receipts are taken in beside the banks' messages (settings: mail.other_senders). */
export interface OtherSendersOut {
  domains: string[];
}

export interface OverdraftOut {
  limit: MoneyOut | null;
  used: MoneyOut;
  days_below: number;
  window_start: string | null;
  window_end: string | null;
  interest: MoneyOut;
  note: string;
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

/**
 * How a credit card statement was paid (F07's payment history): by the next statement's cut, or for the newest one, by
 * today.
 */
export type PaidStatus = "full" | "minimum" | "partial" | "unpaid" | "open" | "nothing_due";

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

/** A part of a split row: what of it counts under which category. */
export interface PartIn {
  minor: number;
  category: string;
  necessity?: Necessity | null;
}

/** An account's share of the net worth. */
export interface PartOut {
  account: AccountRefOut;
  value: MoneyOut;
  certainty: Certainty;
}

/** What an item of the calendar is (F09). */
export type PaymentKind = "regular" | "periodic" | "income" | "installment" | "loan" | "card_due" | "bill";

/** A row a series rests on, and the document it is printed in. */
export interface PaymentOut {
  fingerprint: string;
  day: string;
  amount: MoneyOut;
  document: string;
  sha256: string;
  certainty: Certainty;
}

export interface PeriodOut {
  start: string;
  end: string;
  first: string;
  last: string;
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

/** Where the row is printed; the viewer opens /belgeler/<document>?satir=<fingerprint> at it. */
export interface PrintedOut {
  document: string;
  name: string;
  kind: DocumentKind | null;
  page: number | null;
  line: number | null;
  sheet: string | null;
  row: number | null;
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

/** A line of İplikçi Nedim's; a dialogue's lines in turn, his first. */
export interface QuoteOut {
  id: string;
  lines: string[];
}

export interface RateDaysOut {
  source: RateSource;
  newest: string;
  days: number;
}

/**
 * Where a TL rate comes from (F12, architecture §15). A row's own rate always comes first; then TCMB's bulletin of the
 * day; ECB's reference rate, or Frankfurter's copy of it, when TCMB could not be reached. Without the network the
 * documents' own rates are used.
 */
export type RateSource = "document" | "tcmb" | "ecb" | "frankfurter";

export interface RatesFetchIn {
  history?: boolean;
}

/** Where the exchange rates stand (architecture §15). */
export interface RatesOut {
  providers: RateSource[];
  sources: RateDaysOut[];
  days: number;
  start: string | null;
  missing: number;
  last_run: string;
  last_error: string;
  summary: string;
}

export interface RatesQueuedOut {
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

/** The trend's averages at one month's prices with TÜFE (F12's V1+ part): only the months with an index. */
export interface RealTrendOut {
  base: string;
  before: string[];
  recent: string[];
  before_nominal: MoneyOut;
  recent_nominal: MoneyOut;
  before_real: MoneyOut;
  recent_real: MoneyOut;
  nominal_change: number | null;
  real_change: number | null;
  prices: number;
  missing: string[];
  say: string;
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

/** How the last restore went, as the start that tried it wrote it. */
export interface RestoreOutcomeOut {
  backup: string;
  ok: boolean;
  error: string;
  at: string;
}

export interface RestoringOut {
  backup: string;
  restarts: boolean;
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
  split_of: string;
  split_parts: number;
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

/** The rule file a category rule is in (docs/domain/categorization.md): the user's own goes above the shipped. */
export type RuleLayer = "own" | "shipped";

/**
 * İplikçi Nedim's word on the money (F06): a line of his, the situation it is said about and how that stands. The
 * browser extension shows it too, so it carries no amount, account or name (ADR-0020).
 */
export interface SayingOut {
  situation: Situation;
  mood: Mood;
  reason: string;
  quote: QuoteOut;
}

export interface SayingsOut {
  items: SayingOut[];
}

/** What a finished scan of Gmail searched, as the cursor said when it began. */
export interface ScannedIn {
  start_day: string;
  senders: string[];
}

export interface ScannedOut {
  history_due: boolean;
}

export interface ScheduleMonthOut {
  month: string;
  amount: MoneyOut;
  count: number;
}

/**
 * A screen of the interface, as a link names it, and what the link's id holds there: document (a document's sha256, its
 * query's "satir" a row's fingerprint to open it at), documents, transaction (a row's fingerprint), transactions,
 * account (an account's id), accounts, month (YYYY-MM), invoice (a bill's or a receipt's key), invoices, subscription
 * (a series' id), calendar (a day, YYYY-MM-DD, or "" for the days from today on), forecast (an account's id), insights,
 * fx, todo (a kind of item to see to), system, notifications. A list screen opens with the link's query as its filters.
 */
export type Screen = "document" | "documents" | "transaction" | "transactions" | "account" | "accounts" | "month" | "invoice" | "invoices" | "subscription" | "calendar" | "forecast" | "insights" | "fx" | "todo" | "system" | "notifications";

export interface SecurityOut {
  code: string;
  name: string;
  quantity: string;
  value: MoneyOut;
  as_of: string;
}

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

export interface ServiceEndingOut {
  ending: boolean;
  restarts: boolean;
}

export interface ServiceOut {
  version: string;
  started_at: string;
  pid: number;
  home: string;
}

export interface ServiceRemoveIn {
  data_to_trash?: boolean;
}

export interface ServiceStateOut {
  version: string;
  started_at: string;
  registered: boolean;
  manager: string;
  can_end: boolean;
  restore: RestoreOutcomeOut | null;
}

export interface SettingsOut {
  home: string;
  port: number;
  names: string[];
  business_names: string[];
  mail: MailSettingsOut;
  bank_senders: string[];
  backup_days: number;
}

export interface SetupOut {
  steps: SetupStepOut[];
  first_run: boolean;
}

/** The setup wizard's steps (F17), in its order. */
export type SetupStep = "data_folder" | "names" | "business_names" | "mail" | "senders" | "documents" | "notifications" | "service" | "remote";

export interface SetupStepOut {
  step: SetupStep;
  done: boolean;
  optional: boolean;
  note: string;
}

/** What a line is said about; listed most pressing first. */
export type Situation = "going_negative" | "overspent" | "in_debt" | "spending_more" | "thin" | "best_month" | "foreign_income" | "spending_less" | "saving" | "income_arrived" | "good" | "price_rise" | "fees" | "quiet" | "no_data";

export interface SkippedOut {
  account: AccountRefOut;
  reason: string;
}

export interface SliceOut {
  key: string;
  slot: number;
}

export type Sort = "day" | "amount" | "title" | "category" | "account";

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

export interface SpendingForecastLineOut {
  part: ForecastPart;
  label: string;
  note: string;
  necessity: Necessity;
  group: string;
  slot: number;
  amounts: MoneyOut[];
  link: LinkOut | null;
}

export interface SpendingForecastOut {
  base: string[];
  months: string[];
  lines: SpendingForecastLineOut[];
  totals: MoneyOut[];
  by_level: MonthTableOut;
  actual: MonthTableOut;
  income: MoneyOut;
  income_names: string[];
  saving: MoneyOut;
  saving_names: string[];
  other: MoneyOut;
  left: MoneyOut | null;
}

export interface SpendingOut {
  period: PeriodOut | null;
  tiles: TilesOut;
  by_group: MonthTableOut;
  by_level: MonthTableOut;
  categories: CategoryLineOut[];
  merchants: MerchantLineOut[];
  flow: FlowMonthOut[];
  forecast: SpendingForecastOut | null;
}

/** A part as the user split the row: the detail's parts are what the ledger counts of them. */
export interface SplitPartOut {
  minor: number;
  category: string;
  necessity: Necessity | null;
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

/** A statement's own check on the month-end page (docs/domain/interpretation.md, "Ay sonu kapanışı"). */
export type StatementCheck = "verified" | "failed" | "nothing";

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

/** A card statement on the card's timeline. */
export interface StatementOut {
  cut: string;
  start: string;
  end: string;
  total: MoneyOut | null;
  due: string | null;
  minimum: MoneyOut | null;
  limit: MoneyOut | null;
  rows: number;
  spent: MoneyOut;
  verified: boolean;
  document: string;
  paid: MoneyOut | null;
  status: PaidStatus | null;
}

export interface StepOut {
  title: string;
  text: string;
  monthly: MoneyOut | null;
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
  mail: MailOut;
  backup: BackupHealthOut;
  rates?: RatesOut | null;
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

/** The month's spending so far against the typical month (complete months only). */
export interface ThisMonthOut {
  pace: PaceOut;
  say: string;
  link: LinkOut;
}

export interface TilesOut {
  total: MoneyOut;
  count: number;
  average: MoneyOut | null;
  average_months: number;
  partial_months: number;
  income_average: MoneyOut | null;
  income_months: number;
  income_share: string | null;
  unnecessary: MoneyOut;
  last_month: string | null;
  last_total: MoneyOut;
  last_partial: boolean;
  last_change: string | null;
  last_base_months: number;
}

/** The steps a to-do offers (F19). */
export type TodoAction = "add_rule" | "upload" | "reparse" | "open" | "ask_claude" | "ignore";

export interface TodoCountOut {
  kind: TodoKind;
  count: number;
  link: LinkOut;
}

export interface TodoIgnoredIn {
  key: string;
  ignored: boolean;
}

/** What keeps the data from being complete and right (F19): each a to-do with the step that settles it. */
export type TodoKind = "uncategorized" | "unmatched_evidence" | "unmatched_invoice" | "unverified_statement" | "missing_documents" | "unprocessed_document" | "orphan_annotation" | "split_dropped" | "format_alarm";

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

export interface TodoSummaryOut {
  kinds: TodoCountOut[];
  total: number;
  say: string;
  link: LinkOut;
}

export interface TodosOut {
  items: TodoOut[];
  counts: Record<string, number>;
  ignored: number;
}

export interface TokenOut {
  token: string;
}

export interface ToldOut {
  fingerprint: string;
  status: EvidenceStatus;
  day: string;
  amount: MoneyOut;
  printed: PrintedOut | null;
}

/** How a finding reads. */
export type Tone = "attention" | "info" | "good";

export interface TotalsOut {
  count: number;
  counted: number;
  spent: MoneyOut;
  money_out: MoneyOut;
  money_in: MoneyOut;
  provisional: number;
  excluded: number;
}

/**
 * Which way a currency changed hands for TL (docs/domain/interpretation.md, "Kur makası"): it decides which of TCMB's
 * two rates the bank's rate is compared with.
 */
export type TradeSide = "buy" | "sell";

export interface TransactionDetailOut {
  row: RowOut;
  printed: PrintedOut | null;
  why: WhyOut;
  told: ToldOut[];
  bill: BillOut | null;
  annotation: AnnotationOut | null;
  correctable: boolean;
  parts: RowOut[];
  splittable: boolean;
  split_dropped: boolean;
}

/**
 * What a row is. For every kind, an amount above zero is money leaving the user and below zero money coming in (a
 * refund, income, a transfer in).
 */
export type TransactionKind = "purchase" | "refund" | "interest_fee" | "p2p_transfer" | "loan_principal" | "cash_advance" | "investment" | "income" | "card_payment_no_statement" | "card_payment" | "own_transfer" | "transfer_candidate";

export interface TransactionsOut {
  rows: RowOut[];
  totals: TotalsOut;
  offset: number;
  next: number | null;
}

/**
 * How the ledger resolved a row that moves money to or from someone its reader could not name (docs/domain/ledger.md,
 * transfers), in the order the ledger tries them.
 */
export type TransferStep = "own_name" | "own_account" | "rule" | "like_named" | "paired" | "uncovered_bank" | "person" | "income";

export interface TrendOut {
  before: string[];
  recent: string[];
  before_average: MoneyOut;
  recent_average: MoneyOut;
  usual_before: MoneyOut;
  usual_recent: MoneyOut;
  changes: ChangeOut[];
  large: RowOut[];
  threshold: MoneyOut;
  real?: RealTrendOut | null;
  real_note?: string;
}

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

/** A movement worth a look (F10). It is only flagged: no row is ever dropped for it. */
export type UnusualKind = "unusual_amount" | "possible_duplicate" | "new_large" | "unexpected_fee";

export interface UnusualOut {
  kind: UnusualKind;
  row: RowOut;
  text: string;
  link: LinkOut;
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

export interface ViewModel {
  name: string;
  query: Record<string, string[]>;
}

export interface WaitingOut {
  account: AccountRefOut;
  waiting_for: string;
}

export interface WhyOut {
  category: CategoryReason;
  rule: string;
  layer: RuleLayer | null;
  necessity: NecessityReason | null;
  necessity_layer: RuleLayer | null;
  transfer: TransferStep | null;
  pair: RowOut | null;
  rate: string | null;
  rate_day: string | null;
  rate_source?: RateSource | null;
}

/** The days a document's bank row is looked for in. */
export interface WindowOut {
  start: string;
  end: string;
}

/** The assets less the debts, of what has a TL value: the dashboard's net worth. */
export interface WorthOut {
  total: MoneyOut;
  assets: MoneyOut;
  debts: MoneyOut;
  certainty: Certainty;
  parts: PartOut[];
  left_out: UnknownOut[];
  currencies: InCurrencyOut[];
  note: string;
}

/** The whole rule file, as the user edited it. */
export interface WriteRulesIn {
  action: "write";
  content: string;
}

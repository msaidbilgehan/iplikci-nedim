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

export interface AppliedOut {
  stored: number;
  counts: Record<string, number>;
  trash: string | null;
}

export interface ApplyIn {
  plan_id: string;
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

/** How sure a row or a total is, and whether it counts (architecture §8). */
export type Certainty = "confirmed" | "provisional" | "excluded" | "info";

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

export interface DiskOut {
  vault: number;
  database: number;
  free: number;
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
}

export interface DocumentPageOut {
  items: DocumentOut[];
  next: string;
}

export interface EventOut {
  id: number;
  at: string;
  kind: string;
  target: string;
  detail: Record<string, unknown>;
}

export interface FailedJobOut {
  id: number;
  kind: string;
  attempts: number;
  finished_at: string;
  error: string;
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

/**
 * An amount in its currency's smallest unit: {"minor": 123456, "currency": "TRY"} is 1.234,56 TL. The interface formats
 * it (architecture §16).
 */
export interface MoneyOut {
  minor: number;
  currency: string;
}

export type Necessity = "required" | "optional" | "unnecessary" | "unknown";

export interface OtherSendersIn {
  domains: string[];
}

/** The domains whose bills and receipts are taken in beside the banks' messages (settings: mail.other_senders). */
export interface OtherSendersOut {
  domains: string[];
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

/** What a finished scan of Gmail searched, as the cursor said when it began. */
export interface ScannedIn {
  start_day: string;
  senders: string[];
}

export interface ScannedOut {
  history_due: boolean;
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

/** The days a document's bank row is looked for in. */
export interface WindowOut {
  start: string;
  end: string;
}

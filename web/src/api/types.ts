// The names the screens give the service's answers. The shapes come from the API's OpenAPI document (schema.ts, made
// by `uv run iplikci dev api-tipleri`, ADR-0007). Codes travel in the data; their Turkish labels come from
// /api/labels. Times are ISO 8601 strings, sizes are bytes, amounts are minor units with their currency.

import type {
  AccountForecastOut,
  AccountOut,
  AccountRefOut,
  AccountsOut,
  AlertOut,
  AnnotationOut,
  AlertPreviewOut,
  AlertRuleModel,
  AlertRulesOut,
  AppliedOut,
  BridgeOut,
  BulkOut,
  CalendarItemOut,
  CalendarOut,
  CategoryOut,
  CategoryRulesOut,
  Certainty,
  Channel,
  ChannelStage,
  ChannelStateOut,
  ClosingOut,
  CorrectionIn,
  DashboardOut,
  DeliveryStatus,
  DetailLevel,
  DocumentDetailOut,
  DocumentOut,
  DocumentPageOut,
  DocumentViewOut,
  EventInfoOut,
  EventKind,
  EventOut,
  ExportKind,
  ExportOut,
  ExportsQueuedOut,
  FeedDetailOut,
  FeedItemOut,
  FeedOut,
  ForecastOut,
  FreshnessOut,
  InstallmentOut,
  InvoiceOut,
  InvoicesOut,
  LabelsOut,
  LinkOut,
  MailCoverageOut,
  MerchantRuleIn,
  MoneyOut,
  Necessity,
  NetWorthOut,
  NotificationOut,
  NotificationsOut,
  NotificationsReadOut,
  NotifySettingsIn,
  NotifySettingsOut,
  NowBalanceOut,
  NowCardOut,
  NowOut,
  OtherSendersOut,
  PaceOut,
  PageLinesOut,
  PairingOut,
  PlanOut,
  PrintedOut,
  QueuedOut,
  RefusedMailOut,
  RowOut,
  RuleChangeOut,
  SeriesOut,
  SubscriptionsOut,
  SystemOut,
  TelegramCheckOut,
  TelegramPairingOut,
  TelegramTokenOut,
  TodoSummaryOut,
  TotalsOut,
  TransactionDetailOut,
  TransactionsOut,
  UploadOut,
  ViewModel,
} from "./schema";

export type SystemStatus = SystemOut;
export type { ExportKind }; // the report, the rows as CSV and as Excel, the month-end pages (F20)
export type ExportItem = ExportOut;
export type ExportsQueued = ExportsQueuedOut;
export type DocumentItem = DocumentOut;
export type DocumentPage = DocumentPageOut;
export type Labels = LabelsOut;
export type Pairing = PairingOut;
export type Bridge = BridgeOut;
export type Uploaded = UploadOut;
export type Plan = PlanOut;
export type Applied = AppliedOut;
export type LoggedEvent = EventOut;
export type Queued = QueuedOut;
export type RefusedMail = RefusedMailOut;
export type MailCoverage = MailCoverageOut;
export type Money = MoneyOut;
export type { Certainty }; // how sure a row or a total is, and whether it counts (architecture §8)
export type Subscriptions = SubscriptionsOut;
export type Series = SeriesOut;
export type Installment = InstallmentOut;
export type Calendar = CalendarOut;
export type CalendarItem = CalendarItemOut;
export type Forecast = ForecastOut;
export type AccountForecast = AccountForecastOut;
export type Invoices = InvoicesOut;
export type InvoiceItem = InvoiceOut;
export type OtherSenders = OtherSendersOut;

// The notifications (F13, ADR-0010). The codes keep the API's names; Pairing above is the browser extension's.
export type { Channel, ChannelStage, DeliveryStatus, DetailLevel, EventKind };
export type NotificationItem = NotificationOut;
export type Notifications = NotificationsOut;
export type NotificationsMarked = NotificationsReadOut;
export type NotifySettings = NotifySettingsOut;
export type NotifyPreferences = NotifySettingsIn;
export type ChannelState = ChannelStateOut;
export type AlertRule = AlertRuleModel;
export type AlertRules = AlertRulesOut;
export type AlertEvent = EventInfoOut;
export type AlertPreview = AlertPreviewOut;
export type TelegramBot = TelegramTokenOut;
export type TelegramPairing = TelegramPairingOut;
export type TelegramCheck = TelegramCheckOut;

// Where an item leads (app/links.py): lib/links.ts turns it into an address of the interface.
export type Destination = LinkOut;
export type AccountRef = AccountRefOut;
export type Row = RowOut;
export type Pace = PaceOut;

// The feed (F05): the event log a page at a time, and what stands now.
export type FeedPage = FeedOut;
export type FeedItem = FeedItemOut;
export type FeedDetail = FeedDetailOut;
export type Now = NowOut;
export type NowBalance = NowBalanceOut;
export type NowCard = NowCardOut;

// The accounts in their groups (F07).
export type Accounts = AccountsOut;
export type AccountItem = AccountOut;

// The Transactions screen (F04): the rows a filter keeps with their totals, one row with why it is what it is, the
// corrections, the kept views; and the category rules a correction may become.
export type TransactionPage = TransactionsOut;
export type Totals = TotalsOut;
export type TransactionDetail = TransactionDetailOut;
export type Annotation = AnnotationOut;
export type Correction = CorrectionIn;
export type SavedView = ViewModel;
export type BulkResult = BulkOut;
export type CategoryRules = CategoryRulesOut;
export type Category = CategoryOut;
export type MerchantRule = MerchantRuleIn;
export type RuleChange = RuleChangeOut;
export type { Necessity };

// A document as the viewer shows it, and where its rows are printed (F03).
export type DocumentDetail = DocumentDetailOut;
export type DocumentView = DocumentViewOut;
export type PageLines = PageLinesOut;
export type Printed = PrintedOut;

// The dashboard (F06): every card with its plain-view sentence (`say`) and the screen it leads to (`link`).
export type Dashboard = DashboardOut;
export type NetWorth = NetWorthOut;
export type OpenAlert = AlertOut;
export type MonthClosing = ClosingOut;
export type Freshness = FreshnessOut;
export type TodoSummary = TodoSummaryOut;

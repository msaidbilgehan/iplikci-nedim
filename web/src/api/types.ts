// The names the screens give the service's answers. The shapes come from the API's OpenAPI document (schema.ts, made
// by `uv run iplikci dev api-tipleri`, ADR-0007). Codes travel in the data; their Turkish labels come from
// /api/labels. Times are ISO 8601 strings, sizes are bytes, amounts are minor units with their currency.

import type {
  AccountDetailOut,
  AccountForecastOut,
  AccountGroup,
  AccountOut,
  AccountRefOut,
  AccountsOut,
  AliasOut,
  BrokerageOut,
  BudgetLineOut,
  CardPageOut,
  ConnectionOut,
  CategoryLineOut,
  CurvePointOut,
  DepositOut,
  FeesOut,
  FindingOut,
  FlowEdgeOut,
  FlowKind,
  FlowMonthOut,
  FlowNodeOut,
  FlowOut,
  FlowsOut,
  ForecastPart,
  GroupOut,
  HabitOut,
  HabitStatus,
  HoldingOut,
  InsightsOut,
  LoanOut,
  MerchantLineOut,
  MonthRowOut,
  MonthTableOut,
  MonthTotalsOut,
  OverdraftOut,
  PaidStatus,
  PeriodOut,
  SpendingForecastLineOut,
  SpendingForecastOut,
  SpendingOut,
  StatementOut,
  AlertOut,
  AnnotationOut,
  AlertPreviewOut,
  AlertRuleModel,
  AlertRulesOut,
  AppliedOut,
  AssetOut,
  ArrivalOut,
  BackupOut,
  BridgeOut,
  BulkOut,
  CalendarItemOut,
  CalendarOut,
  CategoryMoveOut,
  CategoryOut,
  CategoryRulesOut,
  CurrencyShareOut,
  Certainty,
  ChangedRowOut,
  Channel,
  ChannelStage,
  ChannelStateOut,
  ClosingOut,
  CommitmentIn,
  CorrectionIn,
  DashboardOut,
  DeliveryStatus,
  DetailLevel,
  DocumentDetailOut,
  DocumentOut,
  DocumentPageOut,
  DocumentRowOut,
  DocumentViewOut,
  EndedIn,
  EndedOut,
  EventInfoOut,
  EventKind,
  EventOut,
  EvdsOut,
  ExportKind,
  ExportOut,
  ExportsQueuedOut,
  ExtensionFolderOut,
  ExtensionOut,
  FeedDetailOut,
  FeedItemOut,
  FeedOut,
  ForecastOut,
  FreshnessOut,
  FxConversionOut,
  FxCurrencyIncomeOut,
  FxCurrencyOut,
  FxIncomeOut,
  FxIncomeRowOut,
  FxOut,
  FxRateOut,
  FxSensitivityOut,
  FxSpreadOut,
  FxSpreadRowOut,
  HoldingsOut,
  ImapOut,
  InstallmentOut,
  InvoiceOut,
  InvoicesOut,
  LabelsOut,
  LinkOut,
  CoverageOut,
  CoverOut,
  MailCoverageOut,
  MailSettingsIn,
  MailSettingsOut,
  MerchantNecessityIn,
  MerchantNecessityOut,
  MerchantRuleIn,
  MoneyOut,
  MonthEndAccountOut,
  MonthEndDetailOut,
  MonthEndListOut,
  MonthEndOut,
  MonthEndRegularOut,
  MonthEndShareOut,
  MonthEndTotalsOut,
  MonthStatus,
  Necessity,
  NetWorthOut,
  NotEndedIn,
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
  PaymentOut,
  PlanOut,
  PrintedOut,
  QueuedOut,
  RateDaysOut,
  RateSource,
  RatesOut,
  RealTrendOut,
  RatesQueuedOut,
  RefusedMailOut,
  RemovedOut,
  ReparsedOut,
  RestoringOut,
  RowOut,
  RuleChangeOut,
  SeriesOut,
  SeriesStatus,
  ServiceEndingOut,
  ServiceStateOut,
  SettingsOut,
  SetupOut,
  SetupStep,
  SetupStepOut,
  SourceRefOut,
  StatementCheckOut,
  StepOut,
  SubscriptionsOut,
  SystemOut,
  TelegramCheckOut,
  TelegramPairingOut,
  TelegramTokenOut,
  TokenOut,
  TilesOut,
  TodoAction,
  TodoKind,
  TodoOut,
  TodosOut,
  TodoSummaryOut,
  Tone,
  TotalsOut,
  TransactionDetailOut,
  TransactionsOut,
  TrendOut,
  UnusualKind,
  UnusualOut,
  UploadOut,
  ViewKind,
  ViewModel,
  WriteRulesIn,
} from "./schema";

export type SystemStatus = SystemOut;
export type { ExportKind }; // the report, the rows as CSV and as Excel, the month-end pages (F20)
export type ExportItem = ExportOut;
export type ExportsQueued = ExportsQueuedOut;
export type DocumentItem = DocumentOut;
export type DocumentPage = DocumentPageOut;
export type Labels = LabelsOut;
export type Pairing = PairingOut;
export type ExtensionInfo = ExtensionOut; // the extension the program carries and its folder (K20)
export type ExtensionFolder = ExtensionFolderOut;
export type Bridge = BridgeOut;
export type Uploaded = UploadOut;
export type Plan = PlanOut;
export type Applied = AppliedOut;
export type LoggedEvent = EventOut;
export type Queued = QueuedOut;
export type RefusedMail = RefusedMailOut;
export type MailCoverage = MailCoverageOut;
export type Coverage = CoverageOut;
export type AccountCover = CoverOut;
export type Money = MoneyOut;
export type { Certainty }; // how sure a row or a total is, and whether it counts (architecture §8)
export type Subscriptions = SubscriptionsOut;
export type Series = SeriesOut;
export type Payment = PaymentOut; // a row a series rests on
export type Installment = InstallmentOut;
export type { SeriesStatus };
export type Calendar = CalendarOut;
export type CalendarItem = CalendarItemOut;
export type Forecast = ForecastOut;
export type AccountForecast = AccountForecastOut;
export type Invoices = InvoicesOut;
export type InvoiceItem = InvoiceOut;
export type OtherSenders = OtherSendersOut;
export type McpConnection = ConnectionOut; // Claude's connection (K23): no secret in it
export type McpToken = TokenOut; // the API token, shown when the user asks
export type McpMasking = ConnectionOut["masking"];

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

// The Hesaplar screens (F07): the accounts in their groups, an account's page with what its type adds, the name the
// user gives one, and where the money went between them.
export type AccountGroupItem = GroupOut;
export type AccountPage = AccountDetailOut;
export type CurvePoint = CurvePointOut;
export type MonthTotals = MonthTotalsOut;
export type Fees = FeesOut;
export type CardPage = CardPageOut;
export type Statement = StatementOut;
export type Overdraft = OverdraftOut;
export type Deposit = DepositOut;
export type Holding = HoldingOut;
export type Brokerage = BrokerageOut;
export type Loan = LoanOut;
export type Alias = AliasOut;
export type Flows = FlowsOut;
export type FlowNode = FlowNodeOut;
export type FlowEdge = FlowEdgeOut;
export type { AccountGroup, FlowKind, PaidStatus };

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
// The payments the user ended (`_biten`): "İptal ettim" writes one, "Yeniden bekle" takes the user's own back.
export type EndedPayment = EndedOut;
export type EndedRule = EndedIn;
export type NotEndedRule = NotEndedIn;
// The edits the screens preview, then write: a merchant rule, an ended payment and its undoing, and the Rules
// screen's commitment category, merchant's own necessity and whole file.
export type RuleEdit =
  | MerchantRule
  | EndedRule
  | NotEndedRule
  | CommitmentIn
  | MerchantNecessityIn
  | WriteRulesIn;

// A document as the viewer shows it, and where its rows are printed (F03).
export type DocumentDetail = DocumentDetailOut;
export type DocumentView = DocumentViewOut;
export type DocumentRow = DocumentRowOut;
export type DocumentCheck = StatementCheckOut;
export type Arrival = ArrivalOut;
export type SourceRef = SourceRefOut;
export type PageLines = PageLinesOut;
export type Printed = PrintedOut;
export type Reparsed = ReparsedOut;
export type Removed = RemovedOut;
export type { ViewKind };

// The Değerlendirme screen (F10): the spending the filters keep, card by card, and the interpretation no filter
// changes, each part with its window and numbers.
export type Spending = SpendingOut;
export type SpendingTiles = TilesOut;
export type SpendingPeriod = PeriodOut;
export type MonthTable = MonthTableOut;
export type MonthRow = MonthRowOut;
export type CategoryLine = CategoryLineOut;
export type MerchantLine = MerchantLineOut;
export type FlowMonth = FlowMonthOut;
export type SpendingForecast = SpendingForecastOut;
export type ForecastLine = SpendingForecastLineOut;
export type Insights = InsightsOut;
export type Finding = FindingOut;
export type InsightStep = StepOut;
export type BudgetLine = BudgetLineOut;
export type Habit = HabitOut;
export type MoneyFlow = FlowOut;
export type Trend = TrendOut;
export type Unusual = UnusualOut;
export type { ForecastPart, HabitStatus, Tone, UnusualKind };

// The dashboard (F06): every card with its plain-view sentence (`say`) and the screen it leads to (`link`).
export type Dashboard = DashboardOut;
export type NetWorth = NetWorthOut;
// Döviz (F12, its Phase 6 part): the net worth in TL and the other units, every asset and debt, the currencies' shares
// and the rates the documents print.
export type Holdings = HoldingsOut;
export type Asset = AssetOut; // an asset or a debt, with its value and cost where known
export type CurrencyShare = CurrencyShareOut;
export type FxRates = FxOut;
export type CurrencyRates = FxCurrencyOut;
export type FxRate = FxRateOut;
// Phase 8: where a rate comes from (a row's own document, TCMB, ECB, or Frankfurter's copy of ECB's), what the banks'
// rates cost against TCMB's, the income that comes in a foreign currency and where the stored rates stand.
export type { RateSource };
export type FxSpread = FxSpreadOut;
export type FxSpreadRow = FxSpreadRowOut;
export type FxIncome = FxIncomeOut;
export type CurrencyIncome = FxCurrencyIncomeOut;
export type IncomeRow = FxIncomeRowOut;
export type Conversion = FxConversionOut;
export type Sensitivity = FxSensitivityOut;
export type RatesState = RatesOut;
export type RateDays = RateDaysOut;
export type RatesQueued = RatesQueuedOut;
// TÜFE from EVDS with the user's own key (F12's V1+ part): where it stands, and the spending trend at one month's
// prices that it makes possible on Değerlendirme.
export type EvdsState = EvdsOut;
export type RealTrend = RealTrendOut;
export type OpenAlert = AlertOut;
export type MonthClosing = ClosingOut;
export type Freshness = FreshnessOut;
export type TodoSummary = TodoSummaryOut;

// The month-end closing (F11): the months with their statuses, and one month in full — each account's closing and what
// it waits for, the totals, where the money went, the regular payments and the rows receipts and notices show.
export type { MonthStatus };
export type MonthEndList = MonthEndListOut;
export type MonthEnd = MonthEndOut;
export type MonthEndDetail = MonthEndDetailOut;
export type MonthEndAccount = MonthEndAccountOut;
export type MonthEndTotals = MonthEndTotalsOut;
export type MonthEndShare = MonthEndShareOut;
export type MonthEndRegular = MonthEndRegularOut;

// The Rules screen (F15): a merchant weighed apart from its category, and what a change would move — the rows, from
// which category to which.
export type MerchantNecessity = MerchantNecessityOut;
export type CategoryMove = CategoryMoveOut;
export type ChangedRow = ChangedRowOut;

// The to-do list (F19): what keeps the data from being complete and right, each item with the steps that settle it.
// A kind or a step this version does not know yet is shown by its label from /api/labels.
export type { TodoAction, TodoKind };
export type Todos = TodosOut;
export type TodoItem = TodoOut;

// The setup wizard and the Settings screen (F17): where each step stands, and the settings with no secret in them,
// the e-mail address masked as the service gives it.
export type { SetupStep };
export type Setup = SetupOut;
export type SetupStepState = SetupStepOut;
export type Settings = SettingsOut;
export type MailSettings = MailSettingsOut;
export type MailChange = MailSettingsIn;
export type ImapSetUp = ImapOut;

// The service's own life (ADR-0017): its state, the answer of a step that ends it, the backups and one being put back.
export type ServiceState = ServiceStateOut;
export type ServiceEnding = ServiceEndingOut;
export type BackupItem = BackupOut;
export type Restoring = RestoringOut;

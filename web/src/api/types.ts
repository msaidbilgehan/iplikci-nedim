// The names the screens give the service's answers. The shapes come from the API's OpenAPI document (schema.ts, made
// by `uv run iplikci dev api-tipleri`, ADR-0007). Codes travel in the data; their Turkish labels come from
// /api/labels. Times are ISO 8601 strings, sizes are bytes, amounts are minor units with their currency.

import type {
  AccountForecastOut,
  AccountOut,
  AccountRefOut,
  AccountsOut,
  AlertPreviewOut,
  AlertRuleModel,
  AlertRulesOut,
  AppliedOut,
  BridgeOut,
  CalendarItemOut,
  CalendarOut,
  Certainty,
  Channel,
  ChannelStage,
  ChannelStateOut,
  DeliveryStatus,
  DetailLevel,
  DocumentOut,
  DocumentPageOut,
  EventInfoOut,
  EventKind,
  EventOut,
  FeedDetailOut,
  FeedItemOut,
  FeedOut,
  ForecastOut,
  InstallmentOut,
  InvoiceOut,
  InvoicesOut,
  LabelsOut,
  LinkOut,
  MailCoverageOut,
  MoneyOut,
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
  PairingOut,
  PlanOut,
  QueuedOut,
  RefusedMailOut,
  RowOut,
  SeriesOut,
  SubscriptionsOut,
  SystemOut,
  TelegramCheckOut,
  TelegramPairingOut,
  TelegramTokenOut,
  UploadOut,
} from "./schema";

export type SystemStatus = SystemOut;
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

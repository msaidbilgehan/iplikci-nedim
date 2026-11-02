// The names the screens give the service's answers. The shapes come from the API's OpenAPI document (schema.ts, made
// by `uv run iplikci dev api-tipleri`, ADR-0007). Codes travel in the data; their Turkish labels come from
// /api/labels. Times are ISO 8601 strings, sizes are bytes, amounts are minor units with their currency.

import type {
  AccountForecastOut,
  AlertPreviewOut,
  AlertRuleModel,
  AlertRulesOut,
  AppliedOut,
  BridgeOut,
  CalendarItemOut,
  CalendarOut,
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
  ForecastOut,
  InstallmentOut,
  InvoiceOut,
  InvoicesOut,
  LabelsOut,
  MailCoverageOut,
  MoneyOut,
  NotificationOut,
  NotificationsOut,
  NotificationsReadOut,
  NotifySettingsIn,
  NotifySettingsOut,
  OtherSendersOut,
  PairingOut,
  PlanOut,
  QueuedOut,
  RefusedMailOut,
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

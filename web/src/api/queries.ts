// The server state the screens read, through TanStack Query. The event stream invalidates these keys when the
// service records something new (useEventStream), so the screens stay current without polling hard.

import { type QueryClient, useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type {
  Accounts,
  AlertPreview,
  AlertRule,
  AlertRules,
  Bridge,
  Calendar,
  Channel,
  Dashboard,
  DocumentPage,
  FeedPage,
  Forecast,
  Invoices,
  Labels,
  Notifications,
  NotificationsMarked,
  NotifyPreferences,
  NotifySettings,
  Now,
  OtherSenders,
  Pairing,
  Queued,
  Subscriptions,
  SystemStatus,
  TelegramBot,
  TelegramCheck,
  TelegramPairing,
} from "./types";

export const keys = {
  system: ["system"] as const,
  labels: ["labels"] as const,
  feedAll: ["feed"] as const, // the events and what stands now: every event of the stream refreshes them
  feed: (filter: FeedFilter) => ["feed", "events", filter] as const,
  now: ["feed", "now"] as const,
  accounts: ["accounts"] as const,
  dashboard: ["dashboard"] as const,
  documents: (filter: DocumentFilter) => ["documents", filter] as const,
  allDocuments: ["documents"] as const,
  bridges: ["bridges"] as const,
  subscriptions: ["subscriptions"] as const,
  calendar: ["calendar"] as const,
  forecast: ["forecast"] as const,
  invoices: ["invoices"] as const,
  otherSenders: ["settings", "mail", "other-senders"] as const,
  notifications: ["notifications"] as const, // the box and the history both
  notificationBox: ["notifications", "in_app"] as const,
  notificationLog: ["notifications", "all"] as const,
  notifySettings: ["notify", "settings"] as const,
  alertRules: ["rules", "alerts"] as const,
};

const OTHER_SENDERS = "/api/settings/mail/other-senders";

export type DocumentFilter = "all" | "unprocessed";

const FILTER_STATUSES: Record<DocumentFilter, string[]> = {
  all: [],
  unprocessed: ["unprocessed", "unreadable"],
};

export function useSystem() {
  return useQuery({
    queryKey: keys.system,
    queryFn: () => api.get<SystemStatus>("/api/system"),
    refetchInterval: 30_000, // the queue moves without events too
  });
}

/** The Turkish labels of every code type; they change only with a new version of the service. */
export function useLabels() {
  return useQuery({
    queryKey: keys.labels,
    queryFn: () => api.get<Labels>("/api/labels"),
    staleTime: Number.POSITIVE_INFINITY,
  });
}

export function useDocuments(filter: DocumentFilter) {
  return useInfiniteQuery({
    queryKey: keys.documents(filter),
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ limit: "50" });
      for (const status of FILTER_STATUSES[filter]) {
        params.append("status", status);
      }
      if (pageParam) {
        params.set("cursor", pageParam);
      }
      return api.get<DocumentPage>(`/api/documents?${params.toString()}`);
    },
    initialPageParam: "",
    getNextPageParam: (last) => last.next || undefined,
  });
}

export function useBridges() {
  return useQuery({ queryKey: keys.bridges, queryFn: () => api.get<Bridge[]>("/api/bridge") });
}

// --- the feed (F05) ----------------------------------------------------------------------------------------------

const FEED_PAGE = 50;

/** What the feed is narrowed to, in the API's names: null for no filter, [] for none chosen (nothing to ask). */
export type FeedFilter = {
  account: string[] | null;
  kind: string[] | null; // event codes ("transaction.created") or families ("document")
  certainty: string[] | null;
};

/** Whether filters leave nothing to show: one of them has none of its choices chosen. */
export function choosesNothing(filters: Record<string, string[] | null>): boolean {
  return Object.values(filters).some((values) => values !== null && values.length === 0);
}

/**
 * The event log newest first, a page at a time; `next` is the next page's `before`. A narrow filter may give a page
 * shorter than its limit with more still to read: only a null `next` ends the feed. The event stream refreshes every
 * page as events come (useEventStream), each page found again from the one before it.
 */
export function useFeed(filter: FeedFilter) {
  return useInfiniteQuery({
    queryKey: keys.feed(filter),
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ limit: String(FEED_PAGE) });
      if (pageParam > 0) {
        params.set("before", String(pageParam));
      }
      for (const [name, values] of Object.entries(filter)) {
        for (const value of values ?? []) {
          params.append(name, value);
        }
      }
      return api.get<FeedPage>(`/api/feed?${params.toString()}`);
    },
    initialPageParam: 0,
    getNextPageParam: (last) => (last.next !== null && last.next > 0 ? last.next : undefined),
    enabled: !choosesNothing(filter),
  });
}

/** What stands now: the balances as far as the documents tell, the cards, the month's pace and the next 14 days. */
export function useNow() {
  return useQuery({ queryKey: keys.now, queryFn: () => api.get<Now>("/api/feed/now") });
}

/** The accounts in their groups with their balances and freshness, and the closed ones apart (F07). */
export function useAccounts() {
  return useQuery({ queryKey: keys.accounts, queryFn: () => api.get<Accounts>("/api/accounts") });
}

/** The dashboard's cards as of today, each with its sentence and the screen it leads to (F06). */
export function useDashboard() {
  return useQuery({ queryKey: keys.dashboard, queryFn: () => api.get<Dashboard>("/api/dashboard") });
}

/** The monthly and periodic payments, the regular income and the installments left (F08). */
export function useSubscriptions() {
  return useQuery({ queryKey: keys.subscriptions, queryFn: () => api.get<Subscriptions>("/api/subscriptions") });
}

/** The next 60 days' expected payments and income, from today (F09). */
export function useCalendar() {
  return useQuery({ queryKey: keys.calendar, queryFn: () => api.get<Calendar>("/api/calendar") });
}

/** Each bank account's balance day by day for the next 60 days: an estimate (F09). */
export function useForecast() {
  return useQuery({ queryKey: keys.forecast, queryFn: () => api.get<Forecast>("/api/forecast") });
}

/** The bills and receipts non-bank senders mailed, each with what the bank's rows say of it (F14). */
export function useInvoices() {
  return useQuery({ queryKey: keys.invoices, queryFn: () => api.get<Invoices>("/api/invoices") });
}

/** The domains whose bills and receipts are taken in beside the banks' messages (F14). */
export function useOtherSenders() {
  return useQuery({ queryKey: keys.otherSenders, queryFn: () => api.get<OtherSenders>(OTHER_SENDERS) });
}

/** Save the whole list of non-bank senders; a new list makes the history be read again (the System screen says so). */
export function useSetOtherSenders() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (domains: string[]) => api.put<OtherSenders>(OTHER_SENDERS, { domains }),
    onSuccess: (saved) => {
      client.setQueryData(keys.otherSenders, saved);
      void client.invalidateQueries({ queryKey: keys.system });
    },
  });
}

export function useStartPairing() {
  return useMutation({ mutationFn: () => api.post<Pairing>("/api/bridge/pairings") });
}

export function useRevokeBridge() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/bridge/${encodeURIComponent(id)}`),
    onSettled: () => client.invalidateQueries({ queryKey: keys.bridges }),
  });
}

export function useBackupNow() {
  return useMutation({ mutationFn: () => api.post<Queued>("/api/backups") });
}

// --- notifications (F13, ADR-0010) ---------------------------------------------------------------------------------

const NOTIFICATIONS = "/api/notifications";
const NOTIFY_SETTINGS = "/api/notify/settings";
const TELEGRAM = "/api/notify/telegram";
const ALERT_RULES = "/api/rules/alerts";
const BOX_PAGE = 20;
const LOG_PAGE = 50;

function notificationPage(limit: number, before: number, channel?: Channel): Promise<Notifications> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (channel) {
    params.set("channel", channel);
  }
  if (before) {
    params.set("before", String(before));
  }
  return api.get<Notifications>(`${NOTIFICATIONS}?${params.toString()}`);
}

/** Where the next page starts, as the service said; none after the last page. */
function nextPage(page: Notifications): number | undefined {
  return page.next ?? undefined;
}

/**
 * The interface's notification box, newest first, a page at a time; the menu shows its unread count. The event
 * stream tells when a notification is made (useEventStream), so the box is not asked again on a timer.
 */
export function useNotificationBox() {
  return useInfiniteQuery({
    queryKey: keys.notificationBox,
    queryFn: ({ pageParam }) => notificationPage(BOX_PAGE, pageParam, "in_app"),
    initialPageParam: 0,
    getNextPageParam: nextPage,
  });
}

/** How many notifications in the box are not seen yet. */
export function useUnreadNotifications(): number {
  return useNotificationBox().data?.pages[0]?.unread ?? 0;
}

/** Every channel's notifications as they were sent, failed or kept back: the history, newest first. */
export function useNotificationLog() {
  return useInfiniteQuery({
    queryKey: keys.notificationLog,
    queryFn: ({ pageParam }) => notificationPage(LOG_PAGE, pageParam),
    initialPageParam: 0,
    getNextPageParam: nextPage,
  });
}

function refreshNotifications(client: QueryClient): void {
  void client.invalidateQueries({ queryKey: keys.notifications });
  void client.invalidateQueries({ queryKey: keys.notifySettings }); // its unread count and the channels' state
}

/** The box seen up to the newest notification shown: one that arrives meanwhile stays unread. */
export function useMarkNotificationsRead() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (upTo: number) => api.post<NotificationsMarked>(`${NOTIFICATIONS}/read`, { up_to: upTo }),
    onSettled: () => refreshNotifications(client),
  });
}

/** The quiet hours, each channel's level of detail and state, and what a channel still needs in the service's words. */
export function useNotifySettings() {
  return useQuery({ queryKey: keys.notifySettings, queryFn: () => api.get<NotifySettings>(NOTIFY_SETTINGS) });
}

export function useSetNotifySettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (preferences: NotifyPreferences) => api.put<NotifySettings>(NOTIFY_SETTINGS, preferences),
    onSuccess: (saved) => client.setQueryData(keys.notifySettings, saved),
  });
}

/** A test notification now on a channel; the in-app one lands in the box, and a stopped channel is tried again. */
export function useTestNotification() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (channel: Channel) => api.post<void>("/api/notify/test", { channel }),
    onSettled: () => refreshNotifications(client),
  });
}

/**
 * Check a bot's token with Telegram and keep it in the keyring. A plain call, not a mutation: a mutation keeps its
 * variables in the client's cache, and the token must not stay in the page once it is sent.
 */
export async function sendTelegramToken(client: QueryClient, token: string): Promise<TelegramBot> {
  const bot = await api.post<TelegramBot>(`${TELEGRAM}/token`, { token });
  void client.invalidateQueries({ queryKey: keys.notifySettings });
  return bot;
}

/** A code the user sends the bot as "/start <code>" within ten minutes. */
export function useStartTelegramPairing() {
  return useMutation({ mutationFn: () => api.post<TelegramPairing>(`${TELEGRAM}/pairing`) });
}

/** Whether the open code reached the bot; the service reads the bot's new messages once per call. */
export function checkTelegramPairing(): Promise<TelegramCheck> {
  return api.post<TelegramCheck>(`${TELEGRAM}/check`);
}

/** Forget the bot's token and the paired chat. */
export function useRemoveTelegram() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete(TELEGRAM),
    onSettled: () => client.invalidateQueries({ queryKey: keys.notifySettings }),
  });
}

/** The alert rules (the user's or the shipped ones) and the events a rule may watch with the conditions each allows. */
export function useAlertRules() {
  return useQuery({ queryKey: keys.alertRules, queryFn: () => api.get<AlertRules>(ALERT_RULES) });
}

/** Save the whole list of rules; the service checks it first and refuses it whole, saying why. */
export function useSetAlertRules() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (rules: AlertRule[]) => api.put<AlertRules>(ALERT_RULES, { rules }),
    onSuccess: (saved) => client.setQueryData(keys.alertRules, saved),
  });
}

/** How often a rule would have spoken in the last 30 days, with its newest texts; nothing is saved. */
export function usePreviewAlertRule() {
  return useMutation({
    mutationFn: (rule: AlertRule) => api.post<AlertPreview>(`${ALERT_RULES}/preview`, { rule }),
  });
}

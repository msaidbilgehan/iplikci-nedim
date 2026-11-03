// The server state the screens read, through TanStack Query. The event stream invalidates these keys when the
// service records something new (useEventStream), so the screens stay current without polling hard.

import {
  keepPreviousData,
  type QueryClient,
  useInfiniteQuery,
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { api, ApiError } from "./client";
import type {
  AccountPage,
  Accounts,
  Alias,
  AlertPreview,
  AlertRule,
  AlertRules,
  Annotation,
  BackupItem,
  Bridge,
  BulkResult,
  Calendar,
  CategoryRules,
  Channel,
  Correction,
  Coverage,
  Dashboard,
  DocumentDetail,
  DocumentPage,
  DocumentView,
  ExportItem,
  ExportsQueued,
  ExtensionFolder,
  EvdsState,
  ExtensionInfo,
  FxIncome,
  FxRates,
  FxSpread,
  FeedPage,
  Flows,
  Forecast,
  Holdings,
  ImapSetUp,
  Insights,
  Invoices,
  Labels,
  MailChange,
  MerchantRule,
  MonthEndDetail,
  MonthEndList,
  Notifications,
  NotificationsMarked,
  NotifyPreferences,
  NotifySettings,
  Now,
  McpConnection,
  McpMasking,
  McpToken,
  OtherSenders,
  PageLines,
  Pairing,
  Queued,
  RatesQueued,
  Removed,
  Reparsed,
  Restoring,
  RuleChange,
  RuleEdit,
  SavedView,
  ServiceEnding,
  ServiceState,
  Settings,
  Setup,
  Spending,
  Subscriptions,
  SystemStatus,
  TelegramBot,
  TelegramCheck,
  TelegramPairing,
  Todos,
  TransactionDetail,
  TransactionPage,
} from "./types";

export const keys = {
  system: ["system"] as const,
  exports: ["system", "exports"] as const, // under the System screen's key: every event refreshes it too
  labels: ["labels"] as const,
  feedAll: ["feed"] as const, // the events and what stands now: every event of the stream refreshes them
  feed: (filter: FeedFilter) => ["feed", "events", filter] as const,
  now: ["feed", "now"] as const,
  accounts: ["accounts"] as const, // the list, every account's page and the flows between them
  account: (id: string, offset: number) =>
    ["accounts", "page", id, offset] as const,
  flows: (from: string, to: string) => ["accounts", "flows", from, to] as const,
  coverage: ["accounts", "coverage"] as const,
  dashboard: ["dashboard"] as const,
  allTransactions: ["transactions"] as const, // the lists and the rows' details: a new analysis moves them
  transactions: (query: string) => ["transactions", "list", query] as const,
  transaction: (fingerprint: string) =>
    ["transactions", "row", fingerprint] as const,
  views: ["views", "transactions"] as const, // the user's own, which no analysis moves
  allSpending: ["spending"] as const, // the Değerlendirme screen's cards, every filter's: a new analysis moves them
  spending: (query: string) => ["spending", query] as const,
  insights: ["insights"] as const,
  categoryRules: ["rules", "categories"] as const,
  documentDetail: (sha256: string) => ["documents", sha256, "detail"] as const,
  documentView: (sha256: string) => ["documents", sha256, "view"] as const,
  pageLines: (sha256: string, page: number) =>
    ["documents", sha256, "lines", page] as const,
  documents: (query: string) => ["documents", "list", query] as const,
  allDocuments: ["documents"] as const, // the lists and every document's detail: a reading or an analysis moves them
  bridges: ["bridges"] as const,
  extension: ["extension"] as const,
  subscriptions: ["subscriptions"] as const,
  calendar: ["calendar"] as const,
  forecast: ["forecast"] as const,
  holdings: ["holdings"] as const,
  fx: ["fx"] as const, // the rates; and as a prefix, the spread and the foreign income too: an analysis moves them
  fxSpread: ["fx", "spread"] as const,
  fxIncome: ["fx", "income"] as const,
  invoices: ["invoices"] as const,
  otherSenders: ["settings", "mail", "other-senders"] as const,
  mcpConnection: ["mcp", "connection"] as const,
  notifications: ["notifications"] as const, // the box and the history both
  notificationBox: ["notifications", "in_app"] as const,
  notificationLog: ["notifications", "all"] as const,
  notifySettings: ["notify", "settings"] as const,
  alertRules: ["rules", "alerts"] as const,
};

const OTHER_SENDERS = "/api/settings/mail/other-senders";
const MCP_CONNECTION = "/api/mcp/connection";

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

/**
 * The kept documents a query keeps (the filters in the API's names and the page's size), newest first, a page at a
 * time by the service's cursor; nothing is asked while a filter chooses none.
 */
export function useDocuments(query: string, enabled = true) {
  return useInfiniteQuery({
    queryKey: keys.documents(query),
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams(query);
      if (pageParam) {
        params.set("cursor", pageParam);
      }
      return api.get<DocumentPage>(`/api/documents?${params.toString()}`);
    },
    initialPageParam: "",
    getNextPageParam: (last) => last.next || undefined,
    placeholderData: keepPreviousData, // another filter's documents stay, dimmed, until its own arrive
    enabled,
  });
}

export function useBridges() {
  return useQuery({
    queryKey: keys.bridges,
    queryFn: () => api.get<Bridge[]>("/api/bridge"),
  });
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
export function choosesNothing(
  filters: Record<string, string[] | null>,
): boolean {
  return Object.values(filters).some(
    (values) => values !== null && values.length === 0,
  );
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
    getNextPageParam: (last) =>
      last.next !== null && last.next > 0 ? last.next : undefined,
    enabled: !choosesNothing(filter),
  });
}

/** What stands now: the balances as far as the documents tell, the cards, the month's pace and the next 14 days. */
export function useNow() {
  return useQuery({
    queryKey: keys.now,
    queryFn: () => api.get<Now>("/api/feed/now"),
  });
}

/** The accounts in their groups with their balances and freshness, and the closed ones apart (F07). */
export function useAccounts() {
  return useQuery({
    queryKey: keys.accounts,
    queryFn: () => api.get<Accounts>("/api/accounts"),
  });
}

export const ACCOUNT_ROWS = 50; // an account page's rows a page at a time

/** An account's page: its card, its rows a page at a time, its balance by day, its months and what its type adds. */
export function useAccount(id: string, offset: number) {
  return useQuery({
    queryKey: keys.account(id, offset),
    queryFn: () =>
      api.get<AccountPage>(
        `/api/accounts/${encodeURIComponent(id)}?offset=${offset}&limit=${ACCOUNT_ROWS}`,
      ),
    placeholderData: keepPreviousData,
  });
}

/** Where the money went between the accounts from one day to another; the service's window when none is given. */
export function useFlows(from: string, to: string) {
  const params = new URLSearchParams();
  if (from) {
    params.set("from", from);
  }
  if (to) {
    params.set("to", to);
  }
  return useQuery({
    queryKey: keys.flows(from, to),
    queryFn: () => api.get<Flows>(`/api/accounts/flows?${params.toString()}`),
    placeholderData: keepPreviousData,
  });
}

/** How much of each month each account's statements and account lists cover: the MVP report's coverage grid. */
export function useCoverage() {
  return useQuery({
    queryKey: keys.coverage,
    queryFn: () => api.get<Coverage>("/api/accounts/coverage"),
  });
}

/**
 * Give an account a name of the user's own, or take it away with "". Every screen that names the account asks again:
 * the accounts, the rows, what stands now and the dashboard.
 */
export function useRename(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (alias: string) =>
      api.put<Alias>(`/api/accounts/${encodeURIComponent(id)}/alias`, {
        alias,
      }),
    onSuccess: () => {
      for (const key of [
        keys.accounts,
        keys.allTransactions,
        keys.feedAll,
        keys.dashboard,
      ]) {
        void client.invalidateQueries({ queryKey: key });
      }
    },
  });
}

/** The dashboard's cards as of today, each with its sentence and the screen it leads to (F06). */
export function useDashboard() {
  return useQuery({
    queryKey: keys.dashboard,
    queryFn: () => api.get<Dashboard>("/api/dashboard"),
  });
}

// --- the Transactions screen (F04) ----------------------------------------------------------------------------------

const TRANSACTIONS = "/api/transactions";
const VIEWS = `${TRANSACTIONS}/views`;
const CATEGORY_RULES = "/api/rules/categories";
// The service makes its analysis again in the background after a correction: the rows show it a moment later.
const SETTLING_MS = [1_500, 4_000, 9_000] as const;

/**
 * The rows the filters keep, a page at a time, with what they all add up to; query is the API's query string (its
 * filters, sort and page). Paging and sorting keep the rows shown until the next ones come. Not asked when a filter
 * has nothing chosen: nothing could match.
 */
export function useTransactions(query: string, enabled = true) {
  return useQuery({
    queryKey: keys.transactions(query),
    queryFn: () => api.get<TransactionPage>(`${TRANSACTIONS}?${query}`),
    placeholderData: keepPreviousData,
    enabled,
  });
}

/** One row with where it is printed and why it is what it is; none asked without a fingerprint. */
export function useTransaction(fingerprint: string) {
  return useQuery({
    queryKey: keys.transaction(fingerprint),
    queryFn: () =>
      api.get<TransactionDetail>(
        `${TRANSACTIONS}/${encodeURIComponent(fingerprint)}`,
      ),
    enabled: fingerprint !== "",
  });
}

/** The rows and their details asked again now and as the service's new analysis settles. */
export function refreshTransactions(client: QueryClient): void {
  void client.invalidateQueries({ queryKey: keys.allTransactions });
  for (const after of SETTLING_MS) {
    setTimeout(
      () => void client.invalidateQueries({ queryKey: keys.allTransactions }),
      after,
    );
  }
}

/** A detail with a correction's note and tags in it, as the row will have them. */
function withNote(
  detail: TransactionDetail,
  change: Correction,
): TransactionDetail {
  const note = change.note ?? detail.row.note;
  const tags = change.tags ?? detail.row.tags;
  const nothing = {
    note: "",
    tags: [],
    category: "",
    necessity: null,
    parts: [],
    updated_at: "",
  };
  const annotation = detail.annotation ?? nothing;
  return {
    ...detail,
    row: { ...detail.row, note, tags },
    annotation: { ...annotation, note, tags },
  };
}

/**
 * Correct one row: its note, tags, category or necessity. A note or tags show at once and go back if the service
 * refuses them (architecture §18: the only changes shown before the service has them); a category or a necessity
 * shows as the service's new analysis settles.
 */
export function useCorrection(fingerprint: string) {
  const client = useQueryClient();
  const key = keys.transaction(fingerprint);
  return useMutation({
    mutationFn: (change: Correction) =>
      api.put<Annotation | null>(
        `${TRANSACTIONS}/${encodeURIComponent(fingerprint)}/annotation`,
        change,
      ),
    onMutate: async (change) => {
      if (change.note == null && change.tags == null) {
        return { before: undefined };
      }
      await client.cancelQueries({ queryKey: key });
      const before = client.getQueryData<TransactionDetail>(key);
      if (before) {
        client.setQueryData(key, withNote(before, change));
      }
      return { before };
    },
    onError: (_error, _change, context) => {
      if (context?.before) {
        client.setQueryData(key, context.before);
      }
    },
    onSuccess: (annotation) => {
      client.setQueryData<TransactionDetail>(key, (was) =>
        was ? { ...was, annotation } : was,
      );
    },
    onSettled: () => refreshTransactions(client),
  });
}

/** Give the selected rows one category, or add tags to theirs. */
export function useBulkCorrection() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (change: {
      fingerprints: string[];
      category?: string;
      tags?: string[];
    }) => api.post<BulkResult>(`${TRANSACTIONS}/bulk`, change),
    onSettled: () => refreshTransactions(client),
  });
}

/** The filters the user kept under names. */
export function useSavedViews() {
  return useQuery({
    queryKey: keys.views,
    queryFn: () => api.get<SavedView[]>(VIEWS),
  });
}

/** Keep the filters under a name; the same name replaces the view kept before. */
export function useSaveView() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (view: SavedView) => api.put<SavedView[]>(VIEWS, view),
    onSuccess: (views) => client.setQueryData(keys.views, views),
  });
}

/** Forget a kept view; the service answers with the views left. */
export function useRemoveView() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (name: string) =>
      api.delete<SavedView[]>(`${VIEWS}/${encodeURIComponent(name)}`),
    onSuccess: (views) => client.setQueryData(keys.views, views),
  });
}

/** The categories with their groups, colours and necessity, the user's rule file and its history (F15). */
export function useCategoryRules() {
  return useQuery({
    queryKey: keys.categoryRules,
    queryFn: () => api.get<CategoryRules>(CATEGORY_RULES),
  });
}

/**
 * What a rule edit would do: the rule file's difference and the rows it moves, from which category to which (an
 * ended payment moves none). Nothing saved.
 */
export function usePreviewRule() {
  return useMutation({
    mutationFn: (rule: RuleEdit) =>
      api.post<RuleChange>(`${CATEGORY_RULES}/preview`, rule),
  });
}

/**
 * Save a rule edit: the service writes it and makes its analysis again before it answers, then says what moved. The
 * rows, the bills' matches, the regular payments and what they expect are asked again.
 */
export function useSaveRule() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (rule: RuleEdit) => api.put<RuleChange>(CATEGORY_RULES, rule),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.categoryRules });
      void client.invalidateQueries({ queryKey: keys.invoices }); // the new analysis matches the bills again
      refreshTransactions(client);
      refreshOutlook(client);
    },
  });
}

/**
 * What a new analysis moves beyond the rows: the regular payments, the days ahead and the balances they expect, what
 * stands now, the dashboard, the accounts' pages (which list the payments made from them) and the assessment.
 */
export function refreshOutlook(client: QueryClient): void {
  for (const key of [
    keys.subscriptions,
    keys.calendar,
    keys.forecast,
    keys.feedAll,
    keys.dashboard,
    keys.accounts,
    keys.allSpending,
    keys.insights,
  ]) {
    void client.invalidateQueries({ queryKey: key });
  }
}

// --- the Değerlendirme screen (F10) ---------------------------------------------------------------------------------

/**
 * The spending the filters keep, card by card (query is the Transactions screen's filters, in the API's names). The
 * cards keep showing while another filter's arrive.
 */
export function useSpending(query: string, enabled = true) {
  return useQuery({
    queryKey: keys.spending(query),
    queryFn: () => api.get<Spending>(`/api/spending?${query}`),
    placeholderData: keepPreviousData,
    enabled,
  });
}

/** The interpretation over the complete months, which no filter changes. */
export function useInsights() {
  return useQuery({
    queryKey: keys.insights,
    queryFn: () => api.get<Insights>("/api/insights"),
  });
}

/**
 * The totals of the rows of each kind the spending leaves out, as the Transactions screen counts them with the same
 * filters (query, without a kind) and one kind each: what "Toplama dahil değil" offers to add.
 */
export function useKindTotals(
  query: string,
  kinds: readonly string[],
  enabled = true,
) {
  return useQueries({
    queries: kinds.map((kind) => {
      const params = new URLSearchParams(query);
      params.set("kind", kind);
      params.set("limit", "1");
      const asked = params.toString();
      return {
        queryKey: keys.transactions(asked),
        queryFn: () => api.get<TransactionPage>(`${TRANSACTIONS}?${asked}`),
        placeholderData: keepPreviousData,
        enabled,
      };
    }),
  });
}

// --- a document as the viewer shows it (F03) ------------------------------------------------------------------------

const DOCUMENTS = "/api/documents";

/** A kept document: what it is, how it arrived, and the rows read from it with where each is printed. */
export function useDocumentDetail(sha256: string, enabled = true) {
  return useQuery({
    queryKey: keys.documentDetail(sha256),
    queryFn: () => api.get<DocumentDetail>(`${DOCUMENTS}/${sha256}`),
    enabled: enabled && sha256 !== "",
  });
}

/** How the viewer shows a document: a PDF's page sizes, a sheet's cells, an e-mail's text. */
export function useDocumentView(sha256: string) {
  return useQuery({
    queryKey: keys.documentView(sha256),
    queryFn: () => api.get<DocumentView>(`${DOCUMENTS}/${sha256}/view`),
    enabled: sha256 !== "",
  });
}

/** A PDF page's text line by line, for a row placed by its line. */
export function usePageLines(sha256: string, page: number, enabled = true) {
  return useQuery({
    queryKey: keys.pageLines(sha256, page),
    queryFn: () =>
      api.get<PageLines>(`${DOCUMENTS}/${sha256}/pages/${page}/lines`),
    enabled: enabled && sha256 !== "" && page > 0,
  });
}

/**
 * Read a document again now: the status it has after; "removed" when it turned out to be a company's (ADR-0003). The
 * analysis follows in the background and the event stream says when it is done.
 */
export function useReparse() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (sha256: string) =>
      api.post<Reparsed>(`${DOCUMENTS}/${sha256}/reparse`),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.allDocuments });
      void client.invalidateQueries({ queryKey: keys.system });
    },
  });
}

/** Move a document to the system Trash once the user confirmed it (F03, ADR-0003); its rows leave the ledger. */
export function useRemoveDocument() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (sha256: string) =>
      api.post<Removed>(`${DOCUMENTS}/${sha256}/remove`),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.allDocuments });
      void client.invalidateQueries({ queryKey: keys.system });
    },
  });
}

/** The monthly and periodic payments, the regular income and the installments left (F08). */
export function useSubscriptions() {
  return useQuery({
    queryKey: keys.subscriptions,
    queryFn: () => api.get<Subscriptions>("/api/subscriptions"),
  });
}

/** The next 60 days' expected payments and income, from today (F09). */
export function useCalendar() {
  return useQuery({
    queryKey: keys.calendar,
    queryFn: () => api.get<Calendar>("/api/calendar"),
  });
}

/** Each bank account's balance day by day for the next 60 days: an estimate (F09). */
export function useForecast() {
  return useQuery({
    queryKey: keys.forecast,
    queryFn: () => api.get<Forecast>("/api/forecast"),
  });
}

/** The bills and receipts non-bank senders mailed, each with what the bank's rows say of it (F14). */
export function useInvoices() {
  return useQuery({
    queryKey: keys.invoices,
    queryFn: () => api.get<Invoices>("/api/invoices"),
  });
}

/** The domains whose bills and receipts are taken in beside the banks' messages (F14). */
export function useOtherSenders() {
  return useQuery({
    queryKey: keys.otherSenders,
    queryFn: () => api.get<OtherSenders>(OTHER_SENDERS),
  });
}

/** Save the whole list of non-bank senders; a new list makes the history be read again (the System screen says so). */
export function useSetOtherSenders() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (domains: string[]) =>
      api.put<OtherSenders>(OTHER_SENDERS, { domains }),
    onSuccess: (saved) => {
      client.setQueryData(keys.otherSenders, saved);
      void client.invalidateQueries({ queryKey: keys.system });
    },
  });
}

/** What connects Claude (K23): the MCP address, the headers helper, the ready configurations; never the token. */
export function useMcpConnection() {
  return useQuery({
    queryKey: keys.mcpConnection,
    queryFn: () => api.get<McpConnection>(MCP_CONNECTION),
  });
}

/** The API token, asked for when the user presses "Göster": a write, so only the interface's own pages get it. */
export function useRevealToken() {
  return useMutation({
    mutationFn: () => api.post<McpToken>("/api/mcp/token"),
  });
}

/** What MCP's answers hide from now on: nothing, account numbers and IBANs, or people's names too. */
export function useSetMasking() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (masking: McpMasking) =>
      api.put<McpConnection>("/api/mcp/masking", { masking }),
    onSuccess: (saved) => client.setQueryData(keys.mcpConnection, saved),
  });
}

/** The net worth in TL and the other units, every asset and debt with its value and cost, the currencies' shares. */
export function useHoldings() {
  return useQuery({
    queryKey: keys.holdings,
    queryFn: () => api.get<Holdings>("/api/holdings"),
  });
}

/** The TL rates by currency: the providers' newest in use, else the documents' newest; with their history (F12). */
export function useFxRates() {
  return useQuery({
    queryKey: keys.fx,
    queryFn: () => api.get<FxRates>("/api/fx"),
  });
}

/** What the banks' rates cost against TCMB's over the last 12 months: currency trades and card purchases abroad. */
export function useFxSpread() {
  return useQuery({
    queryKey: keys.fxSpread,
    queryFn: () => api.get<FxSpread>("/api/fx/spread"),
  });
}

/** The income that comes in a foreign currency: its TL value now, its sales for TL and its sensitivity to the rate. */
export function useFxIncome() {
  return useQuery({
    queryKey: keys.fxIncome,
    queryFn: () => api.get<FxIncome>("/api/fx/income"),
  });
}

/**
 * Ask the service to fetch the rates now: the day's bulletin and the business days missed since the newest one; with
 * history, every day of the history not asked for yet. The System screen shows how it went as the service works.
 */
export function useFetchRates() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (history: boolean) => api.post<RatesQueued>("/api/fx/fetch", { history }),
    onSuccess: () => void client.invalidateQueries({ queryKey: keys.system }),
  });
}

/** The extension the program carries, and its folder in the data folder that the browser loads it from (K20). */
export function useExtension() {
  return useQuery({
    queryKey: keys.extension,
    queryFn: () => api.get<ExtensionInfo>("/api/extension"),
  });
}

/** Make the extension's folder, or bring it up to date, and show it in the system's file manager. */
export function useShowExtensionFolder() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<ExtensionFolder>("/api/extension/folder"),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.extension }),
  });
}

export function useStartPairing() {
  return useMutation({
    mutationFn: () => api.post<Pairing>("/api/bridge/pairings"),
  });
}

export function useRevokeBridge() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.delete(`/api/bridge/${encodeURIComponent(id)}`),
    onSettled: () => client.invalidateQueries({ queryKey: keys.bridges }),
  });
}

export function useBackupNow() {
  return useMutation({ mutationFn: () => api.post<Queued>("/api/backups") });
}

/** What the last analysis wrote to download (F20): the report, the rows as CSV and Excel, the month-end pages. */
export function useExports() {
  return useQuery({
    queryKey: keys.exports,
    queryFn: () => api.get<ExportItem[]>("/api/exports"),
  });
}

/** The analysis and its exports made again now; the list is asked again as the service writes them. */
export function useExportsAgain() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<ExportsQueued>("/api/exports"),
    onSuccess: () => {
      for (const after of SETTLING_MS) {
        setTimeout(
          () => void client.invalidateQueries({ queryKey: keys.exports }),
          after,
        );
      }
    },
  });
}

// --- notifications (F13, ADR-0010) ---------------------------------------------------------------------------------

const NOTIFICATIONS = "/api/notifications";
const NOTIFY_SETTINGS = "/api/notify/settings";
const TELEGRAM = "/api/notify/telegram";
const ALERT_RULES = "/api/rules/alerts";
const BOX_PAGE = 20;
const LOG_PAGE = 50;

function notificationPage(
  limit: number,
  before: number,
  channel?: Channel,
): Promise<Notifications> {
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
    mutationFn: (upTo: number) =>
      api.post<NotificationsMarked>(`${NOTIFICATIONS}/read`, { up_to: upTo }),
    onSettled: () => refreshNotifications(client),
  });
}

/** The quiet hours, each channel's level of detail and state, and what a channel still needs in the service's words. */
export function useNotifySettings() {
  return useQuery({
    queryKey: keys.notifySettings,
    queryFn: () => api.get<NotifySettings>(NOTIFY_SETTINGS),
  });
}

export function useSetNotifySettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (preferences: NotifyPreferences) =>
      api.put<NotifySettings>(NOTIFY_SETTINGS, preferences),
    onSuccess: (saved) => client.setQueryData(keys.notifySettings, saved),
  });
}

/** A test notification now on a channel; the in-app one lands in the box, and a stopped channel is tried again. */
export function useTestNotification() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (channel: Channel) =>
      api.post<void>("/api/notify/test", { channel }),
    onSettled: () => refreshNotifications(client),
  });
}

/**
 * Check a bot's token with Telegram and keep it in the keyring. A plain call, not a mutation: a mutation keeps its
 * variables in the client's cache, and the token must not stay in the page once it is sent.
 */
export async function sendTelegramToken(
  client: QueryClient,
  token: string,
): Promise<TelegramBot> {
  const bot = await api.post<TelegramBot>(`${TELEGRAM}/token`, { token });
  void client.invalidateQueries({ queryKey: keys.notifySettings });
  return bot;
}

/** A code the user sends the bot as "/start <code>" within ten minutes. */
export function useStartTelegramPairing() {
  return useMutation({
    mutationFn: () => api.post<TelegramPairing>(`${TELEGRAM}/pairing`),
  });
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
    onSettled: () =>
      client.invalidateQueries({ queryKey: keys.notifySettings }),
  });
}

/** The alert rules (the user's or the shipped ones) and the events a rule may watch with the conditions each allows. */
export function useAlertRules() {
  return useQuery({
    queryKey: keys.alertRules,
    queryFn: () => api.get<AlertRules>(ALERT_RULES),
  });
}

/** Save the whole list of rules; the service checks it first and refuses it whole, saying why. */
export function useSetAlertRules() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (rules: AlertRule[]) =>
      api.put<AlertRules>(ALERT_RULES, { rules }),
    onSuccess: (saved) => client.setQueryData(keys.alertRules, saved),
  });
}

/** How often a rule would have spoken in the last 30 days, with its newest texts; nothing is saved. */
export function usePreviewAlertRule() {
  return useMutation({
    mutationFn: (rule: AlertRule) =>
      api.post<AlertPreview>(`${ALERT_RULES}/preview`, { rule }),
  });
}

// --- the month-end closing (F11) ------------------------------------------------------------------------------------

// Under the dashboard's key, as the dashboard's closing card shows the same months: every event of the stream and
// every change that refreshes the dashboard (a rule, a correction) refreshes them too.
const monthEndKey = [...keys.dashboard, "month-end"] as const;

/** The current month and the twelve before it with documents, the newest first, each with its status. */
export function useMonthEnds() {
  return useQuery({
    queryKey: monthEndKey,
    queryFn: () => api.get<MonthEndList>("/api/month-end"),
  });
}

/** One month in full; nothing is asked for an address that names no month. */
export function useMonthEnd(month: string, enabled = true) {
  return useQuery({
    queryKey: [...monthEndKey, month],
    queryFn: () => api.get<MonthEndDetail>(`/api/month-end/${month}`),
    enabled,
  });
}

// --- the to-do list (F19) -------------------------------------------------------------------------------------------

// Under the dashboard's key, as the dashboard counts the same items: every event of the stream (a document read again)
// and every change that refreshes the dashboard (a rule, a correction) refreshes the list too.
const todoKey = (withIgnored: boolean) =>
  [...keys.dashboard, "todos", withIgnored] as const;

/** The to-do list by kind in F19's order; withIgnored also lists what the user took off it. */
export function useTodos(withIgnored: boolean) {
  return useQuery({
    queryKey: todoKey(withIgnored),
    queryFn: () => api.get<Todos>(`/api/todos?with_ignored=${withIgnored}`),
    placeholderData: keepPreviousData, // showing what was taken off keeps the list on the page meanwhile
  });
}

/** Take an item off the list (ignored), or put it back. */
export function useIgnoreTodo() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (change: { key: string; ignored: boolean }) =>
      api.post<void>("/api/todos/ignored", change),
    onSettled: () => client.invalidateQueries({ queryKey: keys.dashboard }),
  });
}

// --- the setup wizard and the Settings screen (F17) -----------------------------------------------------------------

// Under the System screen's key, as the exports: every event of the stream refreshes them (a paired extension, a
// document read, a channel made ready all move a step of the setup).
const setupKey = [...keys.system, "setup"] as const;
const settingsKey = [...keys.system, "settings"] as const;
const SETTINGS = "/api/settings";

/** Where each step of the setup wizard stands, and whether nothing is set up yet (the app then opens the wizard). */
export function useSetup() {
  return useQuery({
    queryKey: setupKey,
    queryFn: () => api.get<Setup>("/api/setup"),
  });
}

/** The settings with no secret in them; the e-mail address masked, as the service gives it. */
export function useSettings() {
  return useQuery({
    queryKey: settingsKey,
    queryFn: () => api.get<Settings>(SETTINGS),
  });
}

/** A settings change answered with the settings as they are now; the setup's steps are asked again. */
function useSettingsChange<T>(path: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (change: T) => api.put<Settings>(`${SETTINGS}/${path}`, change),
    onSuccess: (saved) => {
      client.setQueryData(settingsKey, saved);
      void client.invalidateQueries({ queryKey: setupKey });
    },
  });
}

/** The user's names and the company names, both lists whole; other company names make the documents be read again. */
export function useSetIdentity() {
  return useSettingsChange<{ names: string[]; business_names: string[] }>(
    "identity",
  );
}

/** The way e-mail comes in and the day the mailbox is read from. */
export function useSetMail() {
  return useSettingsChange<MailChange>("mail");
}

/** How many days of daily backups are kept. */
export function useSetBackupDays() {
  return useSettingsChange<{ keep_days: number }>("backup");
}

/**
 * Set an IMAP account up: one login with its app password, then the password goes to the keychain. A plain call, not
 * a mutation: a mutation keeps its variables in the client's cache, and the password must not stay in the page. A
 * refused login keeps nothing, and nothing here tries it again.
 */
export async function setUpImap(
  client: QueryClient,
  account: { address: string; password: string; start: string | null },
): Promise<ImapSetUp> {
  try {
    return await api.post<ImapSetUp>(`${SETTINGS}/mail/imap`, account);
  } finally {
    void client.invalidateQueries({ queryKey: keys.system }); // the settings, the setup and the mail's state
  }
}

// --- TÜFE from EVDS, with the user's own key (F12's V1+ part) ------------------------------------------------------------

const evdsKey = [...keys.system, "evds"] as const;
const EVDS = `${SETTINGS}/evds`;

/** Whether a key is kept, TÜFE's months fetched and the last attempt; the key itself never comes back. */
export function useEvds() {
  return useQuery({
    queryKey: evdsKey,
    queryFn: () => api.get<EvdsState>(EVDS),
  });
}

/**
 * Give the service an EVDS key: it is tried once with EVDS and kept in the keychain only when EVDS takes it. The
 * Değerlendirme screen's trend is asked again, now in real terms too.
 */
export function useSetEvdsKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (key: string) => api.put<EvdsState>(EVDS, { key }),
    onSuccess: (saved) => {
      client.setQueryData(evdsKey, saved);
      void client.invalidateQueries({ queryKey: keys.insights });
    },
  });
}

/** Forget the key; TÜFE's months already fetched stay. */
export function useRemoveEvdsKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete<void>(EVDS),
    onSettled: () => client.invalidateQueries({ queryKey: evdsKey }),
  });
}

/** Forget the IMAP account and its password. */
export function useRemoveImap() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete<void>(`${SETTINGS}/mail/imap`),
    onSettled: () => client.invalidateQueries({ queryKey: keys.system }),
  });
}

// --- the service's own life (ADR-0017) -------------------------------------------------------------------------------

// Under the System screen's key: every event of the stream refreshes them, a backup just taken among them.
const serviceKey = [...keys.system, "service"] as const;
const backupsKey = [...keys.system, "backups"] as const;
const SERVICE = "/api/service";

/** The running service: its version, since when, and whether the computer's service manager starts it here. */
export function useServiceState() {
  return useQuery({
    queryKey: serviceKey,
    queryFn: () => api.get<ServiceState>(SERVICE),
  });
}

/** The whole backups, newest first: one can be put back. */
export function useBackups() {
  return useQuery({
    queryKey: backupsKey,
    queryFn: () => api.get<BackupItem[]>("/api/backups"),
  });
}

/** Stop the service until the next login or until the app is opened again; it ends moments after it answers. */
export function useStopService() {
  return useMutation({
    mutationFn: () => api.post<ServiceEnding>(`${SERVICE}/stop`),
  });
}

/** End the service for the computer's service manager to start it again; only a registered service can. */
export function useRestartService() {
  return useMutation({
    mutationFn: () => api.post<ServiceEnding>(`${SERVICE}/restart`),
  });
}

/** Take the service off the computer and end it; the data folder goes to the Trash only when asked, never deleted. */
export function useRemoveService() {
  return useMutation({
    mutationFn: (dataToTrash: boolean) =>
      api.post<ServiceEnding>(`${SERVICE}/remove`, {
        data_to_trash: dataToTrash,
      }),
  });
}

/** Put a backup back: checked now, put back as the service starts again, after a backup of what there is now. */
export function useRestoreBackup() {
  return useMutation({
    mutationFn: (name: string) =>
      api.post<Restoring>(`/api/backups/${encodeURIComponent(name)}/restore`),
  });
}

/**
 * Who answers after the service ended to start again: "new" once a service started after `before` does, "signedOut"
 * when one answers but does not know this session (a backup put back brings its own), "old" while the one that ended
 * still does, "down" while none does. The health check could not tell the old service from the new one.
 */
export async function serviceAnswer(before: string): Promise<ServiceAnswer> {
  try {
    const state = await api.get<ServiceState>(SERVICE);
    return state.started_at === before
      ? { kind: "old" }
      : { kind: "new", state };
  } catch (error) {
    return {
      kind: error instanceof ApiError && error.signedOut ? "signedOut" : "down",
    };
  }
}

/** Which service answers after a restart or a restore; the new one says how its restore went. */
export type ServiceAnswer =
  { kind: "new"; state: ServiceState } | { kind: "signedOut" | "old" | "down" };

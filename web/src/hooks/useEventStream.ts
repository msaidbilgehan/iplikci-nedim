// The service's event stream (SSE, F05): each new event refreshes the server state it touches, and a burst of events
// refreshes each query once. A stream opened afresh tells the last minute's events again, which the page may have been
// loading through; the named `start` event first names the event it starts after. After a break the browser reconnects
// on its own and the service resumes after the last event it delivered (Last-Event-ID); a stream the browser gave up on
// is opened again after the last event seen or named, so nothing that happened meanwhile is missed. A named
// `notifications` event says that a notification was made or settled: the notifications follow their event by a
// moment (ADR-0010).

import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { keys } from "../api/queries";
import type { LoggedEvent } from "../api/types";

type QueryKey = readonly unknown[];

// What a new analysis changes: the series, the calendar, the forecast, the non-bank bills' matches, the rows, the
// accounts (their balances, pages and flows), the holdings and the documents' rates, and the assessment's cards and
// interpretation.
const ANALYSIS = [
  keys.subscriptions,
  keys.calendar,
  keys.forecast,
  keys.invoices,
  keys.allTransactions,
  keys.accounts,
  keys.allSpending,
  keys.insights,
  keys.holdings,
  keys.fx,
] as const;
// What every event changes: the feed shows it, what stands now and the dashboard's cards may move (its alerts follow
// the mail, the backups and the extension too); the System screen follows everything.
const EVERY = [keys.feedAll, keys.dashboard, keys.system] as const;
// What the stream's `notifications` event refreshes: the box, the history and the channels' counts.
export const NOTIFICATIONS_EVENT = "notifications";
export const NOTIFICATIONS: readonly QueryKey[] = [keys.notifications, keys.notifySettings];
// The named event a stream opened afresh begins with: the id of the event the stream starts after.
export const START_EVENT = "start";

const BATCH_MS = 200; // the events of a burst refresh each query once
const REOPEN_MS = 5_000; // after the browser gave up on the stream

/** The query keys an event of this kind makes stale. */
export function staleBy(kind: string): readonly QueryKey[] {
  if (kind.startsWith("document.") || kind.startsWith("transaction.")) {
    return [keys.allDocuments, ...ANALYSIS, ...EVERY];
  }
  if (kind.startsWith("parser.")) {
    return [keys.allDocuments, ...EVERY];
  }
  // A month's closing and a bill's new match come from a new analysis: a pending bill is on the calendar too.
  if (kind.startsWith("month.") || kind.startsWith("invoice.")) {
    return [...ANALYSIS, ...EVERY];
  }
  if (kind.startsWith("bridge.")) {
    return [keys.bridges, ...EVERY];
  }
  return EVERY;
}

/** Collects the stale keys of a burst and refreshes each once when the burst is over. */
function batcher(client: QueryClient): { add: (stale: readonly QueryKey[]) => void; stop: () => void } {
  const pending = new Map<string, QueryKey>();
  let timer: ReturnType<typeof setTimeout> | undefined;
  return {
    add(stale) {
      for (const queryKey of stale) {
        pending.set(JSON.stringify(queryKey), queryKey);
      }
      if (timer === undefined) {
        timer = setTimeout(() => {
          timer = undefined;
          const due = [...pending.values()];
          pending.clear();
          for (const queryKey of due) {
            void client.invalidateQueries({ queryKey });
          }
        }, BATCH_MS);
      }
    },
    stop() {
      clearTimeout(timer);
    },
  };
}

export function useEventStream(): void {
  const client = useQueryClient();
  useEffect(() => {
    if (typeof EventSource === "undefined") {
      return undefined;
    }
    const refresh = batcher(client);
    let last: number | null = null; // the newest event seen or named: a stream opened again starts after it
    let connected = false;
    let stream: EventSource | null = null;
    let reopen: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      stream = new EventSource(last === null ? "/api/events/stream" : `/api/events/stream?after=${last}`);
      stream.onopen = () => {
        if (connected) {
          // Back after a break: the service sends the events missed, but not the notifications made meanwhile.
          refresh.add(NOTIFICATIONS);
        }
        connected = true;
      };
      stream.onmessage = (message: MessageEvent<string>) => {
        let event: LoggedEvent;
        try {
          event = JSON.parse(message.data) as LoggedEvent;
        } catch {
          return; // not an event of ours
        }
        last = Math.max(last ?? 0, event.id);
        refresh.add(staleBy(event.kind));
      };
      stream.addEventListener(START_EVENT, (message: MessageEvent<string>) => {
        const id = Number(message.data);
        if (Number.isSafeInteger(id) && id >= 0) {
          last = Math.max(last ?? 0, id);
        }
      });
      stream.addEventListener(NOTIFICATIONS_EVENT, () => refresh.add(NOTIFICATIONS));
      stream.onerror = () => {
        // A broken connection is retried by the browser itself; one it gave up on is closed for good.
        if (stream?.readyState === EventSource.CLOSED) {
          stream.close();
          reopen = setTimeout(connect, REOPEN_MS);
        }
      };
    };

    connect();
    return () => {
      clearTimeout(reopen);
      refresh.stop();
      stream?.close();
    };
  }, [client]);
}

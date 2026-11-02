// The service's event stream (SSE, F05): each new event refreshes the server state it touches. The browser
// reconnects on its own after a break and resumes from the last event it saw. A named `notifications` event says
// that a notification was made or settled: the notifications follow their event by a moment (ADR-0010).

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { keys } from "../api/queries";
import type { LoggedEvent } from "../api/types";

// What a new analysis changes: the series, the calendar, the forecast and the non-bank bills' matches.
const ANALYSIS = [keys.subscriptions, keys.calendar, keys.forecast, keys.invoices] as const;
// What the stream's `notifications` event refreshes: the box, the history and the channels' counts.
export const NOTIFICATIONS_EVENT = "notifications";
export const NOTIFICATIONS: ReadonlyArray<readonly unknown[]> = [keys.notifications, keys.notifySettings];

/** The query keys an event of this kind makes stale; the System screen follows everything. */
export function staleBy(kind: string): ReadonlyArray<readonly unknown[]> {
  if (kind.startsWith("document.") || kind.startsWith("transaction.")) {
    return [keys.allDocuments, ...ANALYSIS, keys.system];
  }
  if (kind.startsWith("parser.")) {
    return [keys.allDocuments, keys.system];
  }
  // A month's closing and a bill's new match come from a new analysis: a pending bill is on the calendar too.
  if (kind.startsWith("month.") || kind.startsWith("invoice.")) {
    return [...ANALYSIS, keys.system];
  }
  if (kind.startsWith("bridge.")) {
    return [keys.bridges, keys.system];
  }
  return [keys.system];
}

export function useEventStream(): void {
  const client = useQueryClient();
  useEffect(() => {
    if (typeof EventSource === "undefined") {
      return undefined;
    }
    const stream = new EventSource("/api/events/stream");
    stream.onmessage = (message: MessageEvent<string>) => {
      let event: LoggedEvent;
      try {
        event = JSON.parse(message.data) as LoggedEvent;
      } catch {
        return; // not an event of ours
      }
      for (const queryKey of staleBy(event.kind)) {
        void client.invalidateQueries({ queryKey });
      }
    };
    stream.addEventListener(NOTIFICATIONS_EVENT, () => {
      for (const queryKey of NOTIFICATIONS) {
        void client.invalidateQueries({ queryKey });
      }
    });
    return () => stream.close();
  }, [client]);
}

// The service's event stream (SSE, F05): each new event refreshes the server state it touches. The browser
// reconnects on its own after a break and resumes from the last event it saw.

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { keys } from "../api/queries";
import type { LoggedEvent } from "../api/types";

// What a new analysis changes: the series, the calendar and the forecast.
const ANALYSIS = [keys.subscriptions, keys.calendar, keys.forecast] as const;

/** The query keys an event of this kind makes stale; the System screen follows everything. */
export function staleBy(kind: string): ReadonlyArray<readonly unknown[]> {
  if (kind.startsWith("document.") || kind.startsWith("transaction.")) {
    return [keys.allDocuments, ...ANALYSIS, keys.system];
  }
  if (kind.startsWith("parser.")) {
    return [keys.allDocuments, keys.system];
  }
  if (kind.startsWith("month.")) {
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
    return () => stream.close();
  }, [client]);
}

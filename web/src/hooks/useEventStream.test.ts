import { describe, expect, it } from "vitest";

import { keys } from "../api/queries";
import { staleBy } from "./useEventStream";

describe("staleBy", () => {
  it("refreshes the documents on a document's events and the System screen on every event", () => {
    const analysis = [keys.subscriptions, keys.calendar, keys.forecast, keys.invoices];
    expect(staleBy("document.received")).toEqual([keys.allDocuments, ...analysis, keys.system]);
    expect(staleBy("transaction.created")).toEqual([keys.allDocuments, ...analysis, keys.system]);
    expect(staleBy("month.closed")).toEqual([...analysis, keys.system]); // a new analysis: the days ahead move
    expect(staleBy("invoice.matched")).toEqual([...analysis, keys.system]); // the Bills screen and the calendar
    expect(staleBy("invoice.pending")).toEqual([...analysis, keys.system]);
    expect(staleBy("parser.format_alarm")).toEqual([keys.allDocuments, keys.system]);
    expect(staleBy("backup.failed")).toEqual([keys.system]);
    expect(staleBy("mail.auth_failed")).toEqual([keys.system]);
    expect(staleBy("bridge.paired")).toEqual([keys.bridges, keys.system]); // the pairing page shows the new one
  });
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { keys } from "../api/queries";
import { NOTIFICATIONS, staleBy, useEventStream } from "./useEventStream";

describe("staleBy", () => {
  it("refreshes the documents on a document's events, and the feed, the dashboard and the System screen on every event", () => {
    const analysis = [keys.subscriptions, keys.calendar, keys.forecast, keys.invoices];
    const every = [keys.feedAll, keys.dashboard, keys.system];
    expect(staleBy("document.received")).toEqual([keys.allDocuments, ...analysis, ...every]);
    expect(staleBy("transaction.created")).toEqual([keys.allDocuments, ...analysis, ...every]);
    expect(staleBy("month.closed")).toEqual([...analysis, ...every]); // a new analysis: the days ahead move
    expect(staleBy("invoice.matched")).toEqual([...analysis, ...every]); // the Bills screen and the calendar
    expect(staleBy("invoice.pending")).toEqual([...analysis, ...every]);
    expect(staleBy("parser.format_alarm")).toEqual([keys.allDocuments, ...every]);
    expect(staleBy("backup.failed")).toEqual(every);
    expect(staleBy("mail.auth_failed")).toEqual(every);
    expect(staleBy("bridge.paired")).toEqual([keys.bridges, ...every]); // the pairing page shows the new one
  });

  it("refreshes what stands now with the feed: both live under the feed's key", () => {
    expect(keys.now.slice(0, keys.feedAll.length)).toEqual([...keys.feedAll]);
  });
});

describe("the notifications event", () => {
  it("refreshes the notification box, the history and the channels' counts", () => {
    expect(NOTIFICATIONS).toEqual([keys.notifications, keys.notifySettings]);
  });
});

/** An EventSource the test drives: it opens, delivers and breaks when told. */
class FakeStream {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  static opened: FakeStream[] = [];
  readonly url: string;
  readyState = FakeStream.CONNECTING;
  onopen: (() => void) | null = null;
  onmessage: ((message: MessageEvent<string>) => void) | null = null;
  onerror: (() => void) | null = null;
  private readonly named = new Map<string, (message: MessageEvent<string>) => void>();

  constructor(url: string) {
    this.url = url;
    FakeStream.opened.push(this);
  }

  addEventListener(type: string, listener: (message: MessageEvent<string>) => void): void {
    this.named.set(type, listener);
  }

  close(): void {
    this.readyState = FakeStream.CLOSED;
  }

  open(): void {
    this.readyState = FakeStream.OPEN;
    this.onopen?.();
  }

  deliver(id: number, kind: string, at: string): void {
    const data = JSON.stringify({ id, at, kind, target: "", detail: {} });
    this.onmessage?.(new MessageEvent("message", { data, lastEventId: String(id) }));
  }

  /** The named `start` event a stream opened afresh begins with. */
  start(id: number): void {
    this.named.get("start")?.(new MessageEvent("start", { data: String(id), lastEventId: String(id) }));
  }

  notify(): void {
    this.named.get("notifications")?.(new MessageEvent("notifications", { data: "1" }));
  }

  /** The connection broke; closed: the browser gave up instead of retrying. */
  fail(closed: boolean): void {
    this.readyState = closed ? FakeStream.CLOSED : FakeStream.CONNECTING;
    this.onerror?.();
  }
}

const OPENED = new Date("2026-11-02T09:00:00Z");

function streamed() {
  const client = new QueryClient();
  const invalidate = vi.spyOn(client, "invalidateQueries").mockResolvedValue();
  const wrapper = ({ children }: { children: ReactNode }) => createElement(QueryClientProvider, { client }, children);
  const hook = renderHook(() => useEventStream(), { wrapper });
  const refreshed = () => invalidate.mock.calls.map(([filters]) => filters?.queryKey);
  return { hook, invalidate, refreshed, stream: () => FakeStream.opened.at(-1)! };
}

describe("useEventStream", () => {
  beforeEach(() => {
    FakeStream.opened = [];
    vi.stubGlobal("EventSource", FakeStream);
    vi.useFakeTimers({ toFake: ["Date", "setTimeout", "clearTimeout"] });
    vi.setSystemTime(OPENED);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("refreshes each stale query once for a burst of events", () => {
    const { refreshed, stream } = streamed();
    stream().open();
    stream().deliver(7, "document.received", "2026-11-02T09:00:05Z");
    stream().deliver(8, "document.processed", "2026-11-02T09:00:06Z");
    expect(refreshed()).toEqual([]);
    act(() => vi.advanceTimersByTime(250));
    expect(refreshed()).toEqual(staleBy("document.received"));
  });

  it("opens the stream afresh, and a stream given up on before any event came again after the one the service named", () => {
    const { stream } = streamed();
    expect(stream().url).toBe("/api/events/stream");
    stream().open();
    stream().start(0); // the log is empty: the stream starts at its beginning
    stream().fail(true);
    act(() => vi.advanceTimersByTime(5_000));
    expect(FakeStream.opened).toHaveLength(2);
    expect(stream().url).toBe("/api/events/stream?after=0");
  });

  it("opens a stream the browser gave up on again after the last event seen, and catches up the notifications", () => {
    const { refreshed, stream } = streamed();
    stream().open();
    stream().deliver(41, "backup.failed", "2026-11-02T09:00:05Z");
    act(() => vi.advanceTimersByTime(250));
    stream().fail(true);
    expect(FakeStream.opened).toHaveLength(1);
    act(() => vi.advanceTimersByTime(5_000));
    expect(FakeStream.opened).toHaveLength(2);
    expect(stream().url).toBe("/api/events/stream?after=41");
    stream().open();
    act(() => vi.advanceTimersByTime(250));
    expect(refreshed()).toEqual([...staleBy("backup.failed"), ...NOTIFICATIONS]);
  });

  it("lets the browser retry a broken connection itself", () => {
    const { stream } = streamed();
    stream().open();
    stream().fail(false);
    act(() => vi.advanceTimersByTime(10_000));
    expect(FakeStream.opened).toHaveLength(1);
  });

  it("refreshes the notifications when the stream says one was made", () => {
    const { refreshed, stream } = streamed();
    stream().open();
    stream().notify();
    act(() => vi.advanceTimersByTime(250));
    expect(refreshed()).toEqual(NOTIFICATIONS);
  });

  it("closes the stream when the page goes", () => {
    const { hook, stream } = streamed();
    hook.unmount();
    expect(stream().readyState).toBe(FakeStream.CLOSED);
  });
});

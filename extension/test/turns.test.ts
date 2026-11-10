import { describe, expect, it } from "vitest";

import type { RunSummary, ScanSummary } from "../src/bridge/state";
import { Turns } from "../src/bridge/turns";

const RAN: RunSummary = {
  at: "2026-11-10T15:00:00Z",
  outcome: "nothing-new",
  delivered: 0,
  detail: "Yeni banka iletisi yok.",
};
const SCANNED: ScanSummary = {
  at: "2026-11-10T15:00:00Z",
  phase: "done",
  pages: 1,
  conversations: 0,
  found: 0,
  missing: 0,
  delivered: 0,
  unshown: 0,
  between: 0,
  betweenUnread: 0,
  detail: "Gmail'in aramasında listedeki bankalardan ileti çıkmadı.",
};

function deferred<T>() {
  let resolve: (value: T) => void = () => undefined;
  let reject: (error: Error) => void = () => undefined;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

/** The delivery runs as they are started, each with the ids it was given; each ends when the test says. */
function runs() {
  const started: Array<{ shown: readonly string[]; end: (summary: RunSummary) => void; fail: () => void }> = [];
  const turns = new Turns((shown) => {
    const run = deferred<RunSummary>();
    started.push({ shown, end: run.resolve, fail: () => run.reject(new Error("bozuldu")) });
    return run.promise;
  });
  return { turns, started };
}

/** What was started meanwhile has started: the runs begin in promise callbacks. */
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("one delivery run or scan at a time", () => {
  it("lets an alarm that comes during a run join it", async () => {
    const { turns, started } = runs();
    const first = turns.run();
    expect(turns.run()).toBe(first);
    started[0]?.end(RAN);
    expect(await first).toEqual(RAN);
    expect(started).toHaveLength(1);
  });

  it("starts a run at once for the ids a Gmail tab tells", () => {
    const { turns, started } = runs();
    turns.seen(["1000"]);
    expect(started.map((run) => run.shown)).toEqual([["1000"]]);
  });

  it("keeps the ids a Gmail tab tells during a run for a run right after it", async () => {
    const { turns, started } = runs();
    void turns.run();
    turns.seen(["1000"]);
    turns.seen(["2000", "1000"]);
    expect(started.map((run) => run.shown)).toEqual([[]]);
    started[0]?.end(RAN);
    await settle();
    expect(started.map((run) => run.shown)).toEqual([[], ["1000", "2000"]]);
    started[1]?.end(RAN);
    await settle();
    expect(started).toHaveLength(2); // nothing more waits
  });

  it("starts the next run after one that failed", async () => {
    const { turns, started } = runs();
    const first = turns.run();
    turns.seen(["1000"]);
    started[0]?.fail();
    await expect(first).rejects.toThrow("bozuldu");
    await settle();
    expect(started.map((run) => run.shown)).toEqual([[], ["1000"]]);
  });

  it("starts no run during a scan, and takes the ids told meanwhile when it ends", async () => {
    const { turns, started } = runs();
    const scan = deferred<ScanSummary>();
    const scanning = turns.scan(() => scan.promise);
    expect(turns.scanning).toBe(true);
    turns.seen(["1000"]);
    expect(await turns.run()).toBeNull();
    expect(started).toEqual([]);
    scan.resolve(SCANNED);
    expect(await scanning).toEqual(SCANNED);
    await settle();
    expect(turns.scanning).toBe(false);
    expect(started.map((run) => run.shown)).toEqual([["1000"]]);
  });

  it("begins a scan only when the run under way has ended", async () => {
    const { turns, started } = runs();
    void turns.run();
    let began = false;
    const scanning = turns.scan(async () => {
      began = true;
      return SCANNED;
    });
    expect(turns.scan(async () => SCANNED)).toBe(scanning); // one scan at a time
    await settle();
    expect(began).toBe(false);
    started[0]?.end(RAN);
    await scanning;
    expect(began).toBe(true);
  });

  it("forgets the ids told for another account or pairing", async () => {
    const { turns, started } = runs();
    void turns.run();
    turns.seen(["1000"]);
    turns.forget();
    started[0]?.end(RAN);
    await settle();
    expect(started).toHaveLength(1);
  });
});

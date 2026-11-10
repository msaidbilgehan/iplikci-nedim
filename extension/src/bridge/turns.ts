/**
 * One thing at a time with Gmail (ADR-0016: requests go one at a time, a second apart): a delivery run or a scan of
 * Gmail, never both. An alarm that comes during a run joins it. While a scan runs no run starts: the scan holds
 * Gmail's one request a second and delivers in the meantime. A scan asked for during a run waits for its end.
 *
 * The ids an open Gmail tab tells (content.ts) wait here for the next run, which keeps them in the stored state first
 * thing: it starts at once when nothing runs, else right after the run or the scan under way.
 */

import type { RunSummary, ScanSummary } from "./state";

export class Turns {
  private delivering: Promise<RunSummary> | null = null;
  private searching: Promise<ScanSummary> | null = null;
  private readonly waiting = new Set<string>();

  /** deliver: one delivery run, given the ids the open Gmail tabs told since the last one. */
  constructor(private readonly deliver: (shown: readonly string[]) => Promise<RunSummary>) {}

  /** Whether a scan of Gmail runs, or waits for the run under way to end. */
  get scanning(): boolean {
    return this.searching !== null;
  }

  /** The delivery run under way, else a new one; null while a scan runs. */
  run(): Promise<RunSummary | null> {
    if (this.searching !== null) {
      return Promise.resolve(null);
    }
    if (this.delivering === null) {
      const shown = [...this.waiting];
      this.waiting.clear();
      this.delivering = this.deliver(shown).finally(() => {
        this.delivering = null;
        this.next();
      });
    }
    return this.delivering;
  }

  /** The scan under way, else `start` once the run under way has ended. */
  scan(start: () => Promise<ScanSummary>): Promise<ScanSummary> {
    this.searching ??= (async () => {
      await this.delivering?.catch(() => undefined);
      return start();
    })().finally(() => {
      this.searching = null;
      this.next();
    });
    return this.searching;
  }

  /** Ids an open Gmail tab showed: a run takes them now, or right after the run or the scan under way. */
  seen(ids: Iterable<string>): void {
    for (const id of ids) {
      this.waiting.add(id);
    }
    if (this.delivering === null) {
      this.next();
    }
  }

  /** Another account or pairing: the ids told for the one before are not this one's. */
  forget(): void {
    this.waiting.clear();
  }

  private next(): void {
    if (this.waiting.size > 0) {
      this.run().catch(() => undefined); // the run keeps what happened in the stored state
    }
  }
}

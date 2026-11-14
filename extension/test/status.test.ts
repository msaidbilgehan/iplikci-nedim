import { describe as group, expect, it } from "vitest";

import type { Status } from "../src/bridge/messages";
import type { RunSummary, ScanSummary } from "../src/bridge/state";
import { ICON_PATHS, NO_PROGRAM, SILENT, describe } from "../src/ui/status";

const PAIRED: Status = {
  paired: true,
  account: 0,
  lastRun: null,
  scan: null,
  historyDue: false,
  startDay: "2026-01-01",
  stopped: [],
  problem: "",
};

function ran(outcome: RunSummary["outcome"], detail: string): RunSummary {
  return { at: "2026-11-02T11:05:00Z", outcome, delivered: 0, detail };
}

const SCAN: ScanSummary = {
  at: "2026-11-02T11:00:00Z",
  phase: "searching",
  pages: 2,
  conversations: 40,
  found: 0,
  missing: 0,
  delivered: 0,
  unshown: 0,
  between: 0,
  betweenUnread: 0,
  detail: "Gmail'de aranıyor: 40 konuşma…",
};

const STATES: ReadonlyArray<[string, Status | null]> = [
  ["the background did not answer", null],
  ["not paired", { ...PAIRED, paired: false }],
  ["paired, before the first check", PAIRED],
  ["working", { ...PAIRED, lastRun: ran("nothing-new", "Yeni banka iletisi yok.") }],
  ["needing attention", { ...PAIRED, lastRun: ran("gmail-signed-out", "Bu tarayıcıda seçilen Gmail hesabına girilmemiş.") }],
  ["scanning", { ...PAIRED, lastRun: ran("delivered", "2 yeni ileti İplikçi Nedim'e teslim edildi."), scan: SCAN }],
  ["the service not running", { ...PAIRED, lastRun: ran("service-down", "İplikçi Nedim bu bilgisayarda çalışmıyor.") }],
];

group("where the bridge stands", () => {
  it("names every state with a word and an icon of its own, so the colour never says it alone", () => {
    const shown = STATES.map(([, status]) => describe(status, "Kodu girin."));
    expect(shown.map((s) => s.word)).toEqual([
      "Yanıt yok",
      "Eşleşmedi",
      "Bekleniyor",
      "Çalışıyor",
      "Dikkat",
      "Taranıyor",
      "Kapalı",
    ]);
    expect(new Set(shown.map((s) => `${s.tone} ${s.icon}`)).size).toBe(6); // two words share the cross: both stopped
    expect(shown.every((s) => ICON_PATHS[s.icon] !== "")).toBe(true);
  });

  it("says the program is needed with a word and an icon no other state has", () => {
    const shown = STATES.map(([, status]) => describe(status, "Kodu girin."));
    expect(NO_PROGRAM.word).toBe("Program gerekli");
    expect(shown.some((s) => s.word === NO_PROGRAM.word || s.icon === NO_PROGRAM.icon)).toBe(false);
    expect(ICON_PATHS[NO_PROGRAM.icon]).not.toBe("");
  });

  it("says what the last run said, when it ran and how often", () => {
    const working = describe(STATES[3]![1], "");
    expect(working.detail).toBe("Yeni banka iletisi yok.");
    expect(working.when).toMatch(/^Son denetim: \d{1,2}\.\d{2}\.\d{4} \d{2}:\d{2} \(her dakika denetlenir\)$/);
    expect(describe(STATES[4]![1], "").detail).toBe("Bu tarayıcıda seçilen Gmail hesabına girilmemiş.");
  });

  it("follows a scan under way by its detail, and says where the code goes before pairing", () => {
    expect(describe(STATES[5]![1], "").detail).toBe("Gmail'de aranıyor: 40 konuşma…");
    const done = describe({ ...PAIRED, lastRun: ran("delivered", "1 yeni ileti."), scan: { ...SCAN, phase: "done" } }, "");
    expect(done.word).toBe("Çalışıyor"); // a finished scan is not under way
    expect(describe(STATES[1]![1], "Kodu aşağıya girin.")).toMatchObject({ detail: "Kodu aşağıya girin.", when: "" });
    expect(describe(null, "").detail).toBe(SILENT);
  });
});

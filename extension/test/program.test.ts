// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { type Status, asRequest } from "../src/bridge/messages";
import { INSTALLERS, type Platform, RELEASES, REPO, downloadFor, latest, systemName } from "../src/bridge/program";
import { type Fetcher, SERVICE, answers } from "../src/bridge/service";
import { type Seen, WAIT_MS, follow, guideFor, showGuide } from "../src/ui/program";

const LATEST = `https://github.com/${REPO}/releases/latest/download/`;

describe("the program's download for this computer", () => {
  it.each([
    [{ os: "mac", arch: "arm64" }, "iplikci-nedim-macos-aarch64.dmg"],
    [{ os: "win", arch: "x86-64" }, "iplikci-nedim-windows-x86_64.exe"],
    [{ os: "linux", arch: "x86-64" }, "iplikci-nedim-linux-x86_64.AppImage"],
  ])("leads %o to its installer in the latest release, under a name without the version", (platform, file) => {
    const found = downloadFor(platform);
    expect(found.installer?.file).toBe(file);
    expect(found.url).toBe(`${LATEST}${file}`);
  });

  it.each([
    [{ os: "mac", arch: "x86-64" }, "macOS (Intel işlemci)"],
    [{ os: "win", arch: "arm64" }, "Windows (ARM işlemci)"],
    [{ os: "linux", arch: "arm64" }, "Linux (ARM işlemci)"],
    [{ os: "linux", arch: "x86-32" }, "Linux (32 bit işlemci)"],
    [{ os: "cros", arch: "x86-64" }, "ChromeOS"],
    [{ os: "android", arch: "arm64" }, "Android"],
  ])("leads %o, which no release has an installer for, to the releases' page and names it", (platform, system) => {
    expect(downloadFor(platform)).toEqual({ installer: null, url: RELEASES, system });
  });

  it("never leads anywhere but the releases of the repository the program updates from", () => {
    const platforms: Platform[] = [
      ...INSTALLERS,
      { os: "openbsd", arch: "x86-64" },
      { os: "", arch: "" },
      { os: "mac", arch: "mips64" },
    ];
    for (const platform of platforms) {
      expect(downloadFor(platform).url.startsWith(`https://github.com/${REPO}/releases/latest`)).toBe(true);
    }
    expect(RELEASES).toBe(`https://github.com/${REPO}/releases/latest`);
    expect(latest("a b.dmg")).toBe(`${LATEST}a%20b.dmg`);
  });

  it("names a system it does not know as the browser does", () => {
    expect(systemName({ os: "haiku", arch: "x86-64" })).toBe("haiku");
    expect(systemName({ os: "mac", arch: "" })).toBe("macOS");
  });
});

describe("the guide to install it", () => {
  const mac = guideFor(downloadFor({ os: "mac", arch: "arm64" }));
  const windows = guideFor(downloadFor({ os: "win", arch: "x86-64" }));
  const linux = guideFor(downloadFor({ os: "linux", arch: "x86-64" }));

  it("offers the download and names the file and its system under the button", () => {
    expect([mac.button, mac.target]).toEqual([
      "İplikçi Nedim'i indir",
      "macOS (Apple Silicon) için: iplikci-nedim-macos-aarch64.dmg",
    ]);
    expect(windows.target).toBe("Windows (Intel ya da AMD işlemci) için: iplikci-nedim-windows-x86_64.exe");
    for (const guide of [mac, windows, linux]) {
      expect(guide.steps[0]).toContain(guide.target.split(": ")[1]); // the first step names the file downloaded
    }
  });

  it("tells macOS's way: the disk image, its Applications folder and the first opening's Open Anyway", () => {
    const text = mac.steps.join("\n");
    for (const words of ["“Applications”", "Uygulamalar klasöründe", "“İplikçi Nedim” Açılmadı", "“Bitti”"]) {
      expect(text).toContain(words);
    }
    expect(text).toContain("Sistem Ayarları → Gizlilik ve Güvenlik'te"); // the pane's name in macOS's Turkish
    expect(text).toContain("“Yine de Aç”"); // its button, as macOS writes it
  });

  it("tells Windows's way past SmartScreen and Linux's to run the AppImage", () => {
    expect(windows.steps.join("\n")).toContain("“Ek bilgi”ye, sonra “Yine de çalıştır”a basın");
    const text = linux.steps.join("\n");
    expect(text).toContain("program olarak çalıştırılmasına izin veren");
    expect(text).toContain("uygulama menüsüne");
  });

  it("says plainly that a system without an installer has none, which systems have one, and opens the page", () => {
    const chrome = guideFor(downloadFor({ os: "cros", arch: "x86-64" }));
    expect(chrome).toEqual({
      button: "Sürüm sayfasını aç",
      url: RELEASES,
      target:
        "Bu bilgisayar (ChromeOS) için İplikçi Nedim'in kurulum paketi yok: paketler macOS (Apple Silicon), " +
        "Windows (Intel ya da AMD işlemci) ve Linux (Intel ya da AMD işlemci) içindir. Sürüm sayfası hepsini gösterir.",
      steps: [],
    });
  });

  it("is shown on a page as text, a step an item, without markup", () => {
    document.body.innerHTML = `<button><span id="label"></span></button><p id="target"></p><ol id="steps"></ol>`;
    const parts = {
      label: document.getElementById("label") as HTMLElement,
      target: document.getElementById("target") as HTMLElement,
      steps: document.getElementById("steps") as HTMLOListElement,
    };
    const odd = { ...mac, steps: ["<b>kalın</b> değil", ...mac.steps.slice(1)] };
    showGuide(parts, odd);
    expect(parts.label.textContent).toBe("İplikçi Nedim'i indir");
    expect([...parts.steps.children].map((item) => item.textContent)).toEqual(odd.steps);
    expect(parts.steps.querySelector("b")).toBeNull(); // a step is never read as HTML
    showGuide(parts, guideFor(downloadFor({ os: "cros", arch: "arm64" })));
    expect([parts.steps.children.length, parts.steps.hidden]).toEqual([0, true]);
    expect(parts.label.textContent).toBe("Sürüm sayfasını aç");
  });
});

const UNPAIRED: Status = {
  paired: false,
  account: 0,
  lastRun: null,
  scan: null,
  historyDue: false,
  startDay: "",
  stopped: [],
  problem: "",
};

describe("a page waiting for the program", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("asks again every few seconds while the program is missing, and stops once it answers", async () => {
    vi.useFakeTimers();
    const looks: Seen[] = [
      { status: UNPAIRED, missing: true },
      { status: UNPAIRED, missing: true },
      { status: UNPAIRED, missing: false },
    ];
    const shown: boolean[] = [];
    const find = vi.fn(async () => looks.shift() ?? { status: UNPAIRED, missing: false });
    const refresh = follow((seen) => shown.push(seen.missing), find);
    await refresh();
    expect(shown).toEqual([true]);
    await vi.advanceTimersByTimeAsync(WAIT_MS);
    expect(shown).toEqual([true, true]);
    await vi.advanceTimersByTimeAsync(WAIT_MS);
    expect(shown).toEqual([true, true, false]); // it answers: pairing goes on
    await vi.advanceTimersByTimeAsync(WAIT_MS * 5);
    expect(find).toHaveBeenCalledTimes(3); // nothing more is asked
  });

  it("shows only the latest look when an earlier one answers late", async () => {
    let release: (seen: Seen) => void = () => undefined;
    const slow = new Promise<Seen>((resolve) => {
      release = resolve;
    });
    const answers = [slow, Promise.resolve({ status: UNPAIRED, missing: false })];
    const shown: boolean[] = [];
    const refresh = follow(
      (seen) => shown.push(seen.missing),
      () => answers.shift() ?? Promise.resolve({ status: UNPAIRED, missing: false }),
    );
    const first = refresh();
    await refresh(); // the stored state changed meanwhile
    release({ status: UNPAIRED, missing: true });
    await first;
    expect(shown).toEqual([false]); // the late answer from before is not shown over it
  });
});

describe("whether the program answers", () => {
  it("asks the service's health check only, without a token or a cookie", async () => {
    const asked: Array<{ url: string; init: RequestInit }> = [];
    const fetcher: Fetcher = async (url, init) => {
      asked.push({ url, init });
      return new Response(JSON.stringify({ status: "ok" }), { status: 200 });
    };
    expect(await answers(fetcher)).toBe(true);
    expect(asked).toHaveLength(1);
    expect(asked[0]?.url).toBe(`${SERVICE}/healthz`);
    expect(asked[0]?.init.credentials).toBe("omit");
    expect(new Headers(asked[0]?.init.headers).get("Authorization")).toBeNull();
  });

  it("counts any answer, a service still opening its database too, and nothing when nothing listens", async () => {
    expect(await answers(async () => new Response("{}", { status: 503 }))).toBe(true);
    expect(await answers(async () => new Response("baska bir program", { status: 404 }))).toBe(true);
    expect(
      await answers(async () => {
        throw new TypeError("Failed to fetch");
      }),
    ).toBe(false);
  });

  it("is a request the extension's own pages make, checked like the others", () => {
    expect(asRequest({ kind: "service" })).toEqual({ kind: "service" });
    expect(asRequest({ kind: "service", url: "https://kotu.example" })).toEqual({ kind: "service" });
  });
});

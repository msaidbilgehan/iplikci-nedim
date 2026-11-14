/**
 * İplikçi Nedim's program, for an extension that cannot find it (ADR-0024). Installed from the Chrome Web Store on a
 * computer without the program, the extension is not paired and nothing answers on the service's address: its pages
 * then offer this system's installer from the latest release, and the browser downloads it in a new tab. The
 * extension asks nothing of GitHub itself and needs no permission for it. Every release carries each system's
 * installer under a name without the version (packaging/release.py), so the latest one is always at one address.
 */

/** Where the releases are: where the program looks for its updates (src/iplikci/update/source.py's REPO; the
 * program's tests check that the two agree). */
export const REPO = "msaidbilgehan/iplikci-nedim-surumler";
/** The latest release's page: its notes and every system's installer. */
export const RELEASES = `https://github.com/${REPO}/releases/latest`;

/** This computer as chrome.runtime.getPlatformInfo() names it. */
export interface Platform {
  readonly os: string;
  readonly arch: string;
}

/** A system every release carries an installer for. */
export interface Installer {
  readonly os: "mac" | "win" | "linux";
  readonly arch: string;
  /** The installer's name in every release: packaging/release.py's stable_name (the program's tests check it). */
  readonly file: string;
  /** The system in words, as "… için" follows it. */
  readonly name: string;
}

/** The installers of every release: the machines the release workflow builds on (packaging/release.py's OFFERED). */
export const INSTALLERS: readonly Installer[] = [
  { os: "mac", arch: "arm64", file: "iplikci-nedim-macos-aarch64.dmg", name: "macOS (Apple Silicon)" },
  { os: "win", arch: "x86-64", file: "iplikci-nedim-windows-x86_64.exe", name: "Windows (Intel ya da AMD işlemci)" },
  { os: "linux", arch: "x86-64", file: "iplikci-nedim-linux-x86_64.AppImage", name: "Linux (Intel ya da AMD işlemci)" },
];

/** The operating systems by the names chrome.runtime.getPlatformInfo() gives them. */
export const OS_NAMES: Readonly<Record<string, string>> = {
  mac: "macOS",
  win: "Windows",
  linux: "Linux",
  cros: "ChromeOS",
  android: "Android",
  openbsd: "OpenBSD",
  fuchsia: "Fuchsia",
};

/** What İplikçi Nedim's download is on this computer. */
export interface Download {
  /** This system's installer; null when the releases carry none for it. */
  readonly installer: Installer | null;
  /** Where the button leads: the installer in the latest release, or the releases' page without one. */
  readonly url: string;
  /** This computer's system in words: "macOS (Intel işlemci)", "ChromeOS". */
  readonly system: string;
}

/** The latest release's file of this name. */
export function latest(file: string): string {
  return `https://github.com/${REPO}/releases/latest/download/${encodeURIComponent(file)}`;
}

export function downloadFor(platform: Platform): Download {
  const installer = INSTALLERS.find((each) => each.os === platform.os && each.arch === platform.arch) ?? null;
  return { installer, url: installer === null ? RELEASES : latest(installer.file), system: systemName(platform) };
}

/** The system in words, with its processor where the releases tell machines apart by it. */
export function systemName(platform: Platform): string {
  const os = OS_NAMES[platform.os] ?? platform.os;
  const machine = ["mac", "win", "linux"].includes(platform.os) ? processor(platform) : "";
  return machine === "" ? os : `${os} (${machine})`;
}

function processor({ os, arch }: Platform): string {
  switch (arch) {
    case "arm64":
      return os === "mac" ? "Apple Silicon" : "ARM işlemci";
    case "x86-64":
      return os === "mac" ? "Intel işlemci" : "Intel ya da AMD işlemci";
    case "x86-32":
      return "32 bit işlemci";
    case "arm":
      return "32 bit ARM işlemci";
    default:
      return "";
  }
}

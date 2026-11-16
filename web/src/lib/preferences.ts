// The user's display preferences (architecture §18): the theme — light, dark, or the system's, followed live — the
// view — simple (each card's one-sentence comment and next step) or detailed (tables and raw data) — and what the
// forecast's line counts — the TL accounts alone, or foreign currency and investments too. All are kept in the
// browser's localStorage: preferences only, never a secret. The theme goes on <html> as a class before React renders,
// from the module script; the CSP allows no inline one (ADR-0008).

export type Theme = "light" | "dark" | "system";
export type View = "simple" | "detailed";
// The forecast is for the TL accounts the payments leave from; what moves with a rate or a market is added on demand.
export type Holdings = "tl" | "all";

export const THEMES: readonly Theme[] = ["light", "dark", "system"];
export const VIEWS: readonly View[] = ["simple", "detailed"];
export const HOLDINGS: readonly Holdings[] = ["tl", "all"];
// Until the user chooses, the theme is the system's: the end-to-end tests' light and dark projects rest on it.
export const DEFAULT_THEME: Theme = "system";
// The simple view suits someone new to their finances; whoever wants the tables switches once, and it is remembered.
export const DEFAULT_VIEW: View = "simple";
// The TL accounts alone until the user asks for more: what pays the coming payments, as the warnings count it.
export const DEFAULT_HOLDINGS: Holdings = "tl";

const THEME_KEY = "iplikci.theme";
const VIEW_KEY = "iplikci.view";
const HOLDINGS_KEY = "iplikci.forecast";
const DARK_QUERY = "(prefers-color-scheme: dark)";

function read<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const stored = window.localStorage.getItem(key);
    return allowed.find((value) => value === stored) ?? fallback;
  } catch {
    return fallback; // storage blocked: the defaults, for this visit
  }
}

function write(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // storage blocked: the choice lasts this visit
  }
}

export const readTheme = (): Theme => read(THEME_KEY, THEMES, DEFAULT_THEME);
export const readView = (): View => read(VIEW_KEY, VIEWS, DEFAULT_VIEW);
export const saveTheme = (theme: Theme): void => write(THEME_KEY, theme);
export const saveView = (view: View): void => write(VIEW_KEY, view);
export const readHoldings = (): Holdings => read(HOLDINGS_KEY, HOLDINGS, DEFAULT_HOLDINGS);
export const saveHoldings = (holdings: Holdings): void => write(HOLDINGS_KEY, holdings);

/** The system's colour scheme, where the browser can tell it. */
export function darkQuery(): MediaQueryList | null {
  return typeof window.matchMedia === "function" ? window.matchMedia(DARK_QUERY) : null;
}

export function systemIsDark(): boolean {
  return darkQuery()?.matches ?? false;
}

export function isDark(theme: Theme, systemDark: boolean): boolean {
  return theme === "dark" || (theme === "system" && systemDark);
}

/** The resolved theme on <html>: `dark` turns Tailwind's dark variant on; `light` holds the light one (index.css). */
export function applyTheme(dark: boolean, root: HTMLElement = document.documentElement): void {
  root.classList.toggle("dark", dark);
  root.classList.toggle("light", !dark);
}

// The display preferences as React state (lib/preferences.ts keeps and applies them): the theme, which "Sistem" ties to
// the computer's setting as it changes, and the view the cards read — the simple view shows each card's one-sentence
// comment and its next step, the detailed view its tables and raw data (features.md, shared rules).

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useLayoutEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react";

import {
  applyTheme,
  darkQuery,
  isDark,
  readTheme,
  readView,
  saveTheme,
  saveView,
  systemIsDark,
  type Theme,
  type View,
} from "../lib/preferences";

interface ThemeState {
  theme: Theme;
  dark: boolean; // what the theme comes to now
  setTheme: (theme: Theme) => void;
}

interface ViewState {
  view: View;
  setView: (view: View) => void;
}

const ThemeContext = createContext<ThemeState | null>(null);
const ViewContext = createContext<ViewState | null>(null);

function subscribeToSystem(onChange: () => void): () => void {
  const query = darkQuery();
  query?.addEventListener("change", onChange);
  return () => query?.removeEventListener("change", onChange);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setChoice] = useState(readTheme);
  const systemDark = useSyncExternalStore(subscribeToSystem, systemIsDark, () => false);
  const dark = isDark(theme, systemDark);
  useLayoutEffect(() => applyTheme(dark), [dark]);
  const setTheme = useCallback((next: Theme) => {
    saveTheme(next);
    setChoice(next);
  }, []);
  const value = useMemo(() => ({ theme, dark, setTheme }), [theme, dark, setTheme]);
  return <ThemeContext value={value}>{children}</ThemeContext>;
}

export function ViewProvider({ children }: { children: ReactNode }) {
  const [view, setChoice] = useState(readView);
  const setView = useCallback((next: View) => {
    saveView(next);
    setChoice(next);
  }, []);
  const value = useMemo(() => ({ view, setView }), [view, setView]);
  return <ViewContext value={value}>{children}</ViewContext>;
}

export function useTheme(): ThemeState {
  const state = useContext(ThemeContext);
  if (!state) {
    throw new Error("useTheme is used outside ThemeProvider (AppProviders)");
  }
  return state;
}

export function useView(): ViewState {
  const state = useContext(ViewContext);
  if (!state) {
    throw new Error("useView is used outside ViewProvider (AppProviders)");
  }
  return state;
}

/** Shown in the simple view only: a card's one-sentence comment and its next step. */
export function Simple({ children }: { children: ReactNode }) {
  return useView().view === "simple" ? children : null;
}

/** Shown in the detailed view only: tables and raw data. */
export function Detailed({ children }: { children: ReactNode }) {
  return useView().view === "detailed" ? children : null;
}

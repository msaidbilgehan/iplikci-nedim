// The app's frame: a header with the name and the display switches (view and theme), a grouped menu beside the screen
// on wide windows and behind a menu button on narrow ones, and a skip link to the content for keyboard users. The
// menu shows the screens built so far (navigation.ts) and how many notifications are not seen yet.

import { type KeyboardEvent, type ReactNode, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet } from "react-router";

import { useUnreadNotifications } from "../api/queries";
import { useEventStream } from "../hooks/useEventStream";
import { cn } from "../lib/cn";
import type { Theme, View } from "../lib/preferences";
import { builtGroups, MENU, type ScreenGroup, SETUP } from "./navigation";
import { useTheme, useView } from "./Preferences";
import { useFirstRun } from "./setup/useFirstRun";
import { CloseIcon, MenuIcon, MonitorIcon, MoonIcon, SunIcon } from "./ui/Icons";
import { Segmented } from "./ui/Segmented";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600";

export function Layout() {
  useEventStream();
  useFirstRun();
  const { t } = useTranslation("shell");
  const unread = useUnreadNotifications();
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const menuButton = useRef<HTMLButtonElement>(null);

  function closeOnEscape(event: KeyboardEvent) {
    if (event.key === "Escape" && open) {
      setOpen(false);
      menuButton.current?.focus();
    }
  }

  return (
    <div className="min-h-dvh bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      <a
        href="#icerik"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:p-2 dark:focus:bg-zinc-900"
      >
        {t("skipToContent")}
      </a>
      <header className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2">
          <button
            ref={menuButton}
            type="button"
            aria-expanded={open}
            aria-controls={menuId}
            onClick={() => setOpen((was) => !was)}
            className={cn(
              "inline-flex min-h-11 items-center gap-2 rounded-md px-2 text-sm font-medium lg:hidden",
              "text-zinc-800 hover:bg-zinc-100 dark:text-zinc-100 dark:hover:bg-zinc-800",
              FOCUS,
            )}
          >
            {open ? <CloseIcon className="size-5" /> : <MenuIcon className="size-5" />}
            {t("menu.button")}
          </button>
          <Link to="/" className={cn("rounded-md px-1 text-lg font-semibold", FOCUS)}>
            {t("appName")}
          </Link>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <ViewSwitch />
            <ThemeSwitch />
          </div>
        </div>
      </header>
      <div className="mx-auto flex max-w-7xl flex-col lg:flex-row">
        <nav
          id={menuId}
          aria-label={t("menu.label")}
          onKeyDown={closeOnEscape}
          className={cn(
            open ? "block" : "hidden",
            "border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900",
            "lg:sticky lg:top-0 lg:block lg:max-h-dvh lg:w-56 lg:shrink-0 lg:self-start lg:overflow-y-auto",
            "lg:border-b-0 lg:border-r lg:bg-transparent lg:dark:bg-transparent",
          )}
        >
          <div className="flex flex-col gap-4 px-3 py-4">
            {builtGroups(MENU).map((group) => (
              <MenuGroup key={group.key} group={group} unread={unread} onChoose={() => setOpen(false)} />
            ))}
            {builtGroups([SETUP]).map((group) => (
              <div key={group.key} className="border-t border-zinc-200 pt-4 dark:border-zinc-800">
                <MenuGroup group={group} unread={unread} onChoose={() => setOpen(false)} />
              </div>
            ))}
          </div>
        </nav>
        <main id="icerik" tabIndex={-1} className="min-w-0 flex-1 px-4 py-6 focus:outline-none">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

interface MenuGroupProps {
  group: ScreenGroup;
  unread: number;
  onChoose: () => void; // a screen was chosen: the menu closes on narrow screens
}

function MenuGroup({ group, unread, onChoose }: MenuGroupProps) {
  const { t } = useTranslation("shell");
  const heading = useId();
  return (
    <div>
      <p id={heading} className="px-3 pb-1 text-xs font-semibold text-zinc-600 dark:text-zinc-400">
        {t(`groups.${group.key}`)}
      </p>
      <ul aria-labelledby={heading} className="flex flex-col gap-0.5">
        {group.screens.map((screen) => (
          <li key={screen.to}>
            <NavLink
              to={screen.to}
              end={screen.end ?? false}
              onClick={onChoose}
              className={({ isActive }) =>
                cn(
                  "flex min-h-11 items-center rounded-md border-l-[3px] px-3 text-sm font-medium",
                  FOCUS,
                  // The current screen: a bar beside it as well as the colour.
                  isActive
                    ? "border-teal-700 bg-teal-50 text-teal-900 dark:border-teal-400 dark:bg-teal-950 dark:text-teal-100"
                    : "border-transparent text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800",
                )
              }
            >
              {t(`screens.${screen.key}`)}
              {screen.key === "notifications" ? <UnreadCount count={unread} /> : null}
            </NavLink>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The notifications not seen yet, beside their menu item: a number to see and words to hear. */
function UnreadCount({ count }: { count: number }) {
  const { t } = useTranslation("shell");
  if (count <= 0) {
    return null;
  }
  // The space stands outside the spans: a screen reader joins the words, the menu item's flex box drops it.
  return (
    <>
      {" "}
      <span
        aria-hidden="true"
        className={cn(
          "ml-auto inline-flex min-w-5 items-center justify-center rounded-full px-1.5 text-xs font-semibold",
          "bg-teal-700 text-white dark:bg-teal-400 dark:text-zinc-950",
        )}
      >
        {count > 99 ? "99+" : count}
      </span>
      <span className="sr-only">{t("unread", { count })}</span>
    </>
  );
}

function ViewSwitch() {
  const { t } = useTranslation("shell");
  const { view, setView } = useView();
  const options: Array<{ value: View; label: string }> = [
    { value: "simple", label: t("view.simple") },
    { value: "detailed", label: t("view.detailed") },
  ];
  return <Segmented legend={t("view.label")} options={options} value={view} onChange={setView} />;
}

function ThemeSwitch() {
  const { t } = useTranslation("shell");
  const { theme, setTheme } = useTheme();
  const options: Array<{ value: Theme; label: string; icon: ReactNode }> = [
    { value: "light", label: t("theme.light"), icon: <SunIcon /> },
    { value: "dark", label: t("theme.dark"), icon: <MoonIcon /> },
    { value: "system", label: t("theme.system"), icon: <MonitorIcon /> },
  ];
  return <Segmented legend={t("theme.label")} options={options} value={theme} onChange={setTheme} compact />;
}

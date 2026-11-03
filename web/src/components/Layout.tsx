// The app's frame: a header with the logo and the name, the notification box's bell and the display settings (view and
// theme, in one small panel), a grouped menu with an icon beside each screen — beside the screen on wide windows,
// behind a menu button on narrow ones — and a skip link to the content for keyboard users. The menu shows the screens
// built so far (navigation.ts) and how many notifications are not seen yet. A new screen opens at its top.

import * as Popover from "@radix-ui/react-popover";
import { type KeyboardEvent, type ReactNode, useId, useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useLocation, useNavigationType } from "react-router";

import { useUnreadNotifications } from "../api/queries";
import { useEventStream } from "../hooks/useEventStream";
import { cn } from "../lib/cn";
import type { Theme, View } from "../lib/preferences";
import { builtGroups, everydayScreens, MENU, otherGroups, type Screen, type ScreenGroup, SETUP } from "./navigation";
import { useTheme, useView } from "./Preferences";
import { useFirstRun } from "./setup/useFirstRun";
import { BellIcon, ChevronDownIcon, CloseIcon, MenuIcon, MonitorIcon, MoonIcon, SunIcon } from "./ui/Icons";
import { Segmented } from "./ui/Segmented";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600";
const HEADER_BUTTON = cn(
  "inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-lg px-2.5 text-sm font-medium",
  "text-zinc-700 hover:bg-zinc-100 dark:text-zinc-200 dark:hover:bg-zinc-800",
  FOCUS,
);

/**
 * A new screen opens at its top, as a page does: a link followed from low on one screen (a chart's bar, a card's step)
 * must not leave the next one scrolled down to where the last one was. A filter, a part (?bolum=) or a row's detail
 * changes the address of the same screen and keeps the place; back and forward leave it to the browser's own return.
 */
function useScreenStart(): void {
  const { pathname } = useLocation();
  const type = useNavigationType();
  const was = useRef(pathname);
  useLayoutEffect(() => {
    if (pathname !== was.current && type !== "POP") {
      window.scrollTo(0, 0);
    }
    was.current = pathname;
  }, [pathname, type]);
}

export function Layout() {
  useEventStream();
  useFirstRun();
  useScreenStart();
  const { t } = useTranslation("shell");
  const { view } = useView();
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
      <header className="sticky top-0 z-30 border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-2 px-3 sm:px-4">
          <button
            ref={menuButton}
            type="button"
            aria-expanded={open}
            aria-controls={menuId}
            onClick={() => setOpen((was) => !was)}
            className={cn(HEADER_BUTTON, "lg:hidden")}
          >
            {open ? <CloseIcon className="size-5" /> : <MenuIcon className="size-5" />}
            <span className="sr-only sm:not-sr-only">{t("menu.button")}</span>
          </button>
          <Link to="/" className={cn("flex min-h-11 items-center gap-2.5 rounded-lg pr-2", FOCUS)}>
            <img src="/logo.png" alt="" width={32} height={32} className="size-8 rounded-lg" />
            <span className="text-base font-semibold tracking-tight">{t("appName")}</span>
          </Link>
          <div className="ml-auto flex items-center gap-1">
            <Bell unread={unread} />
            <DisplayMenu />
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
            "lg:sticky lg:top-14 lg:block lg:max-h-[calc(100dvh-3.5rem)] lg:w-60 lg:shrink-0 lg:self-start",
            "lg:overflow-y-auto lg:border-b-0 lg:border-r lg:bg-transparent lg:dark:bg-transparent",
          )}
        >
          <div className="flex flex-col gap-5 px-3 py-4">
            {view === "simple" ? (
              <SimpleMenu unread={unread} onChoose={() => setOpen(false)} />
            ) : (
              <>
                {builtGroups(MENU).map((group) => (
                  <MenuGroup key={group.key} group={group} unread={unread} onChoose={() => setOpen(false)} />
                ))}
                {builtGroups([SETUP]).map((group) => (
                  <div key={group.key} className="border-t border-zinc-200 pt-4 dark:border-zinc-800">
                    <MenuGroup group={group} unread={unread} onChoose={() => setOpen(false)} />
                  </div>
                ))}
              </>
            )}
          </div>
        </nav>
        <main id="icerik" tabIndex={-1} className="min-w-0 flex-1 px-4 py-6 focus:outline-none lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

/** Whether the address is the screen's own, or one under it unless the screen is marked only on its own. */
function isAt(screen: Screen, pathname: string): boolean {
  return screen.end ? pathname === screen.to : pathname === screen.to || pathname.startsWith(`${screen.to}/`);
}

/**
 * The simple view's menu: the everyday screens in one list, the rest grouped under "Diğer ekranlar", which opens by
 * itself while one of them is shown, so the current screen is never hidden.
 */
function SimpleMenu({ unread, onChoose }: { unread: number; onChoose: () => void }) {
  const { t } = useTranslation("shell");
  const { pathname } = useLocation();
  const others = otherGroups([...MENU, SETUP]);
  const here = others.some((group) => group.screens.some((screen) => isAt(screen, pathname)));
  const [chosen, setChosen] = useState(false);
  return (
    <>
      <ScreenList screens={everydayScreens(MENU)} label={t("menu.everyday")} unread={unread} onChoose={onChoose} />
      <details
        open={chosen || here}
        onToggle={(event) => setChosen(event.currentTarget.open)}
        className="group border-t border-zinc-200 pt-3 dark:border-zinc-800"
      >
        <summary
          className={cn(
            "flex min-h-11 cursor-pointer list-none items-center gap-3 rounded-lg px-3 text-sm font-medium lg:min-h-9",
            "text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800",
            "[&::-webkit-details-marker]:hidden",
            FOCUS,
          )}
        >
          <ChevronDownIcon className="size-[1.125rem] shrink-0 opacity-80 transition-transform group-open:rotate-180 motion-reduce:transition-none" />
          {t("menu.more")}
          <UnreadCount count={unread} />
        </summary>
        <div className="mt-3 flex flex-col gap-5">
          {others.map((group) => (
            <MenuGroup key={group.key} group={group} unread={unread} onChoose={onChoose} />
          ))}
        </div>
      </details>
    </>
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
      <p id={heading} className="px-3 pb-1.5 text-xs font-semibold text-zinc-600 dark:text-zinc-400">
        {t(`groups.${group.key}`)}
      </p>
      <ScreenList screens={group.screens} labelledBy={heading} unread={unread} onChoose={onChoose} />
    </div>
  );
}

interface ScreenListProps {
  screens: readonly Screen[];
  label?: string; // the list's name, or the heading naming it
  labelledBy?: string;
  unread: number;
  onChoose: () => void;
}

function ScreenList({ screens, label, labelledBy, unread, onChoose }: ScreenListProps) {
  const { t } = useTranslation("shell");
  return (
    <ul aria-label={label} aria-labelledby={labelledBy} className="flex flex-col gap-0.5">
      {screens.map((screen) => {
        const ScreenIcon = screen.icon;
        return (
          <li key={screen.to}>
            <NavLink
              to={screen.to}
              end={screen.end ?? false}
              onClick={onChoose}
              className={({ isActive }) =>
                cn(
                  "relative flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium lg:min-h-9",
                  FOCUS,
                  // The current screen: a bar beside it as well as the colour.
                  isActive
                    ? cn(
                        "bg-teal-50 text-teal-900 dark:bg-teal-950 dark:text-teal-50",
                        "before:absolute before:inset-y-1.5 before:left-0 before:w-[3px] before:rounded-full",
                        "before:bg-teal-700 dark:before:bg-teal-400",
                      )
                    : "text-zinc-700 hover:bg-zinc-100 hover:text-zinc-950 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-zinc-50",
                )
              }
            >
              <ScreenIcon className="size-[1.125rem] shrink-0 opacity-80" />
              {t(`screens.${screen.key}`)}
              {screen.key === "notifications" ? <UnreadCount count={unread} /> : null}
            </NavLink>
          </li>
        );
      })}
    </ul>
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

/** The header's way to the notification box, with how many are not seen yet. */
function Bell({ unread }: { unread: number }) {
  const { t } = useTranslation("shell");
  return (
    // Named by its own words, hidden but read, not by an aria-label: the count on the bell is text one sees, and a
    // name given apart from the visible text is to contain it (WCAG 2.5.3), which "99+" or a lone digit cannot be.
    <Link to="/bildirimler" title={t("bell")} className={cn(HEADER_BUTTON, "relative")}>
      <BellIcon className="size-5" />
      <span className="sr-only">{t("bell")}</span>
      {unread > 0 ? (
        <>
          <span
            aria-hidden="true"
            className={cn(
              "absolute right-1 top-1.5 inline-flex min-w-4 items-center justify-center rounded-full px-1",
              "text-[0.6875rem] font-semibold leading-4 bg-teal-700 text-white dark:bg-teal-400 dark:text-zinc-950",
            )}
          >
            {unread > 99 ? "99+" : unread}
          </span>
          {/* The space, a text of its own, keeps the count a word apart in the name: "Bildirim kutusu (3 okunmamış)". */}
          {" "}
          <span className="sr-only">{t("unread", { count: unread })}</span>
        </>
      ) : null}
    </Link>
  );
}

const THEME_ICONS: Record<Theme, ReactNode> = {
  light: <SunIcon />,
  dark: <MoonIcon />,
  system: <MonitorIcon />,
};

/** The view and the theme in one small panel: the header keeps room, the chosen view stays named on the button. */
function DisplayMenu() {
  const { t } = useTranslation("shell");
  const { view, setView } = useView();
  const { theme, setTheme } = useTheme();
  const views: Array<{ value: View; label: string }> = [
    { value: "simple", label: t("view.simple") },
    { value: "detailed", label: t("view.detailed") },
  ];
  const themes: Array<{ value: Theme; label: string; icon: ReactNode }> = [
    { value: "light", label: t("theme.light"), icon: <SunIcon /> },
    { value: "dark", label: t("theme.dark"), icon: <MoonIcon /> },
    { value: "system", label: t("theme.system"), icon: <MonitorIcon /> },
  ];
  return (
    <Popover.Root>
      <Popover.Trigger className={HEADER_BUTTON}>
        {THEME_ICONS[theme]}
        <span className="sr-only sm:not-sr-only">{t("display.button", { view: t(`view.${view}`) })}</span>
        <ChevronDownIcon className="hidden size-4 opacity-70 sm:block" />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          aria-label={t("display.label")}
          align="end"
          sideOffset={6}
          collisionPadding={8}
          className={cn(
            "z-50 flex w-72 flex-col gap-4 rounded-xl border p-4 text-sm shadow-lg",
            "border-zinc-200 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100",
          )}
        >
          <div className="flex flex-col gap-2">
            <p className="font-medium">{t("view.label")}</p>
            <Segmented legend={t("view.label")} options={views} value={view} onChange={setView} />
            <p className="text-xs text-zinc-600 dark:text-zinc-400">{t(`view.hint.${view}`)}</p>
          </div>
          <div className="flex flex-col gap-2">
            <p className="font-medium">{t("theme.label")}</p>
            <Segmented legend={t("theme.label")} options={themes} value={theme} onChange={setTheme} />
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

import { NavLink, Outlet } from "react-router";

import { useEventStream } from "../hooks/useEventStream";
import { cn } from "../lib/cn";

const LINKS = [
  { to: "/belgeler", label: "Belgeler" },
  { to: "/abonelikler", label: "Abonelikler" },
  { to: "/takvim", label: "Takvim" },
  { to: "/faturalar", label: "Faturalar" },
  { to: "/sistem", label: "Sistem" },
  { to: "/kurulum/eklenti", label: "Tarayıcı eklentisi" },
] as const;

export function Layout() {
  useEventStream();
  return (
    <div className="min-h-dvh bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      <a
        href="#icerik"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:rounded focus:bg-white focus:p-2 dark:focus:bg-zinc-900"
      >
        İçeriğe geç
      </a>
      <header className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <span className="text-lg font-semibold">İplikçi Nedim</span>
          <nav aria-label="Ana menü">
            <ul className="flex flex-wrap gap-1">
              {LINKS.map((link) => (
                <li key={link.to}>
                  <NavLink
                    to={link.to}
                    className={({ isActive }) =>
                      cn(
                        "inline-flex min-h-11 items-center rounded-md px-3 text-sm font-medium",
                        "focus-visible:outline-2 focus-visible:outline-teal-600",
                        isActive
                          ? "bg-teal-50 text-teal-800 dark:bg-teal-950 dark:text-teal-200"
                          : "text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800",
                      )
                    }
                  >
                    {link.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>
      <main id="icerik" className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}

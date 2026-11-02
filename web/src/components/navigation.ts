// The screens the menu leads to, grouped as someone looking after their money thinks of them (addresses from
// architecture §18), each with its icon beside its name. Every screen of the plan is listed; the menu shows those whose
// page is built. When a screen lands, add its route (routes.tsx), set `ready` here and add it to the end-to-end tests'
// list (e2e/tests/screens.spec.ts).

import type { ReactNode } from "react";

import type shell from "../locales/tr/shell.json";
import {
  BankIcon,
  BellIcon,
  CalendarCheckIcon,
  CalendarIcon,
  ChartIcon,
  ChecklistIcon,
  CoinsIcon,
  FileIcon,
  HomeIcon,
  PlugIcon,
  PulseIcon,
  ReceiptIcon,
  RepeatIcon,
  ServerIcon,
  SlidersIcon,
  SwapIcon,
  TagIcon,
  WandIcon,
} from "./ui/Icons";

export type ScreenKey = keyof (typeof shell)["screens"];
export type GroupKey = keyof (typeof shell)["groups"];

export interface Screen {
  to: string;
  key: ScreenKey; // its name: shell.json, screens
  icon: (props: { className?: string }) => ReactNode;
  ready: boolean;
  end?: boolean; // marked current only on its own address, not on the addresses under it
}

export interface ScreenGroup {
  key: GroupKey; // its name: shell.json, groups
  screens: readonly Screen[];
}

export const MENU: readonly ScreenGroup[] = [
  {
    key: "today", // what to look at first: where things stand, what happened, what needs the user
    screens: [
      { to: "/", key: "dashboard", icon: HomeIcon, ready: true, end: true },
      { to: "/akis", key: "feed", icon: PulseIcon, ready: true },
      { to: "/yapilacaklar", key: "todo", icon: ChecklistIcon, ready: true },
    ],
  },
  {
    key: "money", // the accounts, their rows, what is paid regularly and what comes next
    screens: [
      { to: "/hesaplar", key: "accounts", icon: BankIcon, ready: true },
      { to: "/islemler", key: "transactions", icon: SwapIcon, ready: true },
      { to: "/abonelikler", key: "subscriptions", icon: RepeatIcon, ready: true },
      { to: "/takvim", key: "calendar", icon: CalendarIcon, ready: true },
      { to: "/doviz", key: "fx", icon: CoinsIcon, ready: true },
    ],
  },
  {
    key: "analysis", // what the numbers mean: the assessment and each month's closing
    screens: [
      { to: "/degerlendirme", key: "insights", icon: ChartIcon, ready: true },
      { to: "/ay-sonu", key: "monthEnd", icon: CalendarCheckIcon, ready: true },
    ],
  },
  {
    key: "archive", // the documents kept and the non-bank bills matched to the bank's rows
    screens: [
      { to: "/belgeler", key: "documents", icon: FileIcon, ready: true },
      { to: "/faturalar", key: "invoices", icon: ReceiptIcon, ready: true },
    ],
  },
  {
    key: "app", // how the app behaves and how it is doing
    screens: [
      { to: "/bildirimler", key: "notifications", icon: BellIcon, ready: true },
      { to: "/kurallar", key: "rules", icon: TagIcon, ready: true },
      { to: "/ayarlar", key: "settings", icon: SlidersIcon, ready: true },
      { to: "/sistem", key: "system", icon: ServerIcon, ready: true },
    ],
  },
];

// Setting up stands apart from the everyday screens, below them.
export const SETUP: ScreenGroup = {
  key: "setup",
  screens: [
    { to: "/kurulum", key: "setup", icon: WandIcon, ready: true, end: true },
    { to: "/kurulum/eklenti", key: "extension", icon: PlugIcon, ready: true },
  ],
};

/** The groups with the screens built so far; a group with none built is left out. */
export function builtGroups(groups: readonly ScreenGroup[]): ScreenGroup[] {
  return groups
    .map((group) => ({ ...group, screens: group.screens.filter((screen) => screen.ready) }))
    .filter((group) => group.screens.length > 0);
}

/** Whether a screen of the menu is built, so a link may lead to it (lib/links.ts). */
export function isReady(key: ScreenKey): boolean {
  return [...MENU, SETUP].some((group) => group.screens.some((screen) => screen.key === key && screen.ready));
}

// The pages under a screen's address that open one thing (architecture §18); each comes with or after its list. Set
// one when its route lands, as `ready` above.
export const DETAILS: Readonly<Record<"document" | "account" | "month", boolean>> = {
  document: true, // /belgeler/:id, the viewer: ?satir=<fingerprint> opens it at a row
  account: true, // /hesaplar/:id
  month: true, // /ay-sonu/:ay
};
